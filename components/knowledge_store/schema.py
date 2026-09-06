# components/knowledge_store/schema.py
"""
T017a: SQL DDL for the knowledge_store, per architecture.md §2.1.

Only `files` and `user_profile` are created here. `events` is intentionally
NOT redefined in this module yet — components/events_log.py already owns a
working `events` table (T012/T013, with `undo` already wired against it) in
its own `afo_events.db`. Consolidating `events` into this store (matching the
fuller architecture.md §2.1 shape — populated `file_id`/`reason`/`confidence`
— and repointing file_tools.py/events_log.py's callers at it) is scoped as a
separate subtask (T017b) specifically so this session doesn't risk regressing
the already-owner-tested undo/audit-log feature. `files_fts` (FTS5) is T018.
"""

CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    file_id         TEXT PRIMARY KEY,      -- stable content hash, survives renames/moves
    current_path    TEXT NOT NULL,
    filename        TEXT NOT NULL,
    extension       TEXT,
    size_bytes      INTEGER,
    created_at      TEXT,
    modified_at     TEXT,
    indexed_at      TEXT,
    content_type    TEXT,                  -- text / image / pdf_text / pdf_scanned / office / audio / video
    category        TEXT,                  -- folder AFO filed it under
    summary         TEXT,                  -- short LLM-generated summary, cached
    keywords        TEXT,                  -- extracted/LLM-tagged keywords, comma or JSON
    checksum        TEXT,                  -- for change detection
    status          TEXT NOT NULL DEFAULT 'active'  -- active / moved / deleted / quarantined
);
"""

# One index on current_path: get_file_by_path() (and the future watcher, in
# T020-T022) will look files up by their live filesystem path far more often
# than by file_id, so this is worth the small write-time cost now rather than
# added silently later as a "why is this slow" fix.
CREATE_FILES_PATH_INDEX = """
CREATE INDEX IF NOT EXISTS idx_files_current_path ON files(current_path);
"""

CREATE_USER_PROFILE_TABLE = """
CREATE TABLE IF NOT EXISTS user_profile (
    key             TEXT PRIMARY KEY,      -- e.g. 'top_categories', 'active_hours', 'file_type_affinity'
    value           TEXT,                  -- JSON blob
    updated_at      TEXT
);
"""

ALL_STATEMENTS = [
    CREATE_FILES_TABLE,
    CREATE_FILES_PATH_INDEX,
    CREATE_USER_PROFILE_TABLE,
]
