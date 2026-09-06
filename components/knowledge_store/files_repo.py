# components/knowledge_store/files_repo.py
"""
T017a: minimal CRUD surface over the `files` table.

Nothing in the app calls these functions yet — the watcher still only knows
how to hand a path to agent_core.py's classify-and-move flow (state.md §7).
Wiring a real writer (backfill on folder-choice, on_created/on_moved/
on_deleted reconciliation) is T020-T022. This module exists now so that work
has a stable, already-reviewed storage API to call into instead of each of
those tasks inventing its own ad hoc SQL.
"""
import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from .db import get_connection

# 1 MiB read chunks -- large enough to be efficient, small enough not to
# balloon memory on a big video/archive file.
_HASH_CHUNK_SIZE = 1024 * 1024


def compute_file_id(path: str) -> str:
    """
    Stable content-hash id for a file on disk (architecture.md §2.1:
    "file_id being a content hash, not a path, is deliberate: it's what lets
    the system say 'this is the same file, it just moved'").

    Uses SHA-256 over the file's bytes, streamed in chunks so this doesn't
    require loading a large file fully into memory. Raises the same
    exceptions os.open/read would (FileNotFoundError, PermissionError, ...)
    -- callers are expected to have already confirmed the path exists, same
    convention as move_and_rename_file's existence check in file_tools.py.

    Known limitation, flagged rather than glossed over: hashing full file
    bytes means two files with identical content but different names/paths
    will collide on the same file_id. That's arguably correct for dedup
    purposes, but worth the owner's awareness before this is relied on by
    the watcher (T020-T022) for "is this the same file that moved" logic --
    a copy (not a move) of an already-indexed file would currently look
    identical to a move at the file_id level. Distinguishing those, if it
    turns out to matter, is a refinement for whichever task first hits it.
    """
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_file(
    file_id: str,
    current_path: str,
    *,
    content_type: str = None,
    category: str = None,
    summary: str = None,
    keywords: str = None,
    checksum: str = None,
    status: str = "active",
) -> None:
    """
    Insert a new row for `file_id`, or update the existing one if a row with
    that file_id already exists (e.g. the file moved/was re-categorized).

    `filename`/`extension`/`size_bytes`/`created_at`/`modified_at` are
    derived from `current_path` via os.stat rather than accepted as
    parameters, so callers can't accidentally pass a filename that doesn't
    match the path they gave. `indexed_at` is always set to "now" on every
    upsert (it records when *this system* last touched the row, not when the
    file itself was created/modified on disk).

    Deliberately uses SQLite's UPSERT (`ON CONFLICT ... DO UPDATE`) rather
    than a manual select-then-insert-or-update, so this is a single atomic
    statement with no read-modify-write race.
    """
    stat = os.stat(current_path)
    filename = os.path.basename(current_path)
    _, ext = os.path.splitext(filename)
    now = _now_iso()

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO files (
                    file_id, current_path, filename, extension, size_bytes,
                    created_at, modified_at, indexed_at, content_type,
                    category, summary, keywords, checksum, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    current_path = excluded.current_path,
                    filename     = excluded.filename,
                    extension    = excluded.extension,
                    size_bytes   = excluded.size_bytes,
                    modified_at  = excluded.modified_at,
                    indexed_at   = excluded.indexed_at,
                    content_type = COALESCE(excluded.content_type, files.content_type),
                    category     = COALESCE(excluded.category, files.category),
                    summary      = COALESCE(excluded.summary, files.summary),
                    keywords     = COALESCE(excluded.keywords, files.keywords),
                    checksum     = COALESCE(excluded.checksum, files.checksum),
                    status       = excluded.status
                """,
                (
                    file_id, current_path, filename, ext, stat.st_size,
                    datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                    datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    now, content_type, category, summary, keywords, checksum, status,
                ),
            )
    finally:
        conn.close()


def get_file_by_id(file_id: str) -> dict | None:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_file_by_path(current_path: str) -> dict | None:
    """
    Look up a file by its live path. Returns the first match if (unexpectedly)
    more than one row shares a path -- that shouldn't normally happen since a
    given filesystem path can only hold one file at a time, but this doesn't
    assume uniqueness is enforced at the schema level.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM files WHERE current_path = ? LIMIT 1", (current_path,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_files(status: str = "active", limit: int = 1000) -> list[dict]:
    """
    Return up to `limit` rows, optionally filtered by status (pass
    status=None for no filter). Ordered by indexed_at descending (most
    recently indexed first) since that's the most generally useful default
    for both debugging and future "recently indexed" UI surfaces.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM files ORDER BY indexed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM files WHERE status = ? ORDER BY indexed_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_status(file_id: str, status: str) -> bool:
    """
    Update just the `status` column for a file (e.g. 'deleted' once the
    watcher's on_deleted handler exists in T021). Returns True if a row was
    actually updated, False if no row with that file_id was found.
    """
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE files SET status = ?, indexed_at = ? WHERE file_id = ?",
                (status, _now_iso(), file_id),
            )
        return cur.rowcount > 0
    finally:
        conn.close()
