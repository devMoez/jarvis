import uuid
import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_DB_PATH, EMBEDDING_MODEL, MAX_LONG_TERM_RESULTS

_client: chromadb.Client | None = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        _collection = _client.get_or_create_collection(
            name="jarvis_memory",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def store(fact: str, source: str = "auto") -> str:
    """
    Store a fact in long-term memory.
    source = 'auto' (learned) | 'manual' (user-added via /memory add)
    """
    try:
        col = _get_collection()
        doc_id = str(uuid.uuid4())
        col.add(documents=[fact], ids=[doc_id], metadatas=[{"source": source}])
        return f"Remembered: {fact}"
    except Exception as e:
        return f"Memory store failed: {e}"


def retrieve(query: str) -> str:
    """Retrieve relevant memories for a query. Returns formatted string."""
    try:
        col = _get_collection()
        count = col.count()
        if count == 0:
            return ""
        results = col.query(
            query_texts=[query],
            n_results=min(MAX_LONG_TERM_RESULTS, count),
        )
        docs = results.get("documents", [[]])[0]
        if not docs:
            return ""
        return "\n".join(f"- {d}" for d in docs)
    except Exception as e:
        return ""


def get_all() -> list[dict]:
    """Return all memories as list of {id, doc, source}."""
    try:
        col = _get_collection()
        if col.count() == 0:
            return []
        results = col.get(include=["documents", "metadatas"])
        ids   = results.get("ids", [])
        docs  = results.get("documents", [])
        metas = results.get("metadatas", [])
        out = []
        for i, (doc_id, doc) in enumerate(zip(ids, docs)):
            meta = metas[i] if i < len(metas) else {}
            out.append({"id": doc_id, "doc": doc, "source": meta.get("source", "auto")})
        return out
    except Exception:
        return []


def delete_by_index(idx: int) -> tuple[bool, str]:
    """
    Delete a memory by display index (0-based).
    Auto memories are protected — only manual ones can be deleted.
    """
    entries = get_all()
    if idx < 0 or idx >= len(entries):
        return False, "not_found"
    entry = entries[idx]
    if entry["source"] == "auto":
        return False, "protected"
    try:
        col = _get_collection()
        col.delete(ids=[entry["id"]])
        return True, "ok"
    except Exception as e:
        return False, str(e)


def clear_manual() -> int:
    """Delete only manually-added memories. Auto memories are preserved."""
    entries = get_all()
    manual_ids = [e["id"] for e in entries if e["source"] == "manual"]
    if manual_ids:
        col = _get_collection()
        col.delete(ids=manual_ids)
    return len(manual_ids)


def remember(fact: str) -> str:
    """Tool-callable wrapper — Jarvis uses this, marks source as auto."""
    return store(fact, source="auto")
