"""KURE wiring and ingestion regressions without downloading model weights."""
import asyncio
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.retrieval import faiss_store
from app.utils import ingestion


class LocalTestEmbeddings(Embeddings):
    """Deterministic vectors for exercising real FAISS persistence and queries."""
    def __init__(self):
        self.documents = []
        self.queries = []

    @staticmethod
    def vector(text):
        return [1.0, 0.0] if "주거" in text else [0.0, 1.0]

    def embed_documents(self, texts):
        self.documents.extend(texts)
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return self.vector(text)


class EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        faiss_store._local_embeddings.cache_clear()
        faiss_store._CACHE.clear()
        self.addCleanup(self.env.stop)
        self.addCleanup(faiss_store._local_embeddings.cache_clear)
        self.addCleanup(faiss_store._CACHE.clear)

    def test_default_model_normalizes_documents_and_queries_and_reuses_model(self):
        constructor = Mock(return_value=LocalTestEmbeddings())
        module = types.ModuleType("langchain_huggingface")
        module.HuggingFaceEmbeddings = constructor
        with patch.dict("sys.modules", {"langchain_huggingface": module}):
            first = faiss_store._embeddings()
            self.assertIs(first, faiss_store._embeddings())
        constructor.assert_called_once_with(
            model_name="nlpai-lab/KURE-v1",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True, "batch_size": 8},
            query_encode_kwargs={"normalize_embeddings": True},
        )

    def test_device_and_batch_settings_are_forwarded(self):
        constructor = Mock()
        module = types.ModuleType("langchain_huggingface")
        module.HuggingFaceEmbeddings = constructor
        with patch.dict("sys.modules", {"langchain_huggingface": module}), patch.dict(
            os.environ, {"RAG_EMBEDDING_DEVICE": "cuda", "RAG_EMBEDDING_BATCH_SIZE": "2"}
        ):
            faiss_store._embeddings()
        self.assertEqual(constructor.call_args.kwargs["model_kwargs"], {"device": "cuda"})
        self.assertEqual(constructor.call_args.kwargs["encode_kwargs"]["batch_size"], 2)

    def test_invalid_batch_size_is_rejected(self):
        with patch.dict(os.environ, {"RAG_EMBEDDING_BATCH_SIZE": "0"}):
            with self.assertRaisesRegex(ValueError, "must be positive"):
                faiss_store._embeddings()

    def test_pdf_and_web_store_and_query_share_the_embedder(self):
        embeddings = LocalTestEmbeddings()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            faiss_store, "FAISS_DIR", Path(directory)
        ), patch.object(faiss_store, "_embeddings", return_value=embeddings):
            for kind in ("pdf", "web"):
                with self.subTest(kind=kind):
                    docs = [Document(page_content="청년 주거 지원", metadata={"source_key": "a"}),
                            Document(page_content="청년 취업 지원", metadata={"source_key": "a"})]
                    faiss_store.replace_documents(docs, kind, sources={"a"})
                    store = faiss_store.load_vectorstore(kind)
                    self.assertEqual(store.similarity_search("주거 정책", k=1)[0].page_content,
                                     "청년 주거 지원")
                    pointer = json.loads((Path(directory) / kind / "current.json").read_text())
                    self.assertEqual(pointer["embedding_model"], "nlpai-lab/KURE-v1")
        self.assertEqual(len(embeddings.documents), 4)
        self.assertEqual(embeddings.queries, ["주거 정책", "주거 정책"])

    def test_legacy_index_without_model_metadata_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            faiss_store, "FAISS_DIR", Path(directory)
        ), patch.object(faiss_store, "_embeddings") as embedder:
            path = Path(directory) / "pdf"
            path.mkdir()
            (path / "index.faiss").touch()
            (path / "index.pkl").touch()
            with self.assertRaisesRegex(ValueError, "Embedding model changed"):
                faiss_store.load_vectorstore("pdf")
            with self.assertRaisesRegex(ValueError, "Embedding model changed"):
                faiss_store.replace_documents([Document(page_content="new")], "pdf", sources={"a"})
            embedder.assert_not_called()

    def test_ingestion_does_not_require_openai_key(self):
        chunk = {"page_content": "청년 주거 지원", "metadata": {"source_key": "a"}}
        manifest = {"partial": False, "document_id": "a", "source": "a.pdf",
                    "processed_pages": 1, "total_pages": 1, "policy_count": 1,
                    "chunk_count": 1, "review_count": 0}
        result = Mock(manifest=manifest, chunks=[chunk], pages=[{"quality_flags": []}])
        data = {"records": [{"source_key": "a", "content_hash": "abcdef", "raw_html": "",
                             "source": "https://www.seoul.go.kr/", "title": "공고"}],
                "chunks": [chunk], "failures": []}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            ingestion, "preprocess_pdf", return_value=result
        ), patch.object(ingestion, "collect_topic", return_value=data), patch.object(
            faiss_store, "replace_documents", return_value=(Mock(), 1)
        ) as replace:
            _, pdf_result = ingestion.ingest_paper("a.pdf", output_dir=directory)
            _, web_result = asyncio.run(ingestion.ingest_topic("청년", output_dir=directory))
        self.assertEqual(pdf_result["added_chunks"], 1)
        self.assertEqual(web_result["added_chunks"], 1)
        self.assertEqual([c.args[1] for c in replace.call_args_list], ["pdf", "web"])


if __name__ == "__main__":
    unittest.main()
