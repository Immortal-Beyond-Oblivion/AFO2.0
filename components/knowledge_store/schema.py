# components/knowledge_store/schema.py
"""
T017a: SQL DDL for the knowledge_store, per architecture.md §2.1.

Only `files` and `user_profile` are created here. `events` is intentionally
NOT redefined in this module yet — components/events_log.py already owns a
working `events` table (T012/T013, with `undo` already wired against it) in
its own `afo_events.db`. Consolidating `events` into this store (matching the
fuller architecture.md §2.1 shape — populated `file_id`/`reason`/`confidence`
— and repointing file_tools.py/events_log.py's callers at it) was scoped as a
separate subtask, T017b, which the owner has since decided to SKIP outright
(duplicate work over the already-shipped, already-tested undo/audit feature)
rather than merely defer — see implementation.md's T017b entry and state.md's
T017c session log for the reasoning. `events`/undo continue to live solely in
components/events_log.py's own afo_events.db, indefinitely.

T018 (this addition): `files_fts`, an FTS5 virtual table indexing the
searchable text columns of `files` (`filename`, `category`, `summary`,
`keywords`), plus three triggers (`files_ai_fts` / `files_au_fts` /
`files_ad_fts`) that keep it in sync automatically on every INSERT/UPDATE/
DELETE against `files`. Callers (T017c's `upsert_file`, `mark_status`, and
any future writer such as T020-T022's watcher) don't need to know
`files_fts` exists at all — the triggers do the work, the same way a
database-level invariant should. `file_id` is included as an UNINDEXED
column purely so a trigger/query can identify which `files_fts` row
corresponds to which `files` row (to delete/replace it on update or
delete) — it's not meant to be full-text-searched itself, just carried
alongside the indexed columns as a join key. No query/search function is
added yet (that's T025, "keyword candidate generator via files_fts") — this
task is scoped to just the table + triggers, so it doesn't quietly reach
into retrieval work that isn't scheduled until Phase 2.
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

# --- T018: files_fts (FTS5) + sync triggers -------------------------------

CREATE_FILES_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    file_id UNINDEXED,
    filename,
    category,
    summary,
    keywords
);
"""

# AFTER INSERT: every new `files` row gets a matching `files_fts` row.
CREATE_FILES_FTS_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS files_ai_fts AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(file_id, filename, category, summary, keywords)
    VALUES (new.file_id, new.filename, new.category, new.summary, new.keywords);
END;
"""

# AFTER UPDATE: delete-then-reinsert rather than an in-place FTS5 UPDATE --
# simpler and avoids needing a rowid-tracking scheme, at the cost of a
# slightly larger write; `files` updates are not a hot path (one per file
# move/re-categorization), so this trade-off is fine.
CREATE_FILES_FTS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS files_au_fts AFTER UPDATE ON files BEGIN
    DELETE FROM files_fts WHERE file_id = old.file_id;
    INSERT INTO files_fts(file_id, filename, category, summary, keywords)
    VALUES (new.file_id, new.filename, new.category, new.summary, new.keywords);
END;
"""

# AFTER DELETE: keep files_fts from accumulating orphaned rows. Note that
# today nothing in the app actually issues a hard DELETE against `files`
# (mark_status sets status='deleted' instead, per architecture.md's soft-
# delete convention) -- this trigger exists so files_fts stays correct if/
# when something ever does, rather than silently drifting.
CREATE_FILES_FTS_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS files_ad_fts AFTER DELETE ON files BEGIN
    DELETE FROM files_fts WHERE file_id = old.file_id;
END;
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
    CREATE_FILES_FTS_TABLE,
    CREATE_FILES_FTS_INSERT_TRIGGER,
    CREATE_FILES_FTS_UPDATE_TRIGGER,
    CREATE_FILES_FTS_DELETE_TRIGGER,
    CREATE_USER_PROFILE_TABLE,
]
