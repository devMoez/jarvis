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


def store(fact: str) -> str:
    """Store a fact in long-term memory."""
    try:
        col = _get_collection()
        import uuid
        doc_id = str(uuid.uuid4())
        col.add(documents=[fact], ids=[doc_id])
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


def remember(fact: str) -> str:
    """Tool-callable wrapper for store()."""
    return store(fact)
