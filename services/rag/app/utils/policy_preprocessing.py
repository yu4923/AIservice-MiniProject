"""Local, evidence-preserving preprocessing. No LLM or embedding API calls.

The structured facts are extraction candidates, never eligibility decisions.
PDF coordinates are points with a top-left origin; page numbers are one-based.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

VERSION = "policy-preprocess-v1"
TASK = re.compile(
    r"^\s*(?P<id>[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫIVX]+(?:\s*-\s*\d+){2,4}\s*-\s*\(\d+\)"
    r"|\d+(?:-\d+){1,3}-[가-힣]+-\d+)\s*(?P<title>.+)$"
)
REGIONS = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
           "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
           "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
           "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
           "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
           "경남": "경상남도", "제주": "제주특별자치도"}
FAMILIES = ("일자리", "교육직업훈련", "주거", "금융복지문화", "참여기반")


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def normalize(text: str) -> str:
    # NFC preserves Roman task numbers and compatibility distinctions in raw text.
    text = unicodedata.normalize("NFC", text).replace("\x00", "")
    text = re.sub(r"[\u200b\ufeff]", "", text).replace("\u00a0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()


@dataclass
class Settings:
    ocr: str = "auto"  # auto/off/required; required fails when Korean OCR is unavailable
    max_chars: int = 2200
    max_pages: int | None = None
    first_page: int = 1

    def __post_init__(self):
        if self.ocr not in {"auto", "off", "required"}:
            raise ValueError("ocr must be auto, off or required")
        if self.max_chars < 300 or self.first_page < 1:
            raise ValueError("max_chars >= 300, first_page >= 1 required")
        if self.max_pages is not None and self.max_pages < 1:
            raise ValueError("max_pages must be positive")


@dataclass
class Result:
    manifest: dict
    pages: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def save(self, directory: Path) -> Path:
        """Publish a complete local preprocessing run via a manifest written last."""
        target = directory / self.manifest["document_id"] / self.manifest["run_id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in ("pages", "policies", "chunks", "reviews"):
            tmp = target / (name + ".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as f:
                for row in getattr(self, name):
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            tmp.replace(target / (name + ".jsonl"))
        tmp = target / "manifest.json.tmp"
        tmp.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target / "manifest.json")
        return target


def source_context(source: str) -> dict:
    filename = unicodedata.normalize("NFC", source.split("!/")[-1].split("/")[-1])
    year = re.search(r"20\d{2}", filename)
    region = next((v for k, v in REGIONS.items() if re.search(r"\(" + k + r"\)", filename)), None)
    compact = re.sub(r"[\s·‧]", "", filename)
    category = next((x for x in FAMILIES if x in compact), None)
    return {"document_year": int(year[0]) if year else None, "publisher_region": region,
            "category": category, "document_type": "task_card" if "과제카드" in filename
            else "regional_plan" if region else "overview",
            "authority": "planning_document", "application_status": "unverified"}


def _bbox(item):
    return [round(float(item[k]), 2) for k in ("x0", "top", "x1", "bottom")]


def _inside(word, box):
    x, y = (word["x0"] + word["x1"]) / 2, (word["top"] + word["bottom"]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _lines(words):
    lines = []
    for word in sorted(words, key=lambda w: (round(w["top"] / 3), w["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 4:
            lines.append([word])
        else:
            lines[-1].append(word)
    result = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        result.append({"kind": "text", "text": normalize(" ".join(w["text"] for w in line)),
                       "bbox": [min(w["x0"] for w in line), min(w["top"] for w in line),
                                max(w["x1"] for w in line), max(w["bottom"] for w in line)]})
    return result


def _ocr_ready():
    if not shutil.which("tesseract"):
        return False
    try:
        result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=15)
        return result.returncode == 0 and {"kor", "eng"} <= set(result.stdout.split())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ocr_words(pdf, page_index, width, height):
    import pypdfium2 as pdfium
    with tempfile.TemporaryDirectory(prefix="policy-ocr-") as directory:
        image_path = Path(directory) / "page.png"
        doc = pdfium.PdfDocument(pdf)
        try:
            page = doc[page_index]
            bitmap = page.render(scale=3)
            image = bitmap.to_pil()
            image.save(image_path)
            sx, sy = width / image.width, height / image.height
            bitmap.close()
            page.close()
        finally:
            doc.close()
        proc = subprocess.run(["tesseract", str(image_path), "stdout", "-l", "kor+eng",
                               "--psm", "3", "tsv"], capture_output=True, text=True,
                              timeout=180, check=True)
        words = []
        for row in csv.DictReader(io.StringIO(proc.stdout), delimiter="\t"):
            if row.get("text", "").strip() and float(row.get("conf", -1)) >= 30:
                x, y = int(row["left"]) * sx, int(row["top"]) * sy
                words.append({"text": row["text"], "x0": x, "top": y,
                              "x1": x + int(row["width"]) * sx,
                              "bottom": y + int(row["height"]) * sy})
        return words


def table_text(rows):
    """Keep empty/merged cells and every header; do not invent inherited values."""
    return "\n".join(" | ".join(normalize(c or "").replace("\n", " / ") for c in row)
                     for row in rows)


def money_mentions(text):
    """Normalize literal amounts, never interpret a project budget as a benefit."""
    units = {"조": 10**12, "억": 10**8, "천만": 10**7, "백만": 10**6, "만": 10**4, "천": 1000, "": 1}
    pattern = r"(?:\d[\d,.]*\s*(?:조|억|천만|백만|만|천)\s*)+(?:\d[\d,.]*\s*)?원|\d[\d,.]*\s*원"
    result = []
    for match in re.finditer(pattern, text):
        raw = match[0]
        total = Decimal(0)
        for number, unit in re.findall(r"(\d[\d,.]*)\s*(조|억|천만|백만|만|천)?", raw):
            total += Decimal(number.replace(",", "")) * units[unit]
        result.append({"raw": raw, "value_krw": int(total), "benefit_status": "unverified"})
    return result


def extract_pages(path: Path, settings: Settings):
    import pdfplumber
    pages, reviews = [], []
    ready = settings.ocr != "off" and _ocr_ready()
    with pdfplumber.open(path) as pdf:
        count = len(pdf.pages)
        begin = settings.first_page - 1
        if begin >= count:
            raise ValueError("first_page exceeds PDF page count")
        end = min(count, begin + settings.max_pages) if settings.max_pages else count
        for i in range(begin, end):
            page = pdf.pages[i]
            raw = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            images = [_bbox(x) for x in page.images if x["x1"] > x["x0"] and x["bottom"] > x["top"]]
            flags, method = [], "native"
            needs_ocr = bool(images)  # includes hybrid pages with image-based numbers
            if needs_ocr:
                if ready:
                    try:
                        recovered = _ocr_words(str(path), i, page.width, page.height)
                        if len(raw.strip()) < 30:
                            words = recovered
                        else:
                            words += [w for w in recovered if any(_inside(w, b) for b in images)
                                      and not any(_inside(w, _bbox(n)) for n in words)]
                        method = "native+ocr"
                        # OCR confidence is not proof that numbers and conditions are correct.
                        flags.append("ocr_requires_review")
                    except Exception as exc:
                        if settings.ocr == "required":
                            raise RuntimeError(f"OCR failed on page {i + 1}") from exc
                        flags.append("ocr_failed")
                elif settings.ocr == "required":
                    raise RuntimeError("Korean OCR needs tesseract with kor+eng language data")
                else:
                    flags.append("image_text_not_verified")
            lines = _lines(words)
            printed = next((re.fullmatch(r"-\s*(\d+)\s*-", b["text"])
                            for b in reversed(lines) if b["bbox"][1] > page.height * .85
                            and re.fullmatch(r"-\s*(\d+)\s*-", b["text"])), None)
            blocks, boxes = [], []
            if len(page.edges) >= 4 and method == "native":
                try:
                    for table in page.find_tables():
                        rows = table.extract(x_tolerance=2, y_tolerance=3)
                        if len(rows) < 2 or max(map(len, rows), default=0) < 2:
                            continue
                        box = list(table.bbox)
                        boxes.append(box)
                        blocks.append({"kind": "table", "bbox": box, "rows": rows,
                                       "text": table_text(rows), "table_id": f"p{i+1}-t{len(boxes)}"})
                except Exception:
                    flags.append("table_extraction_failed")
            # OCR/table pages retain visual lines if native table geometry is unreliable.
            for line in _lines([w for w in words if not any(_inside(w, b) for b in boxes)]):
                if re.fullmatch(r"-\s*\d+\s*-", line["text"]) and line["bbox"][1] > page.height * .85:
                    continue
                blocks.append(line)
            blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
            if not normalize(raw) and not images:
                flags.append("blank_page")
            if not words and images:
                flags.append("unreadable_page")
            record = {"page": i + 1, "printed_page": printed[1] if printed else None,
                      "width": page.width, "height": page.height, "raw_text": raw,
                      "blocks": blocks, "extraction_method": method, "quality_flags": flags}
            pages.append(record)
            for reason in flags:
                if reason != "blank_page":
                    reviews.append({"page": i + 1, "reason": reason})
            page.close()
    # Only repeated marginal lines; task titles, footnotes and interior headings survive.
    marginal = Counter()
    for p in pages:
        marginal.update({b["text"] for b in p["blocks"] if b["kind"] == "text"
                         and (b["bbox"][3] < 32 or b["bbox"][1] > p["height"] - 28)
                         and not TASK.match(b["text"])})
    repeated = {s for s, n in marginal.items() if n >= max(3, math.ceil(len(pages) * .6))}
    for p in pages:
        p["blocks"] = [b for b in p["blocks"] if not (b["text"] in repeated and
                          (b["bbox"][3] < 32 or b["bbox"][1] > p["height"] - 28))]
    return pages, reviews, count


def _heading(page):
    for block in page["blocks"]:
        if block["kind"] != "text" or block["bbox"][1] > 180:
            continue
        match = TASK.match(block["text"])
        if match:
            return re.sub(r"\s", "", match["id"]), match["title"].strip()
    return None


def _section(text, previous, document_year):
    compact = text.replace(" ", "")
    if len(compact) < 100 and re.match(r"[ㅇ○-]?\((?:추진경과|진행경과)", compact):
        return {"name": text, "role": "historical_context", "year": None}
    if len(compact) < 150 and re.match(r"[ㅇ○-]?\((?:사업대상|사업내용|사업기간|지원대상|연령기준)", compact):
        if previous["role"] == "historical_context":
            return {"name": text, "role": "plan", "year": document_year}
    if len(compact) < 100 and (compact.startswith("□") or re.match(r"\d+\.", compact)):
        if "추진실적" in compact or "평가" in compact:
            short = re.search(r"[‘’'`]?(\d{2})(?:년도|년)", compact)
            return {"name": text, "role": "past_performance",
                    "year": 2000 + int(short[1]) if short else None}
        if "추진계획" in compact:
            year = re.search(r"20\d{2}", compact)
            short = re.search(r"[‘’'`](\d{2})", compact)
            return {"name": text, "role": "plan", "year": int(year[0]) if year
                    else 2000 + int(short[1]) if short else document_year}
        role = ("budget" if "예산" in compact else "schedule" if "일정" in compact
                else "performance_target" if "성과지표" in compact else previous["role"])
        return {**previous, "name": text, "role": role}
    return previous


def _facts(blocks):
    """Conservative rule candidates. Ambiguity, exceptions and scopes stay in evidence."""
    facts = []
    for index, b in enumerate(blocks):
        text = b["text"]
        if b["section_role"] in {"past_performance", "budget", "schedule", "historical_context", "performance_target"}:
            continue
        # Tables must not let historical budget values enter eligibility candidates.
        if b["kind"] == "table":
            lines = [normalize(" | ".join(c or "" for c in row)) for row in b["rows"]
                     if re.search(r"정책\s*대상|사업\s*대상|지원\s*대상|신청\s*자격", " ".join(c or "" for c in row))]
        else:
            lines = text.splitlines()
        for line in lines:
            compact = line.replace(" ", "")
            qualifiers = [{"text": n["text"], "page": n["page"], "bbox": n["bbox"]}
                          for n in blocks[index+1:index+3] if n["text"].startswith(("*", "※"))]
            scopes = re.findall(r"\(([^)]*(?:기준|유형)[^)]*)\)", line)
            base = {"evidence": line, "page": b["page"], "bbox": b["bbox"],
                    "section": b["section"], "context_year": b["context_year"],
                    "status": "candidate", "scope": scopes or "unverified", "qualifiers": qualifiers}
            for match in re.finditer(r"(?:만)?\s*(\d{1,2})\s*[~∼～–-]\s*(\d{1,2})\s*세", line):
                facts.append({**base, "field": "age", "min": int(match[1]), "max": int(match[2]),
                              "age_basis": "만나이" if match[0].lstrip().startswith("만") else "unverified"})
            upper = re.search(r"(?:만)?\s*(\d{1,2})\s*세\s*(이하|미만|이상|초과)", line)
            if upper:
                number, operator = int(upper[1]), upper[2]
                facts.append({**base, "field": "age", "operator": operator, "value": number,
                              "age_basis": "만나이" if upper[0].lstrip().startswith("만") else "unverified"})
            if "연령무관" in compact or "나이제한없" in compact:
                facts.append({**base, "field": "age", "status": "unrestricted"})
            if re.search(r"미취업|취업준비|구직자|재직|자영업|프리랜서|무주택|가구소득|중위소득|월평균소득|거주|주민등록|병역|중복|제외", line):
                facts.append({**base, "field": "eligibility_text"})
            for field_name, expression in [
                    ("employment", r"미취업(?:자)?|취업준비생|구직자|재직자|자영업자|프리랜서|취[·‧·]창업무관"),
                    ("education", r"대학원생|대학생|재학생|졸업예정자|졸업자|휴학생|비학생|학생여부무관"),
                    ("housing", r"무주택(?:세대구성원|자)?"),
                    ("residence_text", r"거주|주민등록|도내|시내|소재"),
                    ("exclusion_text", r"제외|중복|참여제한|병역")]:
                values = sorted(set(re.findall(expression, compact)))
                if values:
                    facts.append({**base, "field": field_name, "mentions": values})
            for match in re.finditer(r"(기준중위소득|중위소득|(?:도시근로자)?(?:가구원수별)?(?:가구당)?월평균소득)(\d+(?:\.\d+)?)%\s*(이하|미만|이상|초과)?", compact):
                facts.append({**base, "field": "income", "basis": match[1],
                              "percent": float(match[2]), "operator": match[3] or "unverified"})
    return facts


def build_records(pages, source, document_id, context, max_chars=2200):
    policies, chunks, reviews = [], [], []
    groups = []
    for page in pages:
        heading = _heading(page) if context["document_type"] != "overview" else None
        if heading:
            if not groups or groups[-1]["task_id"] != heading[0]:
                groups.append({"task_id": heading[0], "title": heading[1], "pages": []})
        elif not groups:
            groups.append({"task_id": "frontmatter", "title": "문서 개요·정책 체계", "pages": []})
        groups[-1]["pages"].append(page)
    for group in groups:
        pid = digest(f"{document_id}|{group['task_id']}")[:24]
        section = {"name": "요약·사업 개요", "role": "plan", "year": context["document_year"]}
        blocks = []
        for page in group["pages"]:
            for b in page["blocks"]:
                if b["kind"] == "text":
                    section = _section(b["text"], section, context["document_year"])
                blocks.append({**b, "page": page["page"], "printed_page": page["printed_page"],
                               "section": section["name"], "section_role": section["role"],
                               "context_year": section["year"], "quality_flags": page["quality_flags"]})
        facts = _facts(blocks) if group["task_id"] != "frontmatter" else []
        age = [f for f in facts if f["field"] == "age"]
        signatures = {(f.get("status"), f.get("min"), f.get("max"), f.get("operator"), f.get("value")) for f in age}
        conflicts = ["age_scope_conflict"] if len(signatures) > 1 else []
        for flag in conflicts:
            reviews.append({"policy_id": pid, "reason": flag, "evidence": age})
        # Publisher location is NOT converted to an applicant residence requirement.
        policy = {"policy_id": pid, "document_id": document_id, "source": source, **context,
                  "task_id": group["task_id"], "policy_name": group["title"],
                  "page_start": group["pages"][0]["page"], "page_end": group["pages"][-1]["page"],
                  "eligibility_status": "conflict" if conflicts else "unverified",
                  "eligibility_candidates": facts, "review_flags": conflicts,
                  "applicant_type": "unverified", "beneficiary_type": "unverified",
                  "money_mentions": [{**m, "page": b["page"], "section_role": b["section_role"],
                                      "evidence": b["text"], "bbox": b["bbox"]}
                                     for b in blocks for m in money_mentions(b["text"])],
                  "raw_text": "\n".join(p["raw_text"] for p in group["pages"])}
        policies.append(policy)
        batch = []

        def emit():
            if not batch:
                return
            first = batch[0]
            if (group["task_id"] == "frontmatter" and context["document_type"] != "overview") or sum(len(b["text"]) for b in batch) < 35:
                batch.clear()
                return
            page_ids = sorted({b["page"] for b in batch})
            refs = [{"page": b["page"], "printed_page": b["printed_page"], "bbox": b["bbox"],
                     "kind": b["kind"], "text": b["text"], **({"table_id": b["table_id"], "rows": b["rows"]}
                     if b["kind"] == "table" else {})} for b in batch]
            quality = sorted({flag for b in batch for flag in b["quality_flags"]})
            header = (f"정책: {group['title']} | 과제: {group['task_id']}\n"
                      f"문서연도: {context['document_year']} | 발행지역: {context['publisher_region'] or '중앙'}\n"
                      f"구간: {first['section']} | 내용연도: {first['context_year']} | 유형: {first['section_role']}\n"
                      f"근거: {source} | PDF 쪽: {','.join(map(str, page_ids))}\n"
                      f"자격조건 검수: {'적용범위 충돌, 확인 필요' if conflicts else '자동 추출 후보, 자격 확정 아님'}\n"
                      f"추출 검수: {', '.join(quality) if quality else '자동 추출, 원문 대조 필요'}\n"
                      "주의: 시행계획 자료이며 현재 모집·신청자격은 공식 공고 확인 필요.\n")
            content = header + "\n".join(b["text"] for b in batch)
            metadata = {"source": source, "source_key": document_id, "document_id": document_id,
                        "policy_id": pid, "task_id": group["task_id"], "title": group["title"],
                        "page": page_ids[0], "pages": page_ids, "section": first["section"],
                        "section_role": first["section_role"], "context_year": first["context_year"],
                        **context, "evidence": refs, "eligibility_status": policy["eligibility_status"],
                        "quality_flags": sorted(set(quality) | set(conflicts)),
                        "preprocessing_version": VERSION}
            chunks.append({"id": digest(f"{document_id}|{content}"), "page_content": content, "metadata": metadata})
            batch.clear()

        for block in blocks:
            # Every table remains whole; section changes and policy boundaries never overlap.
            if batch and (block["section"] != batch[0]["section"] or
                          sum(len(b["text"]) for b in batch) + len(block["text"]) > max_chars):
                # Attach an immediately following footnote to the preceding table.
                if not (block["text"].startswith(("*", "※")) and batch[-1]["kind"] == "table"):
                    emit()
            batch.append(block)
        emit()
    return policies, chunks, reviews


def preprocess_pdf(path, source_name=None, settings=None) -> Result:
    path = Path(path)
    settings = settings or Settings()
    source = unicodedata.normalize("NFC", source_name or path.name)
    document_id = digest(source)[:24]
    content_hash = digest(path.read_bytes())
    context = source_context(source)
    pages, reviews, total = extract_pages(path, settings)
    policies, chunks, conflicts = build_records(pages, source, document_id, context, settings.max_chars)
    # Text-empty image pages must stay visible in the report, never silently disappear.
    if not chunks:
        reviews.append({"reason": "no_extractable_text"})
    partial = settings.first_page != 1 or len(pages) != total
    manifest = {"document_id": document_id, "source": source, "content_hash": content_hash,
                "preprocessing_version": VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
                "run_id": digest(content_hash + json.dumps(settings.__dict__, sort_keys=True)
                                 + digest(json.dumps(chunks, ensure_ascii=False, sort_keys=True)))[:24],
                "settings": settings.__dict__, "total_pages": total, "processed_pages": len(pages),
                "partial": partial, "policy_count": len([p for p in policies if p['task_id'] != 'frontmatter']),
                "chunk_count": len(chunks), "review_count": len(reviews) + len(conflicts), **context}
    return Result(manifest, pages, policies, chunks, reviews + conflicts)
