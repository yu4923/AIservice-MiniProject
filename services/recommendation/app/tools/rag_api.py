"""RAG 서버의 검색 결과를 받아오는 클라이언트입니다. Vector DB를 직접 열지 않습니다."""

import asyncio
import os
from itertools import zip_longest
from urllib.parse import urlsplit
from typing import Any, Literal

import httpx
from langchain_core.documents import Document
from pydantic import BaseModel, Field


# [RAG 담당자와 맞추는 응답 DTO]
# services/rag의 POST /rag-query 규격을 따릅니다. 다른 서비스 코드를 import하지 않습니다.
class RetrievedDocument(BaseModel):
    content: str
    metadata: dict[str, Any]
    distance: float = Field(allow_inf_nan=False)


class RetrievalResponse(BaseModel):
    prompt: str
    source: Literal["web", "pdf"]
    documents: list[RetrievedDocument]
    context: str
    index_available: bool


class RAGApiRetriever:
    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 15,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = (base_url or os.getenv("RAG_API_URL", "http://127.0.0.1:8001")).rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("RAG_API_URL에는 인증정보·쿼리가 없는 HTTP(S) 서버 주소를 설정하세요.")
        if parsed.path.rstrip("/").endswith(("/rag-query", "/recommend")):
            raise ValueError("RAG_API_URL에는 API 경로가 아닌 서버 주소만 입력하세요.")
        self.timeout_seconds = timeout_seconds
        # 테스트에서 가짜 HTTP 서버를 넣는 자리입니다. 실제 서버에서는 생략합니다.
        self.transport = transport

    async def search(self, query: str, source: str, top_k: int) -> list[Document]:
        if source not in {"pdf", "web", "all"} or not 1 <= top_k <= 20:
            raise ValueError("검색 대상과 top_k를 확인하세요.")
        sources = ["pdf", "web"] if source == "all" else [source]
        async with httpx.AsyncClient(timeout=self.timeout_seconds,
                                     transport=self.transport) as client:
            async def fetch(kind):
                # [복원 시 변경] 예전에는 로컬 FAISS를 직접 읽었습니다.
                # 현재는 데이터 담당자의 RAG 서버에 검색만 요청합니다.
                # profile 전체를 보내지 않고, Graph가 만든 검색어를 prompt로 보냅니다.
                response = await client.post(
                    self.base_url + "/rag-query",
                    json={"prompt": query, "source": kind, "top_k": top_k},
                )
                response.raise_for_status()
                payload = RetrievalResponse.model_validate(response.json())
                if payload.source != kind:
                    raise ValueError("요청한 인덱스와 검색 결과의 인덱스가 다릅니다.")
                if not payload.index_available:
                    return []
                return [
                    Document(page_content=item.content,
                             metadata={**item.metadata, "retrieval_distance": item.distance,
                                       "retrieval_source": kind})
                    for item in payload.documents[:top_k] if item.content.strip()
                ]

            batches = await asyncio.gather(*(fetch(kind) for kind in sources))

        # [all 검색] PDF와 웹 인덱스를 동시에 조회하고 번갈아 후보를 넣습니다.
        # 서로 다른 인덱스의 FAISS 거리를 '자격 점수 0.8'처럼 비교하지 않습니다.
        # 여기서 web은 이미 수집된 웹 문서 인덱스이며, 실시간 웹 검색이 아닙니다.
        result, seen = [], set()
        for row in zip_longest(*batches):
            for doc in row:
                if doc is None:
                    continue
                key = (doc.page_content, str(doc.metadata.get("source", doc.metadata.get("url", ""))))
                if key not in seen:
                    seen.add(key)
                    result.append(doc)
        return result[:top_k]
