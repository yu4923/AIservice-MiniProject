# This practice code is intended for educational purposes only.
"""RAG retrieval API. Recommendation generation belongs to the future graph."""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.retrieval.policy_search import RAGRequest, RetrievalResponse, search_policies

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Read RAG_FAISS_DIR after loading .env, using the same loader as ingestion.
from app.retrieval.faiss_store import load_vectorstore

app = FastAPI(title="청년정책 RAG 검색 API", description="FAISS 정책 검색 근거 반환", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174", "http://[::1]:5174",
                   "http://localhost:8001", "*"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)


@app.post("/rag-query", response_model=RetrievalResponse, summary="정책 근거 검색", tags=["검색"])
def rag_query(request: RAGRequest):
    try:
        store = load_vectorstore(request.source)
    except Exception:
        raise HTTPException(status_code=503, detail="정책 인덱스를 불러올 수 없습니다.") from None
    try:
        return search_policies(request, store)
    except Exception:
        raise HTTPException(status_code=500, detail="정책 검색에 실패했습니다.") from None


# python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
