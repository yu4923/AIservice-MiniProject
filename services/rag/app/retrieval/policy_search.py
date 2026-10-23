"""FAISS retrieval reusable by HTTP routes and future graph nodes."""
from typing import Literal

from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    prompt: str = Field(min_length=1, description="사용자 정보에서 구성한 정책 검색어")
    source: Literal["web", "pdf"]
    top_k: int = Field(default=5, ge=1, le=50)


class RetrievedDocument(BaseModel):
    content: str
    metadata: dict
    distance: float = Field(description="FAISS 원시 거리 값이며 지원 자격 점수가 아닙니다.")


class RetrievalResponse(BaseModel):
    prompt: str
    source: Literal["web", "pdf"]
    documents: list[RetrievedDocument]
    context: str
    index_available: bool


def search_policies(request: RAGRequest, vectorstore) -> RetrievalResponse:
    """Return evidence only; graph nodes will assess it and generate recommendations."""
    documents = []
    if vectorstore is not None:
        seen = set()
        for doc, distance in vectorstore.similarity_search_with_score(request.prompt, k=request.top_k):
            content = (doc.page_content or "").strip()
            if not content or content in seen:
                continue
            seen.add(content)
            documents.append(RetrievedDocument(content=content, metadata=doc.metadata,
                                               distance=float(distance)))
    limit = 12000 if request.source == "pdf" else 4000
    chunks, remaining = [], limit
    for i, document in enumerate(documents, start=1):
        chunk = f"[문서 {i}]\n{document.content}"
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        remaining -= len(chunks[-1])
    return RetrievalResponse(prompt=request.prompt, source=request.source, documents=documents,
                             context="\n\n".join(chunks), index_available=vectorstore is not None)
