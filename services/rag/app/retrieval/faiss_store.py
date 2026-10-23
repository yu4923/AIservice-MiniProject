"""Source replacement with immutable generations and an atomic active pointer.

Only trusted local FAISS files may be loaded (LangChain's pickle metadata).
The writer lock is shared by batch processes on this host. No external API call
is made when callers pass an Embeddings implementation (offline tests).
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import uuid

FAISS_DIR = Path(os.getenv("RAG_FAISS_DIR", str(Path(__file__).resolve().parents[4] / "data" / "faiss")))
_CACHE = {}


def chunk_id(document):
    identity = "\n".join([str(document.metadata.get("source", "")),
                           str(document.metadata.get("page", "")), document.page_content])
    return sha256(identity.encode("utf-8")).hexdigest()


def _embeddings():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(model=os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"))


def _path(kind):
    if kind not in {"web", "pdf"}:
        raise ValueError("Unknown index kind")
    return FAISS_DIR / kind


@contextmanager
def _lock(path):
    path.mkdir(parents=True, exist_ok=True)
    with (path / ".writer.lock").open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.seek(0); f.write(b"0"); f.flush(); f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def _active(path):
    pointer = path / "current.json"
    if pointer.exists():
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        generation = meta["generation"]
        if not isinstance(generation, str) or not generation.isalnum():
            raise ValueError("Invalid local index generation")
        active = path / "generations" / generation
        if not (active / "index.faiss").is_file() or not (active / "index.pkl").is_file():
            raise RuntimeError("Active FAISS generation is incomplete")
        return active, meta
    if (path / "index.faiss").is_file() and (path / "index.pkl").is_file():
        return path, {"generation": "legacy", "embedding_model": None}
    return None, None


def load_vectorstore(kind, *, embeddings=None):
    from langchain_community.vectorstores import FAISS
    root = _path(kind)
    active, meta = _active(root)
    if active is None:
        return None
    model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    if embeddings is None and meta.get("embedding_model") not in (None, model):
        raise ValueError("Embedding model changed; rebuild the index in a new RAG_FAISS_DIR")
    signature = (str(active), (active / "index.faiss").stat().st_mtime_ns,
                 (active / "index.pkl").stat().st_mtime_ns, model)
    if embeddings is None and _CACHE.get(kind, (None,))[0] == signature:
        return _CACHE[kind][1]
    store = FAISS.load_local(str(active), embeddings=embeddings or _embeddings(),
                             allow_dangerous_deserialization=True)
    if embeddings is None:
        _CACHE[kind] = (signature, store)
    return store


def _update(documents, kind, sources=None, source_names=None, embeddings=None):
    from langchain_community.vectorstores import FAISS
    root = _path(kind)
    sources, source_names = set(sources or ()), set(source_names or ())
    incoming = {chunk_id(d): d for d in documents}
    if not incoming:
        raise ValueError("Empty input cannot replace a source index")
    with _lock(root):
        _, old_meta = _active(root)
        model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        if embeddings is None and old_meta and old_meta.get("embedding_model") not in (None, model):
            raise ValueError("Embedding model changed; choose a new index directory")
        embedding = embeddings or _embeddings()
        store = load_vectorstore(kind, embeddings=embedding)
        old = {} if store is None else {
            identifier: store.docstore.search(identifier) for identifier in store.index_to_docstore_id.values()}
        removed, existing_signatures = [], set()
        for identifier, doc in old.items():
            if isinstance(doc, str):
                continue
            if doc.metadata.get("source_key") in sources or doc.metadata.get("source") in source_names:
                removed.append(identifier)
                existing_signatures.add(chunk_id(doc))
        if removed and existing_signatures == set(incoming):
            return store, 0
        if removed:
            # Mutating the cached reader would expose an unpublished generation.
            active, _ = _active(root)
            store = FAISS.load_local(str(active), embeddings=embedding,
                                     allow_dangerous_deserialization=True)
            store.delete(removed)
        remaining = set() if store is None else set(store.index_to_docstore_id.values())
        new_ids = [identifier for identifier in incoming if identifier not in remaining]
        if not new_ids and not removed:
            return store, 0
        if new_ids:
            docs = [incoming[i] for i in new_ids]
            if store is None or store.index.ntotal == 0:
                store = FAISS.from_documents(docs, embedding, ids=new_ids)
            else:
                store.add_documents(docs, ids=new_ids)
        generation = uuid.uuid4().hex
        target = root / "generations" / generation
        target.mkdir(parents=True)
        try:
            store.save_local(str(target))
            _, old_meta = _active(root)
            model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
            # Preserve/validate the known model even when an injected embedder is used.
            if embeddings is None and old_meta and old_meta.get("embedding_model") not in (None, model):
                raise ValueError("Embedding model changed; choose a new index directory")
            pointer = {"generation": generation, "embedding_model": model,
                       "chunks": store.index.ntotal}
            temporary = root / ("current." + generation + ".tmp")
            with temporary.open("w", encoding="utf-8") as f:
                json.dump(pointer, f); f.flush(); os.fsync(f.fileno())
            temporary.replace(root / "current.json")
        except Exception:
            shutil.rmtree(target)
            raise
        _CACHE.pop(kind, None)
        return store, len(new_ids)


def replace_documents(documents, kind, *, sources, source_names=None, embeddings=None):
    """Replace only successfully collected sources; preserve unrelated/failed sources."""
    return _update(documents, kind, sources, source_names, embeddings)


def append_documents(documents, kind):
    """Compatibility entry point for existing callers."""
    return _update(documents, kind)
