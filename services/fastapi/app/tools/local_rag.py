"""Async Graph adapter for internal FAISS retrieval; no HTTP or JWT forwarding."""
import asyncio
from itertools import zip_longest

from langchain_core.documents import Document
from rag.retrieval.faiss_store import load_vectorstore
from rag.retrieval.policy_search import RAGRequest, search_policies


class LocalRAGRetriever:
    @staticmethod
    def _search(query, source, top_k):
        batches = []
        for kind in (["pdf", "web"] if source == "all" else [source]):
            result = search_policies(RAGRequest(prompt=query, source=kind, top_k=top_k),
                                     load_vectorstore(kind))
            batches.append([Document(page_content=d.content,
                metadata={**d.metadata, "retrieval_distance": d.distance, "retrieval_source": kind})
                for d in result.documents])
        docs, seen = [], set()
        for row in zip_longest(*batches):
            for doc in row:
                if doc is None:
                    continue
                key = (doc.page_content, str(doc.metadata.get("source", doc.metadata.get("url", ""))))
                if key not in seen:
                    seen.add(key)
                    docs.append(doc)
        return docs[:top_k]

    async def search(self, query: str, source: str, top_k: int) -> list[Document]:
        if source not in {"web", "pdf", "all"} or not 1 <= top_k <= 20:
            raise ValueError("검색 대상과 top_k를 확인하세요.")
        return await asyncio.to_thread(self._search, query, source, top_k)
