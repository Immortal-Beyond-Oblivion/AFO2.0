# components/knowledge_store/__init__.py
"""
T017a: knowledge_store package — the persistent metadata store described in
architecture.md §2.1.

This package (T017a, first slice of T017 — see implementation.md) creates
the `files` and `user_profile` tables and a minimal read/write API over
`files`. T017c later wired `upsert_file`/`compute_file_id` into
`move_and_rename_file` as the first real caller. T018 added `files_fts` (an
FTS5 virtual table over `filename`/`category`/`summary`/`keywords`) plus
triggers that keep it in sync automatically on every write to `files` — no
changes needed here since callers still only ever touch `files` directly.
Still not touched by anything in this package:
  - the `events` table / components/events_log.py (that consolidation was
    T017b, which the owner has since decided to SKIP outright — see
    implementation.md — so events_log.py's own `afo_events.db` remains the
    permanent home for events/undo, not a temporary state),
  - the watcher/ingestion pipeline backfilling `files` for pre-existing
    files on disk (T020-T022) — this module only provides the storage and
    CRUD surface; the watcher itself doesn't call it yet, only
    move_and_rename_file does.

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
