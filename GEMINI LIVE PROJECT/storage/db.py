import sqlite3
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "agent.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


# ── Checksum helpers ──────────────────────────────────────────

def _compute_checksum(payload: str, prev_hash: str) -> str:
    return hashlib.sha256(f"{payload}{prev_hash}".encode()).hexdigest()


def _get_last_hash(conn: sqlite3.Connection, table: str, session_id: str) -> str:
    # Use rowid for insertion order — timestamp can collide at millisecond level
    row = conn.execute(
        f"SELECT checksum FROM {table} WHERE session_id = ? "
        f"ORDER BY rowid DESC LIMIT 1",
        (session_id,)
    ).fetchone()
    return row["checksum"] if row else "GENESIS"


# ── Event log ─────────────────────────────────────────────────

def insert_event(session_id: str, phase: str,
                 event_type: str, payload: dict) -> str:
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    payload_str = json.dumps(payload)

    with get_connection() as conn:
        prev_hash = _get_last_hash(conn, "events", session_id)
        checksum = _compute_checksum(payload_str, prev_hash)
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
            (event_id, session_id, timestamp, phase,
             event_type, payload_str, prev_hash, checksum)
        )
    return event_id


def get_events(session_id: str, phase: str = None) -> list[dict]:
    query = "SELECT * FROM events WHERE session_id = ?"
    params = [session_id]
    if phase:
        query += " AND phase = ?"
        params.append(phase)
    query += " ORDER BY rowid ASC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def verify_event_chain(session_id: str) -> bool:
    events = get_events(session_id)
    if not events:
        return True
    prev = "GENESIS"
    for e in events:
        expected = _compute_checksum(e["payload"], prev)
        if expected != e["checksum"]:
            return False
        prev = e["checksum"]
    return True


# ── Memory chunks ─────────────────────────────────────────────

def insert_memory_chunk(session_id: str, range_start: int, range_end: int,
                        main_topics: list, key_decisions: list,
                        open_questions: list, summary: str,
                        embedding: bytes) -> str:
    chunk_id = f"{session_id}:{range_start}-{range_end}"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO memory_chunks VALUES (?,?,?,?,?,?,?,?,?,1.0,?)",
            (chunk_id, session_id, range_start, range_end,
             json.dumps(main_topics), json.dumps(key_decisions),
             json.dumps(open_questions), summary, embedding,
             datetime.now(timezone.utc).isoformat())
        )
    return chunk_id


def get_memory_chunks(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memory_chunks WHERE session_id = ? "
            "ORDER BY access_score DESC",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_access_score(chunk_id: str, delta: float = 0.1) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE memory_chunks SET access_score = access_score + ? "
            "WHERE chunk_id = ?",
            (delta, chunk_id)
        )


# ── Plan artifacts ────────────────────────────────────────────

def insert_plan(session_id: str, plan: dict) -> str:
    plan_json = json.dumps(plan)
    plan_hash = hashlib.sha256(plan_json.encode()).hexdigest()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO plan_artifacts VALUES (?,?,?,?)",
            (session_id, plan_json, plan_hash,
             datetime.now(timezone.utc).isoformat())
        )
    return plan_hash


def get_plan(session_id: str) -> tuple[dict, str] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT plan_json, plan_hash FROM plan_artifacts "
            "WHERE session_id = ?",
            (session_id,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["plan_json"]), row["plan_hash"]


# ── Audit log ─────────────────────────────────────────────────

def insert_audit(session_id: str, event_type: str, detail: dict) -> str:
    audit_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    detail_str = json.dumps(detail)

    with get_connection() as conn:
        prev_hash = _get_last_hash(conn, "audit_log", session_id)
        checksum = _compute_checksum(detail_str, prev_hash)
        conn.execute(
            "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)",
            (audit_id, session_id, timestamp, event_type,
             detail_str, prev_hash, checksum)
        )
    return audit_id


def get_audit_log(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE session_id = ? "
            "ORDER BY rowid ASC",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]