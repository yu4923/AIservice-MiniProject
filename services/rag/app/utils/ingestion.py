"""Shared preprocessing and ingestion for standalone scripts."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from app.utils.policy_preprocessing import Settings, preprocess_pdf, digest
from app.utils.web_preprocessing import collect_topic

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
DATA_DIR = Path(os.getenv("RAG_PREPROCESS_DIR", str(BASE_DIR / "data" / "preprocessed")))


def _documents(chunks):
    from langchain_core.documents import Document
    return [Document(page_content=c["page_content"], metadata=c["metadata"]) for c in chunks]


def ingest_paper(file_path, source_name=None, *, dry_run=False, output_dir=None, settings=None):
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 허용됩니다.")
    result = preprocess_pdf(path, source_name, settings)
    output = result.save(Path(output_dir) if output_dir else DATA_DIR / "pdf")
    manifest = result.manifest
    store, added = None, 0
    if not dry_run:
        if manifest["partial"]:
            raise ValueError("일부 페이지 적재는 허용하지 않습니다. --dry-run으로 검사하세요.")
        if not result.chunks:
            raise ValueError(f"추출 가능한 텍스트가 없습니다. 검토 보고서: {output}")
        if any("unreadable_page" in p["quality_flags"] for p in result.pages):
            raise ValueError(f"읽지 못한 이미지 페이지가 있습니다. OCR 후 재실행하세요: {output}")
        from app.retrieval.faiss_store import replace_documents
        store, added = replace_documents(_documents(result.chunks), "pdf",
                                         sources={manifest["document_id"]},
                                         source_names={manifest["source"]})
    return store, {"message": "전처리 완료" if dry_run else "전처리·인덱스 갱신 완료",
                   "dry_run": dry_run, "added_chunks": added, "output_dir": str(output),
                   **{k: manifest[k] for k in ("document_id", "processed_pages", "total_pages",
                                              "policy_count", "chunk_count", "review_count", "partial")}}


async def ingest_topic(topic, *, dry_run=False, urls=None, domains=None, limit=20, output_dir=None):
    if not topic.strip():
        raise ValueError("검색어가 비어 있습니다.")
    data = await collect_topic(topic, client_id=os.getenv("NAVER_CLIENT_ID"),
                               client_secret=os.getenv("NAVER_CLIENT_SECRET"), urls=urls,
                               domains=domains, limit=limit)
    root = Path(output_dir) if output_dir else DATA_DIR / "web"
    root.mkdir(parents=True, exist_ok=True)
    for record in data["records"]:
        folder = root / record["source_key"] / record["content_hash"][:24]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "raw.html").write_text(record["raw_html"], encoding="utf-8")
        (folder / "record.json").write_text(json.dumps({k: v for k, v in record.items() if k != "raw_html"},
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    report = root / (digest(topic)[:24] + ".json")
    report.write_text(json.dumps({"topic": topic, "failures": data["failures"], "chunks": data["chunks"],
                                   "records": len(data["records"])}, ensure_ascii=False, indent=2), encoding="utf-8")
    store, added = None, 0
    if data["chunks"] and not dry_run:
        from app.retrieval.faiss_store import replace_documents
        store, added = replace_documents(_documents(data["chunks"]), "web",
                                         sources={r["source_key"] for r in data["records"]},
                                         source_names={r["source"] for r in data["records"]})
    return store, {"message": "공식 웹 본문 전처리 완료", "dry_run": dry_run,
                   "collected": len(data["records"]), "chunk_count": len(data["chunks"]),
                   "added_chunks": added, "failed": len(data["failures"]), "report": str(report),
                   "sample_titles": [r["title"] for r in data["records"][:3]]}
