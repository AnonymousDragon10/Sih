"""
Thin SQLite wrapper for MediKiosk.

Design note: this is a KIOSK SESSION store, not a permanent EMR.
Per the "session termination" requirement in the problem statement,
a session's raw transcript/document blobs are deleted once the
structured summary has been pushed to the HIS stub (see
consult.py -> POST /consult/{session_id}/finalize). Only the final
structured summary + audit trail survive.
"""
import sqlite3
import os
import json
import uuid
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("DATABASE_PATH", "./medikiosk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT,
    status TEXT,                 -- identify | converse | scan | summarized | finalized
    patient_name TEXT,
    age INTEGER,
    sex TEXT,
    preferred_language TEXT,
    department TEXT,             -- allopathic | ayush
    abha_id TEXT,                -- mocked
    consent_json TEXT,
    red_flag INTEGER DEFAULT 0,
    red_flag_reason TEXT
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    turn_index INTEGER,
    role TEXT,                   -- system | patient | assistant
    input_mode TEXT,             -- voice | touch
    text TEXT,
    created_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    filename TEXT,
    doc_type TEXT,                -- prescription | lab_report | discharge_summary | other
    raw_ocr_text TEXT,
    extracted_json TEXT,          -- structured entities
    low_confidence_fields TEXT,   -- JSON list, flagged for physician review
    uploaded_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    summary_json TEXT,
    physician_edited_json TEXT,
    status TEXT,                  -- draft | accepted | amended | rejected
    created_at TEXT,
    finalized_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    event TEXT,
    detail TEXT,
    created_at TEXT
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> str:
    return datetime.utcnow().isoformat()


def audit(session_id: str, event: str, detail: dict | None = None):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (id, session_id, event, detail, created_at) VALUES (?,?,?,?,?)",
            (new_id(), session_id, event, json.dumps(detail or {}), now()),
        )
