-- ============================================================
-- AGENT SCHEMA
-- All tables append-only except memory_chunks access_score
-- Checksum chain: each event hashes payload + prev_hash
-- ============================================================

-- Core event log
-- Every state change is an event. State is derived from this.
CREATE TABLE IF NOT EXISTS events (
    id          TEXT    PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    phase       TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    payload     TEXT    NOT NULL,   -- JSON string
    prev_hash   TEXT    NOT NULL,
    checksum    TEXT    NOT NULL
);

-- Long-term memory chunks
-- Written once, access_score updated on retrieval
CREATE TABLE IF NOT EXISTS memory_chunks (
    chunk_id            TEXT    PRIMARY KEY,
    session_id          TEXT    NOT NULL,
    range_start         INTEGER NOT NULL,
    range_end           INTEGER NOT NULL,
    main_topics         TEXT    NOT NULL,   -- JSON array
    key_decisions       TEXT    NOT NULL,   -- JSON array
    open_questions      TEXT    NOT NULL,   -- JSON array
    one_line_summary    TEXT    NOT NULL,
    embedding           BLOB    NOT NULL,   -- numpy array as bytes
    access_score        REAL    NOT NULL    DEFAULT 1.0,
    created_at          TEXT    NOT NULL
);

-- Plan artifacts
-- One row per session. Never updated after insert.
CREATE TABLE IF NOT EXISTS plan_artifacts (
    session_id  TEXT    PRIMARY KEY,
    plan_json   TEXT    NOT NULL,
    plan_hash   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- Audit log
-- Security events only. Separate from operational events.
CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT    PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,   -- DEVIATION | INJECTION | PERMISSION_DENIED | AUTHORIZATION
    detail      TEXT    NOT NULL,   -- JSON string
    prev_hash   TEXT    NOT NULL,
    checksum    TEXT    NOT NULL
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_events_session
    ON events(session_id);

CREATE INDEX IF NOT EXISTS idx_events_phase
    ON events(session_id, phase);

CREATE INDEX IF NOT EXISTS idx_memory_session
    ON memory_chunks(session_id);

CREATE INDEX IF NOT EXISTS idx_audit_session
    ON audit_log(session_id);