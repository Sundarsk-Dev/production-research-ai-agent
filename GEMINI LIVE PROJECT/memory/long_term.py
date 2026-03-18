import os
import json
import numpy as np
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from models.schemas import MemoryChunkInput
from storage import db

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = genai.GenerativeModel("gemini-2.5-flash-lite")
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

_COMPRESS_PROMPT = """Summarize these conversation exchanges into structured JSON.
Return ONLY valid JSON, no markdown, no extra text:
{{
  "main_topics": ["topic1", "topic2"],
  "key_decisions": ["decision1"],
  "open_questions": ["question1"],
  "one_line_summary": "single sentence summary"
}}

Exchanges:
{exchanges}"""


def compress_and_store(exchanges: list[dict], session_id: str,
                       range_start: int, range_end: int) -> str:
    formatted = "\n".join(
        f"[{e['role'].upper()}] {e['content']}" for e in exchanges
    )

    try:
        response = _model.generate_content(
            _COMPRESS_PROMPT.format(exchanges=formatted)
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        chunk_data = MemoryChunkInput(**json.loads(raw.strip()))
    except Exception:
        chunk_data = MemoryChunkInput(
            main_topics=["unknown"],
            key_decisions=[],
            open_questions=[],
            one_line_summary=formatted[:100]
        )

    embedding = _embed(chunk_data.one_line_summary)

    return db.insert_memory_chunk(
        session_id=session_id,
        range_start=range_start,
        range_end=range_end,
        main_topics=chunk_data.main_topics,
        key_decisions=chunk_data.key_decisions,
        open_questions=chunk_data.open_questions,
        summary=chunk_data.one_line_summary,
        embedding=embedding
    )


def _embed(text: str) -> bytes:
    vec = _embedder.encode(text, normalize_embeddings=True)
    return vec.astype(np.float32).tobytes()


def embedding_to_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)