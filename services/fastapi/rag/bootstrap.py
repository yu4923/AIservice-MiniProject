"""Prepare missing indexes once before serving requests; reuse existing generations."""
import os
from pathlib import Path
import subprocess
import sys


def prepare_indexes():
    from rag.retrieval import faiss_store
    if os.getenv("RAG_BUILD_ON_START", "true").lower() not in {"true", "false"}:
        raise ValueError("RAG_BUILD_ON_START must be true or false")
    if os.getenv("RAG_BUILD_ON_START", "true").lower() == "false":
        return
    kinds = list(dict.fromkeys(k.strip() for k in os.getenv("RAG_REQUIRED_INDEXES", "web").split(",")))
    if not kinds or any(k not in {"web", "pdf"} for k in kinds):
        raise ValueError("RAG_REQUIRED_INDEXES must be web, pdf, or web,pdf")
    root = Path(__file__).resolve().parent
    # This lock covers collection/embedding too, not just publication of a generation.
    with faiss_store._lock(faiss_store.FAISS_DIR / ".bootstrap"):
        for kind in kinds:
            if faiss_store.load_vectorstore(kind) is not None:
                continue
            script = "ingest_topics.py" if kind == "web" else "ingest_papers.py"
            # Batch output may contain private source text or provider errors: do not relay it.
            result = subprocess.run([sys.executable, str(root / "scripts" / script)],
                                    cwd=root.parent, capture_output=True, timeout=3600)
            if result.returncode != 0:
                raise RuntimeError(f"{kind} 자료 적재에 실패했습니다. 입력 자료와 수집 API 설정을 확인하세요.")
            if faiss_store.load_vectorstore(kind) is None:
                raise RuntimeError(f"{kind} 인덱스가 생성되지 않았습니다.")
