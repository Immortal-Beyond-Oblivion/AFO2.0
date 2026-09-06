# components/knowledge_store/__init__.py
"""
T017a: knowledge_store package — the persistent metadata store described in
architecture.md §2.1.

This subtask (T017a, first slice of T017 — see implementation.md) creates the
`files` and `user_profile` tables and a minimal read/write API over `files`.
It deliberately does NOT touch:
  - the `events` table / components/events_log.py (that consolidation is
    T017b, a separate subtask — events_log.py's own `afo_events.db` keeps
    working exactly as it does today; nothing here changes it),
  - `files_fts` (FTS5 virtual table + sync triggers — that's T018),
  - the watcher/ingestion pipeline actually populating `files` on real
    filesystem activity (T020-T022) — this module only provides the storage
    and CRUD surface; nothing calls it yet.

Public API re-exported here for convenience:
    init_db()               -- create tables if missing, idempotent
    compute_file_id(path)   -- stable content-hash id for a file on disk
    upsert_file(...)        -- insert or update a row in `files`
    get_file_by_id(file_id)
    get_file_by_path(path)
    list_files(...)
    mark_status(file_id, status)
"""
from .db import init_db, get_connection, KNOWLEDGE_DB_PATH
from .files_repo import (
    compute_file_id,
    upsert_file,
    get_file_by_id,
    get_file_by_path,
    list_files,
    mark_status,
)

__all__ = [
    "init_db",
    "get_connection",
    "KNOWLEDGE_DB_PATH",
    "compute_file_id",
    "upsert_file",
    "get_file_by_id",
    "get_file_by_path",
    "list_files",
    "mark_status",
]
