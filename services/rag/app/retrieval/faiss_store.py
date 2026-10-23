"""Append to the existing local FAISS store, skipping identical source chunks."""
from hashlib import sha256
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

FAISS_DIR = Path(__file__).resolve().parents[4] / "data" / "faiss"


def chunk_id(document):
    identity = "\n".join([
        str(document.metadata.get("source", "")),
        str(document.metadata.get("page", "")),
        document.page_content,
    ])
    return sha256(identity.encode("utf-8")).hexdigest()


def append_documents(documents, kind):
    if kind not in {"web", "pdf"}:
        raise ValueError("Unknown index kind")
    path = FAISS_DIR / kind
    embeddings = OpenAIEmbeddings()
    store = None
    seen = set()
    if (path / "index.faiss").exists() and (path / "index.pkl").exists():
        # Only load this application's trusted local indexes.
        store = FAISS.load_local(str(path), embeddings=embeddings,
                                 allow_dangerous_deserialization=True)
        for doc_id in store.index_to_docstore_id.values():
            document = store.docstore.search(doc_id)
            if not isinstance(document, str):
                seen.add(chunk_id(document))
    new_documents, ids = [], []
    for document in documents:
        identifier = chunk_id(document)
        if identifier not in seen:
            seen.add(identifier)
            new_documents.append(document)
            ids.append(identifier)
    if new_documents:
        if store is None:
            store = FAISS.from_documents(new_documents, embeddings, ids=ids)
        else:
            store.add_documents(new_documents, ids=ids)
        path.mkdir(parents=True, exist_ok=True)
        store.save_local(str(path))
    return store, len(new_documents)
