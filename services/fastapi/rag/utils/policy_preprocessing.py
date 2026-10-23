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

VERSION = "policy-preprocess-v3"
TASK = re.compile(
    r"^\s*\[?(?P<id>[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫIVX]+(?:\s*-\s*\d+){2,4}\s*-\s*\(\d+\)"
    r"|\d+(?:\s*-\s*(?:\d+|[\ue000-\uf8ff])){1,3}\s*-\s*[가-힣]+\s*-\s*\d+"
    r"(?:\s*-\s*[①-⑳])?|\d+(?:\s*-\s*\d+){1,3}(?:\([가-힣]+\))?)"
    r"\]?(?![\d-])\s*(?P<title>.*)$"
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
    supplements: list[dict] = field(default_factory=list)

    def save(self, directory: Path) -> Path:
        """Publish a complete local preprocessing run via a manifest written last."""
        target = directory / self.manifest["document_id"] / self.manifest["run_id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in ("pages", "policies", "chunks", "reviews", "supplements"):
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
    # Consume malformed numeric tokens whole, so a date/typo cannot become a
    # valid-looking amount by matching only its suffix. '원스톱' is not currency.
    pattern = (r"(?<![\d.,])(?:"
               r"(?:\d[\d,.]*\s*(?:조|억|천만|백만|만|천)\s*)+(?:\d[\d,.]*\s*)?원"
               r"|\d[\d,.]*\s*원)"
               r"(?=$|[^\w]|(?:은|는|을|를|의|이|가|에|으로|부터|까지|씩|당|만|도|과|와|"
               r"이상|이하|미만|초과|정도|내외)(?![가-힣A-Za-z0-9_]))")
    number_pattern = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
    result = []
    for match in re.finditer(pattern, text):
        raw = match[0]
        parts = re.findall(r"(\d[\d,.]*)\s*(조|억|천만|백만|만|천)?", raw)
        if any(not number_pattern.fullmatch(number) for number, _ in parts):
            continue
        total = Decimal(0)
        for number, unit in parts:
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
                      "heading_blocks": [b for b in lines if b["bbox"][1] <= 180],
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
    # Read the header before table extraction can absorb its title cells.
    # A title can precede the task number or occupy several lines beside it.
    header = []
    has_overview = False
    # Original lines also include table-of-contents / budget table rows. Only
    # restore table-contained header text on a business-overview page.
    overview_page = any(re.match(r"1\.\s*사업\s*개요", b["text"])
                        and b["bbox"][1] <= 240 for b in page["blocks"] if b["kind"] == "text")
    heading_blocks = page.get("heading_blocks", page["blocks"]) if overview_page else page["blocks"]
    for block in heading_blocks:
        if block["kind"] != "text" or block["bbox"][1] > 180:
            continue
        if re.match(r"(?:\d+\.\s|[□ㅇ○])", block["text"]):
            has_overview = bool(re.match(r"1\.\s*사업\s*개요", block["text"]))
            break
        if re.match(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫIVX]+\.", block["text"]):
            continue
        header.append(block)
    matches = [(block, TASK.match(block["text"])) for block in header]
    numbered = [(block, match) for block, match in matches if match]
    # Short local numbers are meaningful only on an actual business start.
    numbered = [(block, match) for block, match in numbered
                if overview_page or not re.fullmatch(r"\d+\s*-\s*\d+", match["id"])]
    common = [block for block in header if has_overview and
              (re.match(r"^(?:공통|기타|공동|[\ue000-\uf8ff])(?:\s|$)", block["text"])
               or re.search(r"(?:^|\s)(?:공통|기타|공동)\s*$", block["text"]))]
    if not numbered and not common:
        return None
    anchor = (numbered[0][0] if numbered else common[0])["bbox"]
    titles = []
    for block, match in matches:
        # Exclude document/chapter headings above the actual title box.
        if block["bbox"][3] < anchor[1] - 25:
            continue
        if match:
            text = match["title"]
        else:
            text = re.sub(r"^(?:(?:공통|기타|공동)(?:\s+|$)|[\ue000-\uf8ff]\s*)", "", block["text"])
        text = re.sub(r"(?:^|\s)(?:자체|공통|기타|공동|신규|계속)\s*$", "", text).strip()
        if text:
            titles.append(text)
    if not titles:
        return None
    if numbered:
        task_id = re.sub(r"\s", "", numbered[0][1]["id"])
    else:
        label = re.match(r"(?:공통|기타|공동|[\ue000-\uf8ff])(?=\s|$)", common[0]["text"])
        task_id = label[0] if label else re.search(r"(?:공통|기타|공동)\s*$", common[0]["text"])[0].strip()
    # Keep undecodable private-use glyphs as evidence; never guess their digits.
    return task_id, " ".join(titles)


def _document_boundary(page):
    """Top-level annexes never inherit the last policy's identity or conditions."""
    lines = page.get("heading_blocks", page["blocks"])
    top = [b["text"] for b in lines if b["kind"] == "text" and b["bbox"][1] < 200]
    compact = re.sub(r"\s", "", " ".join(top[:5]))
    if any(re.fullmatch(r"\s*목\s*차\s*", line) for line in page["raw_text"].splitlines()[:4]):
        return None
    raw_compact = re.sub(r"\s", "", page["raw_text"])
    if len(raw_compact) < 200:
        compact += raw_compact  # section divider titles can be centred below the header
        if any(re.fullmatch(r"\s*(?:붙\s*임|부\s*록|별\s*첨)\s*", line)
               for line in page["raw_text"].splitlines()):
            return "appendix"
    if re.search(r"(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVX]+[.．])[^。]{0,45}(?:자체사업총괄|사업총괄표)", compact):
        return "document_summary"
    if re.match(r"(?:참고\d+(?![\d대])|부록|별첨)", compact):
        return "document_summary" if "자체사업현황" in compact or "세부사업내역" in compact else "appendix"
    return None


def _partition_pages(pages):
    mode = "policy"
    tagged = []
    for page in pages:
        boundary = _document_boundary(page)
        if boundary:
            mode = boundary
        elif mode != "policy" and _heading(page) and any(
                re.match(r"1\.\s*사업\s*개요", b["text"]) and b["bbox"][1] <= 240
                for b in page["blocks"] if b["kind"] == "text"):
            # An internal reference or front-matter note does not swallow later policies.
            mode = "policy"
        tagged.append({**page, "document_role": mode})
    return tagged


def _supplement_records(pages, source, context):
    """Preserve annex rows without assigning them to a policy or a resident."""
    result, columns = [], None
    for page in pages:
        role = page.get("document_role", "policy")
        if role == "policy":
            continue
        entries = []
        for block in page["blocks"]:
            if role != "document_summary" or block["kind"] != "table":
                continue
            for row_index, row in enumerate(block["rows"]):
                cells = [normalize(c or "") for c in row]
                compact = [re.sub(r"\s", "", c) for c in cells]
                if "사업명" in compact and any("주요내용" in c for c in compact):
                    columns = {"name": compact.index("사업명"),
                               "content": next(i for i, c in enumerate(compact) if "주요내용" in c),
                               "region": next((i for i, c in enumerate(compact) if "지자체" in c or "시군명" in c), None),
                               "years": {i: 2000 + int(m[1]) for i, c in enumerate(compact)
                                         if (m := re.search(r"[‘’'`]?(\d{2})(?:예산|년)", c))},
                               "year_headers_raw": [c for c in cells if "예산" in c or re.search(r"\d{2}.*년", c)]}
                    continue
                if not columns or max(columns["name"], columns["content"]) >= len(cells):
                    continue
                name, content = cells[columns["name"]], cells[columns["content"]]
                if not name or not content or re.match(r"^(?:소계|합계|총계)", name):
                    continue
                region_index = columns["region"]
                issuer = cells[region_index] if region_index is not None and region_index < len(cells) else None
                entries.append({"policy_name": name.replace("\n", " "), "conditions_raw": content,
                                "issuer_raw": issuer, "residence_status": "unverified",
                                "issuer_status": "literal" if issuer else "unverified",
                                "year_mapping_status": "header_literal" if columns["years"] and
                                len(columns["years"]) == len(columns["year_headers_raw"]) else "requires_review",
                                "year_headers_raw": columns["year_headers_raw"],
                                "year_values_raw": {str(year): cells[i] for i, year in columns["years"].items() if i < len(cells)},
                                "page": page["page"], "bbox": block["bbox"], "row_index": row_index,
                                "cells": cells, "link_status": "requires_review",
                                "quality_flags": page["quality_flags"]})
        result.append({"record_type": role, "source": source, **context, "page": page["page"],
                       "raw_text": page["raw_text"], "blocks": page["blocks"], "entries": entries,
                       "quality_flags": page["quality_flags"], "policy_link_status": "unverified"})
    return result


def _link_summary_evidence(supplements, policies, chunks, reviews):
    """Exact names are review candidates, never proof of matching local policies."""
    key = lambda value: re.sub(r"[\W_]", "", normalize(value))
    for supplement in supplements:
        for entry in supplement["entries"]:
            matches = [p for p in policies if key(p["policy_name"]) == key(entry["policy_name"])]
            entry["name_candidates"] = [p["policy_id"] for p in matches]
            issuer = re.sub(r"\([^)]*\)", "", entry["issuer_raw"] or "")
            if len(matches) != 1 or key(issuer) != key(supplement["publisher_region"] or ""):
                continue
            policy = matches[0]
            block = {"kind": "text", "text": entry["conditions_raw"], "page": entry["page"],
                     "bbox": entry["bbox"], "section": "독립 총괄표", "section_role": "plan",
                     "context_year": supplement["document_year"], "quality_flags": entry["quality_flags"]}
            summary_facts = _facts([block])
            entry["condition_candidates"] = summary_facts
            signatures = lambda facts: {(f["field"], f.get("min"), f.get("max"), f.get("percent"),
                                          f.get("percent_min"), f.get("percent_max"), f.get("operator"))
                                         for f in facts if f["field"] in {"age", "income"}}
            summary, body = signatures(summary_facts), signatures(policy["eligibility_candidates"])
            if not summary or not body or summary <= body:
                continue
            reason = "summary_body_condition_difference"
            reviews.append({"policy_id": policy["policy_id"], "reason": reason,
                            "status": "requires_review", "summary": summary_facts,
                            "body": policy["eligibility_candidates"], "page": entry["page"]})
            if reason not in policy["review_flags"]:
                policy["review_flags"].append(reason)
            if policy["eligibility_status"] != "conflict":
                policy["eligibility_status"] = "requires_review"
            for chunk in chunks:
                if chunk["metadata"]["policy_id"] == policy["policy_id"]:
                    chunk["metadata"]["eligibility_status"] = policy["eligibility_status"]
                    chunk["metadata"]["verification_status"] = "requires_review"
                    chunk["metadata"]["quality_flags"] = sorted(set(chunk["metadata"]["quality_flags"]) | {reason})
                    chunk["page_content"] += "\n검수: 총괄표·본문 조건 차이, 적용범위 확인 필요."
                    chunk["id"] = digest(f"{policy['document_id']}|{chunk['page_content']}")


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
            return {"name": text, "role": "future_plan" if "이후" in compact else "plan", "year": int(year[0]) if year
                    else 2000 + int(short[1]) if short else document_year}
        role = ("budget" if "예산" in compact else "schedule" if "일정" in compact
                else "performance_target" if "성과지표" in compact else previous["role"])
        return {**previous, "name": text, "role": role}
    return previous


def _candidate_lines(block):
    if block["kind"] != "table":
        return [(line, None, []) for line in block["text"].splitlines()]
    rows = block["rows"]
    header = " ".join(str(c or "") for row in rows[:3] for c in row)
    eligibility_table = bool(re.search(r"지원\s*대상|정책\s*대상|연령\s*기준|소득\s*기준|신청\s*자격", header))
    result = []
    notes = [{"text": table_text([row]), "page": block["page"], "bbox": block["bbox"]}
             for row in rows if table_text([row]).lstrip().startswith(("*", "※", "단,"))]
    for row in rows:
        line = table_text([row])
        if not eligibility_table and not re.search(r"정책\s*대상|사업\s*대상|지원\s*대상|신청\s*자격", line):
            continue
        cells = [normalize(c or "") for c in row]
        subject = cells[0] if cells else None
        if subject and (re.search(r"지원\s*대상|정책\s*대상|연령|소득|나이|자격", subject)
                        or re.search(r"\d|세|%", subject)):
            subject = None
        result.append((line, subject, notes))
    return result


def _age_mentions(line):
    line = line.replace("/", " ")  # wrapped table cells; keep offsets and raw evidence
    ranges = []
    pattern = (r"(?<!\d)(?:만\s*)?(?P<low>\d{1,2})\s*(?:세\s*)?"
               r"(?P<low_op>이상|초과)?\s*[~∼～–-]\s*(?:만\s*)?"
               r"(?P<high>\d{1,2})\s*세\s*(?P<high_op>이하|미만)?")
    for match in re.finditer(pattern, line):
        ranges.append(match.span())
        yield match, {"min": int(match["low"]), "max": int(match["high"]),
                      "lower_inclusive": match["low_op"] != "초과",
                      "upper_inclusive": match["high_op"] != "미만",
                      "age_basis": "만나이" if "만" in match[0] else "unverified"}
    for match in re.finditer(r"(?<!\d)(?:만\s*)?(\d{1,2})\s*세\s*(이하|미만|이상|초과)", line):
        if any(a <= match.start() < b for a, b in ranges):
            continue
        number, operator = int(match[1]), match[2]
        bounds = {"min": number, "lower_inclusive": operator == "이상"} if operator in {"이상", "초과"} else {
            "max": number, "upper_inclusive": operator == "이하"}
        yield match, {**bounds, "operator": operator, "value": number,
                      "age_basis": "만나이" if "만" in match[0] else "unverified"}


def _facts(blocks):
    """Keep row-specific subjects, bounds, exceptions and extraction provenance."""
    facts = []
    for index, b in enumerate(blocks):
        if b["section_role"] in {"past_performance", "budget", "schedule", "historical_context", "performance_target", "future_plan"}:
            continue
        for line, subject, row_notes in _candidate_lines(b):
            compact = re.sub(r"\s", "", line)
            qualifiers = row_notes + [{"text": n["text"], "page": n["page"], "bbox": n["bbox"]}
                                     for n in blocks[index+1:index+3]
                                     if n["text"].lstrip().startswith(("*", "※", "단,", "다만"))]
            for following in blocks[index+1:index+5]:
                if re.search(r"\(사업\s*내용\)|\(사업비\)|\(추진\s*체계\)", following["text"]):
                    break
                if re.search(r"기타\s*조건|우선\s*선발|차순위|예외|병역|군복무|다자녀", following["text"]):
                    note = {"text": following["text"], "page": following["page"], "bbox": following["bbox"],
                            "scope_status": "unverified"}
                    if not any(q["text"] == note["text"] and q["page"] == note["page"] for q in qualifiers):
                        qualifiers.append(note)
            scopes = re.findall(r"\(([^)]*(?:기준|유형)[^)]*)\)", line)
            flags = b.get("quality_flags", [])
            numeric_review = bool(set(flags) & {"ocr_requires_review", "image_text_not_verified", "ocr_failed"})
            base = {"evidence": line, "page": b["page"], "bbox": b["bbox"],
                    "section": b["section"], "context_year": b["context_year"],
                    "status": "candidate", "scope": scopes or "unverified", "subject": subject,
                    "condition_group": digest(f"{b['page']}|{b['bbox']}|{subject or line}")[:16],
                    "qualifiers": qualifiers, "quality_flags": flags,
                    "verification_status": "requires_review" if numeric_review else "candidate",
                    "extraction_method": b.get("extraction_method", "native"),
                    "applicability_text": line,
                    "exceptions": re.findall(r"(?:단[,，]|다만|※|예외)[^;\n]+", line)}
            for match, values in _age_mentions(line):
                # Explicit exception subjects must not overwrite the ordinary age range.
                prefix = line[:match.start()]
                special = re.search(r"(군필자|군복무자|병역이행자|차상위이하|차상위초과|수급자|일반청년)(?:는|은|의)?\s*$", prefix)
                age_subject = subject or (special[1] if special else None)
                invalid = values.get("min", 0) > values.get("max", 99)
                facts.append({**base, "field": "age", **values, "subject": age_subject,
                              "verification_status": "requires_review" if invalid or numeric_review else "candidate"})
            if "연령무관" in compact or "나이제한없" in compact:
                facts.append({**base, "field": "age", "status": "unrestricted"})
            if re.search(r"미취업|취업준비|구직자|재직|자영업|프리랜서|무주택|가구소득|중위소득|월평균소득|거주|주민등록|병역|중복|제외", line):
                facts.append({**base, "field": "eligibility_text"})
            if re.search(r"우선\s*선발|차순위|우대|예외|다자녀|장애인", line):
                facts.append({**base, "field": "selection_text"})
            for field_name, expression in [
                    ("employment", r"미취업(?:자)?|취업준비생|구직자|재직자|자영업자|프리랜서|취[·‧·]창업무관"),
                    ("education", r"대학원생|대학생|재학생|졸업예정자|졸업자|휴학생|비학생|학생여부무관"),
                    ("housing", r"무주택(?:세대구성원|자)?"),
                    ("residence_text", r"거주|주민등록|도내|시내|소재"),
                    ("exclusion_text", r"제외|중복|참여제한|병역")]:
                values = sorted(set(re.findall(expression, compact)))
                if values:
                    facts.append({**base, "field": field_name, "mentions": values})
            basis = r"(기준중위소득|중위소득|(?:도시근로자)?(?:가구원수별)?(?:가구당)?월평균소득)"
            pattern = basis + r"(\d+(?:\.\d+)?)%(이하|미만|이상|초과)?(?:[~∼～–-](\d+(?:\.\d+)?)%(이하|미만|이상|초과)?)?"
            income_text = re.sub(r"(?<=소득)/(?=\d)", "", compact)
            for match in re.finditer(pattern, income_text):
                values = {"percent": float(match[2]), "operator": match[3] or "unverified"}
                if match[4]:
                    values = {"percent_min": float(match[2]), "percent_max": float(match[4]),
                              "lower_inclusive": match[3] != "초과", "upper_inclusive": match[5] != "미만"}
                facts.append({**base, "field": "income", "basis": match[1], **values})
    return facts


def _condition_conflicts(facts):
    """Different named cohorts are not a contradiction; unknown overlaps need review."""
    reasons = []
    for field_name in ("age", "income"):
        candidates = [f for f in facts if f["field"] == field_name]
        conflict = False
        for i, first in enumerate(candidates):
            for second in candidates[i+1:]:
                if first["context_year"] != second["context_year"]:
                    continue
                if first.get("subject") and second.get("subject") and first["subject"] != second["subject"]:
                    continue
                if field_name == "income" and first["basis"].replace("기준", "") != second["basis"].replace("기준", ""):
                    continue
                keys = ("status", "min", "max", "lower_inclusive", "upper_inclusive", "age_basis") if field_name == "age" else (
                    "percent", "operator", "percent_min", "percent_max", "lower_inclusive", "upper_inclusive")
                if tuple(first.get(k) for k in keys) != tuple(second.get(k) for k in keys):
                    conflict = True
        if conflict:
            reasons.append(field_name + "_scope_conflict")
    return reasons


def _unparsed_age(block):
    if block["section_role"] != "plan":
        return False
    if block["kind"] == "table":
        for index, row in enumerate(block["rows"][:3]):
            age_column = next((i for i, c in enumerate(row) if "연령기준" in re.sub(r"\s", "", c or "")), None)
            if age_column is not None:
                values = [row[age_column] or "" for row in block["rows"][index+1:] if age_column < len(row)]
                return any(re.search(r"\d", value) and not list(_age_mentions(value)) for value in values)
        return False
    return bool(re.search(r"(?:연령|나이)\s*기준[)）]?\s*[:：]?\s*(?:만\s*)?\d", block["text"])) and not list(_age_mentions(block["text"]))


def build_records(pages, source, document_id, context, max_chars=2200):
    policies, chunks, reviews = [], [], []
    groups = []
    for page in _partition_pages(pages):
        if page["document_role"] != "policy":
            continue
        heading = _heading(page) if context["document_type"] != "overview" else None
        if heading:
            if not groups or (groups[-1]["task_id"], groups[-1]["title"]) != heading:
                groups.append({"task_id": heading[0], "title": heading[1], "pages": []})
        elif not groups:
            groups.append({"task_id": "frontmatter", "title": "문서 개요·정책 체계", "pages": []})
        groups[-1]["pages"].append(page)
    for group in groups:
        # Regional documents can reuse task IDs (especially PUA glyphs / 공통).
        pid = digest(f"{document_id}|{group['task_id']}|{group['pages'][0]['page']}")[:24]
        if re.search(r"[\ue000-\uf8ff]", group["task_id"]):
            reviews.append({"policy_id": pid, "reason": "task_number_unverified",
                            "page": group["pages"][0]["page"], "raw_task_id": group["task_id"]})
        section = {"name": "요약·사업 개요", "role": "plan", "year": context["document_year"]}
        blocks = []
        for page in group["pages"]:
            for b in page["blocks"]:
                if b["kind"] == "text":
                    section = _section(b["text"], section, context["document_year"])
                blocks.append({**b, "page": page["page"], "printed_page": page["printed_page"],
                               "section": section["name"], "section_role": section["role"],
                               "context_year": section["year"], "quality_flags": page["quality_flags"],
                               "extraction_method": page.get("extraction_method", "native")})
        facts = _facts(blocks) if group["task_id"] != "frontmatter" else []
        money = [{**m, "page": b["page"], "section_role": b["section_role"],
                  "context_year": b["context_year"],
                  "evidence": b["text"], "bbox": b["bbox"], "quality_flags": b["quality_flags"],
                  "extraction_method": b.get("extraction_method", "native"),
                  "verification_status": "requires_review" if set(b["quality_flags"]) & {
                      "ocr_requires_review", "image_text_not_verified", "ocr_failed"} else "candidate"}
                 for b in blocks for m in money_mentions(b["text"])]
        conflicts = _condition_conflicts(facts)
        for flag in conflicts:
            reviews.append({"policy_id": pid, "reason": flag,
                            "evidence": [f for f in facts if f["field"] == flag.split("_")[0]]})
        numeric = [f for f in facts if f["field"] in {"age", "income"} and f["verification_status"] == "requires_review"]
        numeric += [{**m, "field": "money"} for m in money if m["verification_status"] == "requires_review"]
        if numeric:
            reviews.append({"policy_id": pid, "reason": "numeric_evidence_requires_review", "evidence": numeric})
        year_mismatches = {(b["section"], b["context_year"]) for b in blocks
                           if b["section_role"] == "plan" and re.match(r"\d+\.", b["section"])
                           and b["context_year"] not in (None, context["document_year"])}
        for name, year in sorted(year_mismatches):
            reviews.append({"policy_id": pid, "reason": "plan_year_mismatch", "section": name,
                            "context_year": year, "document_year": context["document_year"]})
        review_flags = conflicts + (["numeric_evidence_requires_review"] if numeric else []) + (["plan_year_mismatch"] if year_mismatches else [])
        unparsed = [b for b in blocks if _unparsed_age(b)]
        if unparsed:
            review_flags.append("unparsed_age_condition")
            reviews.append({"policy_id": pid, "reason": "unparsed_age_condition",
                            "evidence": [{"page": b["page"], "bbox": b["bbox"], "text": b["text"]} for b in unparsed]})
        # Publisher location is NOT converted to an applicant residence requirement.
        policy = {"policy_id": pid, "document_id": document_id, "source": source, **context,
                  "task_id": group["task_id"], "policy_name": group["title"],
                  "page_start": group["pages"][0]["page"], "page_end": group["pages"][-1]["page"],
                  "pages": [p["page"] for p in group["pages"]],
                  "eligibility_status": "conflict" if conflicts else "requires_review" if review_flags else "unverified",
                  "eligibility_candidates": facts, "review_flags": review_flags,
                  "applicant_type": "unverified", "beneficiary_type": "unverified",
                  "applicant_residence_status": "unverified",
                  "money_mentions": money,
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
                      f"자격조건 검수: {'적용범위 충돌, 확인 필요' if conflicts else '조건 근거 검토 필요' if review_flags else '자동 추출 후보, 자격 확정 아님'}\n"
                      f"추출 검수: {', '.join(quality) if quality else '자동 추출, 원문 대조 필요'}\n"
                      "주의: 시행계획 자료이며 현재 모집·신청자격은 공식 공고 확인 필요.\n")
            content = header + "\n".join(b["text"] for b in batch)
            metadata = {"source": source, "source_key": document_id, "document_id": document_id,
                        "policy_id": pid, "task_id": group["task_id"], "title": group["title"],
                        "page": page_ids[0], "pages": page_ids, "section": first["section"],
                        "section_role": first["section_role"], "context_year": first["context_year"],
                        **context, "evidence": refs, "eligibility_status": policy["eligibility_status"],
                        "quality_flags": sorted(set(quality) | set(review_flags)),
                        "review_flags": review_flags,
                        "record_type": "policy_evidence",
                        "applicant_residence_status": "unverified",
                        "verification_status": "requires_review" if review_flags else "candidate",
                        "eligibility_candidates": [f for f in facts if f["page"] in page_ids and f["section"] == first["section"]],
                        "money_candidates": [m for m in money if m["page"] in page_ids and m["section_role"] == first["section_role"]
                                             and m["context_year"] == first["context_year"]],
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
    pages = _partition_pages(pages)
    policies, chunks, conflicts = build_records(pages, source, document_id, context, settings.max_chars)
    supplements = _supplement_records(pages, source, context)
    _link_summary_evidence(supplements, policies, chunks, conflicts)
    # Text-empty image pages must stay visible in the report, never silently disappear.
    if not chunks:
        has_text = any(p["raw_text"].strip() for p in pages)
        reviews.append({"reason": "policy_heading_not_found" if has_text and context["document_type"] != "overview"
                        else "no_extractable_text"})
    partial = settings.first_page != 1 or len(pages) != total
    manifest = {"document_id": document_id, "source": source, "content_hash": content_hash,
                "preprocessing_version": VERSION, "processed_at": datetime.now(timezone.utc).isoformat(),
                "run_id": digest(content_hash + json.dumps(settings.__dict__, sort_keys=True)
                                 + digest(json.dumps(chunks, ensure_ascii=False, sort_keys=True)))[:24],
                "settings": settings.__dict__, "total_pages": total, "processed_pages": len(pages),
                "partial": partial, "policy_count": len([p for p in policies if p['task_id'] != 'frontmatter']),
                "chunk_count": len(chunks), "review_count": len(reviews) + len(conflicts),
                "supplement_page_count": len(supplements),
                "summary_entry_count": sum(len(s["entries"]) for s in supplements), **context}
    return Result(manifest, pages, policies, chunks, reviews + conflicts, supplements)
