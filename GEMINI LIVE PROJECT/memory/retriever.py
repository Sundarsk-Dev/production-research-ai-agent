import json
import math
import numpy as np
from sentence_transformers import SentenceTransformer
from memory.long_term import embedding_to_array
from storage import db

_embedder = SentenceTransformer("all-MiniLM-L6-v2")

TOP_K = 3
DECAY_FACTOR = 0.05   # score penalty per day since creation


def search_memory(query: str, session_id: str) -> list[dict]:
    """
    Three-stage retrieval:
      1. Keyword match on main_topics and key_decisions
      2. Embedding cosine similarity on one_line_summary
      3. Re-rank by decayed access_score

    Returns top-k chunks as dicts ready for context injection.
    """
    chunks = db.get_memory_chunks(session_id)
    if not chunks:
        return []

    query_vec = _embed(query)
    scored = []

    for chunk in chunks:
        keyword_score = _keyword_score(query, chunk)
        semantic_score = _cosine(query_vec, embedding_to_array(chunk["embedding"]))
        decay = _decay_score(chunk["created_at"], chunk["access_score"])

        final_score = (0.3 * keyword_score) + (0.5 * semantic_score) + (0.2 * decay)
        scored.append((final_score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:TOP_K]

    # Update access scores for retrieved chunks
    for _, chunk in top:
        db.update_access_score(chunk["chunk_id"], delta=0.1)

    return [_format(chunk) for _, chunk in top]


# ── Scoring helpers ───────────────────────────────────────────

def _keyword_score(query: str, chunk: dict) -> float:
    query_words = set(query.lower().split())
    topics = set(w.lower() for w in json.loads(chunk["main_topics"]))
    decisions = set(w.lower() for w in json.loads(chunk["key_decisions"]))
    combined = topics | decisions
    if not combined:
        return 0.0
    matches = query_words & combined
    return len(matches) / len(query_words) if query_words else 0.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    dot = float(np.dot(a, b))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return dot / norm if norm > 0 else 0.0


def _decay_score(created_at: str, access_score: float) -> float:
    from datetime import datetime, timezone
    try:
        created = datetime.fromisoformat(created_at)
        now = datetime.now(timezone.utc)
        days_old = (now - created).days
        decayed = access_score * math.exp(-DECAY_FACTOR * days_old)
        return min(decayed, 1.0)
    except Exception:
        return access_score


def _embed(text: str) -> np.ndarray:
    return _embedder.encode(text, normalize_embeddings=True).astype(np.float32)


def _format(chunk: dict) -> dict:
    return {
        "chunk_id": chunk["chunk_id"],
        "summary": chunk["one_line_summary"],
        "main_topics": json.loads(chunk["main_topics"]),
        "key_decisions": json.loads(chunk["key_decisions"]),
        "open_questions": json.loads(chunk["open_questions"]),
        "range": f"{chunk['range_start']}-{chunk['range_end']}"
    }