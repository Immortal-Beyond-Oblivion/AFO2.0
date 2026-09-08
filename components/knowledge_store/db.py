# components/knowledge_store/db.py
"""
T017a: connection handling + init/migration for the knowledge_store DB.

Storage location follows the same convention already established by
components/retriever.py (afo_vectordb) and components/events_log.py
(afo_events.db): a sibling file under platformdirs' per-user data directory.
This is a *third*, separate SQLite file (`afo_knowledge.db`) rather than
reusing events_log.py's `afo_events.db` — see schema.py's module docstring
for why `events` isn't being merged in here yet (that's T017b).
"""
import os
import sqlite3

import platformdirs
from constants import APP_NAME, APP_AUTHOR

from .schema import ALL_STATEMENTS

DATA_DIR = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)
KNOWLEDGE_DB_PATH = os.path.join(DATA_DIR, "afo_knowledge.db")


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the knowledge store, creating the DB file/tables if
    they don't exist yet. Idempotent and safe to call repeatedly — same
    pattern as events_log.py's _get_connection().

    Callers that need dict-like rows should set
    `conn.row_factory = sqlite3.Row` themselves (not forced here, to keep
    this a plain drop-in connection for callers that just want the default
    tuple rows).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
    for statement in ALL_STATEMENTS:
        conn.execute(statement)
    conn.commit()
    return conn


def init_db():
    """
    Create the `files`, `files_fts`, and `user_profile` tables/triggers if
    they don't exist yet. Idempotent — safe to call on every app startup,
    same convention as events_log.init_db(). Wired into main.py's startup
    sequence as of T017c, since move_and_rename_file is now a real writer.

    T018: also backfills `files_fts` for any `files` rows that predate the
    files_ai_fts/files_au_fts triggers (i.e. rows written by T017c before
    this task added them) — the triggers only fire on new INSERT/UPDATE
    activity going forward, so without this one-time catch-up, a file moved
    in an earlier session would silently never become keyword-searchable.
    Uses INSERT ... SELECT ... WHERE NOT IN, which is a no-op (touches zero
    rows) once every file already has a matching files_fts row, so this is
    cheap to run unconditionally on every call rather than needing its own
    one-time flag.
    """
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO files_fts (file_id, filename, category, summary, keywords)
            SELECT file_id, filename, category, summary, keywords FROM files
            WHERE file_id NOT IN (SELECT file_id FROM files_fts)
            """
        )
    conn.close()
    print(f"🗂️  Knowledge store ready at: {KNOWLEDGE_DB_PATH}")
