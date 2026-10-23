"""Shared ingestion used by the existing API and standalone batch scripts."""
import os
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.retrieval.faiss_store import append_documents

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def require_env(name):
    value = os.getenv(name)
    if not value or not value.strip():
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


async def ingest_topic(topic):
    """Keep the existing Naver news search, 20 results, and 500/80 chunking."""
    if not topic.strip():
        raise ValueError("검색어가 비어 있습니다.")
    require_env("OPENAI_API_KEY")
    headers = {
        "X-Naver-Client-Id": require_env("NAVER_CLIENT_ID"),
        "X-Naver-Client-Secret": require_env("NAVER_CLIENT_SECRET"),
    }
    items = []
    want, display, start = 20, 20, 1
    async with aiohttp.ClientSession() as session:
        while len(items) < want:
            params = {"query": topic, "display": display, "start": start, "sort": "date"}
            async with session.get("https://openapi.naver.com/v1/search/news.json",
                                   headers=headers, params=params) as response:
                response.raise_for_status()
                data = await response.json()
            batch = data.get("items", [])
            if not batch:
                break
            for item in batch:
                for field in ("title", "description"):
                    item[field] = unescape(re.sub(r"</?b>", "", item.get(field, "")))
            items.extend(batch)
            start += display
            if start > 1000:
                break
    if not items:
        return None, {"message": "검색 결과가 없습니다.", "collected": 0, "added_chunks": 0}
    texts = [f"title: {it.get('title', '')}\nlink: {it.get('link', '')}\ndesc: {it.get('description', '')}"[:3000]
             for it in items]
    collected_at = datetime.now(timezone.utc).isoformat()
    metadata = [{"source": it.get("link", ""), "title": it.get("title", ""),
                 "topic": topic, "collected_at": collected_at} for it in items]
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    docs = splitter.create_documents(texts, metadatas=metadata)
    store, added = append_documents(docs, "web")
    return store, {"message": f"{added}개의 웹 문서(청크) 추가 저장 완료",
                   "collected": len(items), "added_chunks": added,
                   "sample_titles": [it.get("title", "") for it in items[:3]]}


def ingest_paper(file_path, source_name=None):
    require_env("OPENAI_API_KEY")
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 허용됩니다.")
    reader = PdfReader(path)
    texts, metadata = [], []
    for page, content in enumerate(reader.pages, start=1):
        text = content.extract_text() or ""
        if text.strip():
            texts.append(text)
            metadata.append({"source": source_name or path.name, "page": page})
    paper_text = "\n".join(texts)
    if not paper_text.strip():
        raise ValueError("PDF에서 텍스트를 추출하지 못했습니다. 스캔 PDF라면 OCR이 필요합니다.")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    docs = splitter.create_documents(texts, metadatas=metadata)
    store, added = append_documents(docs, "pdf")
    return store, {"message": f"{added}개의 PDF 청크 추가 저장 완료", "added_chunks": added,
                   "extracted_characters": len(paper_text), "preview": paper_text[:300]}
