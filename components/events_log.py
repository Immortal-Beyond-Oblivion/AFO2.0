# components/events_log.py
"""
T012: minimal append-only `events` log (SQLite), per architecture.md §2.1.

This is intentionally a stripped-down version of the full `events` table
described in architecture.md §2.1 — just enough to close the "no audit
trail" half of state.md §6's safety finding, and to give T013 (undo)
something concrete to reverse. The full knowledge_store module
(`files`/`events`/`user_profile`, FTS5, etc.) is T017+ and will very likely
absorb/extend this file rather than live alongside it forever.

Known limitations, called out explicitly rather than silently glossed over:
- `file_id` is always NULL today. The real design (architecture.md §2.1)
  wants a content-hash `file_id` that survives renames/moves, but that
  requires the `files` table from T017's knowledge_store, which doesn't
  exist yet. Once T017 lands, a migration could backfill `file_id` on
  historical rows by matching `to_path` against `files.current_path` on a
  best-effort basis, but that's out of scope here.
- `reason` and `confidence` are always NULL today too. The agent
  (`agent_core.py`) doesn't currently ask the LLM to report a rationale or a
  confidence score alongside its `move_and_rename_file` tool call, so there
  is nothing to log yet. Wiring that through would mean changing the tool's
  argument schema and the system prompt, which is out of scope for T012 —
  the columns exist now so a future task can start populating them without
  another schema migration.
- This module owns its own tiny SQLite file (`afo_events.db`) rather than
  reusing Chroma's storage in `retriever.py` — they are different kinds of
  stores (relational audit log vs. vector index) and T017's knowledge_store
  is the right place to eventually unify them under one schema, not this
  task.
"""
import os
import sqlite3
from datetime import datetime, timezone

import platformdirs
from constants import APP_NAME, APP_AUTHOR

DATA_DIR = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)
EVENTS_DB_PATH = os.path.join(DATA_DIR, "afo_events.db")

_CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     TEXT,
    event_type  TEXT NOT NULL,
    from_path   TEXT,
    to_path     TEXT,
    actor       TEXT,
    reason      TEXT,
    confidence  REAL,
    timestamp   TEXT NOT NULL
);
"""


def _get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(EVENTS_DB_PATH)
    conn.execute(_CREATE_EVENTS_TABLE)
    return conn


def init_db():
    """Create the events table if it doesn't exist yet. Idempotent — safe to
    call on every app startup (see main.py)."""
    conn = _get_connection()
    conn.close()
    print(f"🗒️  Events log ready at: {EVENTS_DB_PATH}")


def log_event(event_type, from_path=None, to_path=None, actor="agent",
              reason=None, confidence=None, file_id=None):
    """
    Append one row to the `events` table.

    Deliberately swallows its own errors rather than raising: by the time
    this is called the underlying file operation has already happened, so a
    logging failure should never be allowed to look like (or cause) the
    actual move/rename failing. Any DB error is printed so the owner notices
    something is wrong with the events store, but the caller's return value
    to the agent is unaffected.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO events
                    (file_id, event_type, from_path, to_path, actor, reason, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, event_type, from_path, to_path, actor, reason, confidence, timestamp),
            )
        conn.close()
    except Exception as e:
        print(f"⚠️ Could not log event ({event_type}: {from_path} -> {to_path}) to {EVENTS_DB_PATH}: {e}")


def get_last_event():
    """
    T013: Return the most recent row in the `events` table as a dict, or
    None if the table is empty.

    "Most recent" is deliberately determined by highest `event_id`
    (insertion/autoincrement order), not `timestamp` -- event_id is
    monotonic and immune to any clock skew or timestamp formatting
    weirdness, whereas comparing ISO timestamp strings would be a subtly
    riskier way to answer the same question for no real benefit.

    This is read-only and safe to call at any time, including before
    init_db()/log_event() have ever run -- _get_connection() creates the
    table (empty) if it doesn't exist yet, so this just returns None in
    that case rather than raising.
    """
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM events ORDER BY event_id DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
