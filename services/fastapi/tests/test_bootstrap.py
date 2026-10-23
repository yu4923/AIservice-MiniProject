import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch, Mock
from rag.bootstrap import prepare_indexes

class BootstrapTests(unittest.TestCase):
    def test_disabled_does_not_load_or_collect(self):
        with patch.dict(os.environ, {'RAG_BUILD_ON_START':'false'}), patch('rag.retrieval.faiss_store.load_vectorstore') as load:
            prepare_indexes()
            load.assert_not_called()

    def test_existing_index_skips_ingestion(self):
        with patch.dict(os.environ, {'RAG_BUILD_ON_START':'true','RAG_REQUIRED_INDEXES':'web'}), patch('rag.retrieval.faiss_store._lock', return_value=nullcontext()), patch('rag.retrieval.faiss_store.load_vectorstore', return_value=object()), patch('rag.bootstrap.subprocess.run') as run:
            prepare_indexes()
            run.assert_not_called()

    def test_missing_index_is_built_and_checked(self):
        with patch.dict(os.environ, {'RAG_BUILD_ON_START':'true','RAG_REQUIRED_INDEXES':'pdf'}), patch('rag.retrieval.faiss_store._lock', return_value=nullcontext()), patch('rag.retrieval.faiss_store.load_vectorstore', side_effect=[None,object()]), patch('rag.bootstrap.subprocess.run', return_value=Mock(returncode=0)) as run:
            prepare_indexes()
            self.assertIn('ingest_papers.py', run.call_args.args[0][1])

    def test_ingestion_failure_stops_startup(self):
        with patch.dict(os.environ, {'RAG_BUILD_ON_START':'true','RAG_REQUIRED_INDEXES':'web'}), patch('rag.retrieval.faiss_store._lock', return_value=nullcontext()), patch('rag.retrieval.faiss_store.load_vectorstore', return_value=None), patch('rag.bootstrap.subprocess.run', return_value=Mock(returncode=1)):
            with self.assertRaises(RuntimeError): prepare_indexes()
