import unittest
from unittest.mock import Mock
from langchain_core.documents import Document
from rag.retrieval.policy_search import RAGRequest, search_policies

class SearchTests(unittest.TestCase):
    def test_empty_index(self):
        result = search_policies(RAGRequest(prompt="월세", source="web"), None)
        self.assertFalse(result.index_available)
        self.assertEqual(result.documents, [])

    def test_retrieval_preserves_metadata_and_distance(self):
        store = Mock()
        store.similarity_search_with_score.return_value = [(Document(page_content="주거 지원", metadata={"source":"p.pdf","page":2}), .2)]
        result = search_policies(RAGRequest(prompt="월세", source="pdf", top_k=1), store)
        self.assertEqual(result.documents[0].metadata["page"], 2)
        self.assertEqual(result.documents[0].distance, .2)
        store.similarity_search_with_score.assert_called_once_with("월세", k=1)
