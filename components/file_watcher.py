import os
import time
import fnmatch
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .knowledge_store import get_file_by_path, upsert_file, mark_status

# T020: default ignore patterns for OS/editor noise and VCS internals.
# Matched per path-segment (see _is_ignored) via fnmatch, so ".git" ignores
# anything anywhere inside a .git directory tree once watching is
# recursive -- not just a literal top-level file/folder named ".git".
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".DS_Store",
    "~$*",           # Office lock files, e.g. ~$report.docx
    "*.tmp",
    "*.crdownload",  # Chrome in-progress downloads
    "*.part",        # Firefox in-progress downloads
]

# Debounce tuning (T020): how long to wait for a file's size to stop
# changing before treating it as "done being written" and safe to queue.
DEBOUNCE_POLL_INTERVAL = 0.5   # seconds between size checks
DEBOUNCE_STABLE_CHECKS = 2     # consecutive unchanged reads required
DEBOUNCE_MAX_WAIT = 30         # give up waiting after this many seconds and queue anyway


def _is_ignored(path, ignore_patterns):
    """
    Returns True if the file should be skipped: any dotfile (filename
    starting with '.'), or any path segment (a parent directory name or the
    final filename) matching one of ignore_patterns via fnmatch. Checking
    every segment -- not just the filename -- is what makes a single
    ".git" pattern correctly ignore every file inside a .git directory once
    the watcher is recursive, without needing a "*/.git/*" glob.
    """
    filename = os.path.basename(path)
    if filename.startswith("."):
        return True
    for part in os.path.normpath(path).split(os.sep):
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


class NewFileHandler(FileSystemEventHandler):
    """
    A handler for filesystem events that debounces (waits for a new file to
    finish being written) and filters out OS/editor noise before putting a
    file path onto the processing queue, and (T021) reconciles on_moved/
    on_deleted events against the knowledge_store's `files` table so that
    metadata already indexed for a file survives it being moved or deleted
    outside of AFO's own move_and_rename_file tool (e.g. the user
    reorganizing things by hand in Finder).
    """

    def __init__(self, queue, ignore_patterns=None):
        self.queue = queue
        self.ignore_patterns = (
            ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS
        )

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if _is_ignored(path, self.ignore_patterns):
            print(f"🙈 Ignoring noise file: {path}")
            return
        print(f"✅ New file detected: {path}. Waiting for it to finish writing...")
        # Debounce on its own thread so the observer thread (which watchdog
        # needs free to keep dispatching other filesystem events) is never
        # blocked by a large, slow-to-finish download/export.
        threading.Thread(target=self._debounce_and_queue, args=(path,), daemon=True).start()

    def _debounce_and_queue(self, path):
        """
        Polls the file's size until it stops changing for
        DEBOUNCE_STABLE_CHECKS consecutive reads, then adds it to the
        queue. This avoids reading a file (a large download, an
        in-progress export, etc.) before its writer has actually finished,
        which would otherwise cause garbage or partial-file extraction
        downstream. Gives up and queues anyway after DEBOUNCE_MAX_WAIT
        seconds so a file that legitimately never stabilizes in time
        doesn't get stuck in limbo forever.
        """
        start_time = time.monotonic()
        last_size = -1
        stable_count = 0

        while time.monotonic() - start_time < DEBOUNCE_MAX_WAIT:
            try:
                current_size = os.path.getsize(path)
            except OSError:
                # File vanished (renamed away, deleted, or was itself a
                # transient temp file cleaned up by its own writer) before
                # it could stabilize -- nothing to queue.
                print(f"⚠️ File disappeared during debounce, skipping: {path}")
                return

            if current_size == last_size:
                stable_count += 1
                if stable_count >= DEBOUNCE_STABLE_CHECKS:
                    break
            else:
                stable_count = 0
                last_size = current_size

            time.sleep(DEBOUNCE_POLL_INTERVAL)
        else:
            print(f"⏱️ Debounce timed out after {DEBOUNCE_MAX_WAIT}s, queuing anyway: {path}")

        if os.path.exists(path):
            print(f"📥 File stable, adding to queue: {path}")
            self.queue.put(path)

    def on_moved(self, event):
        """
        T021: reconcile a filesystem move/rename against the knowledge
        store's `files` table (architecture.md §2.1) instead of leaving a
        stale row behind at the old path.

        Only reconciles moves for a file already tracked in `files` (i.e.
        get_file_by_path(src_path) finds a row). Untracked moves -- e.g.
        AFO's own move_and_rename_file classifying a brand-new file out of
        the watched root's top level, which never had a `files` row at its
        pre-move location in the first place, since indexing only happens
        at move time (T017c) or during a future backfill (T022) -- are a
        deliberate no-op here rather than being (re-)queued as if new. That
        keeps this task scoped to reconciliation only; T022 is what will
        eventually make "index everything already on disk" happen for
        files that were never routed through move_and_rename_file at all.

        Deliberately does NOT change file_id: file_id is a content hash
        (files_repo.compute_file_id), so a same-content move/rename keeps
        the same file_id by definition -- only current_path (and the
        filename/extension/size_bytes/modified_at/indexed_at columns
        upsert_file derives from it) needs to change. Calling
        upsert_file(existing_file_id, dest_path) reuses the exact same
        UPSERT-by-file_id path T017c already relies on, which is what makes
        this "update the row, don't create a duplicate" rather than a
        second INSERT.
        """
        if event.is_directory:
            return

        src_path = event.src_path
        dest_path = event.dest_path

        # A move into an ignored/noise name (e.g. an editor swapping a real
        # file out to a `~$`-style lock name, or into a dotfile) isn't worth
        # reconciling -- there's nothing useful to file the row under, and
        # if it's genuinely being deleted a following on_deleted will
        # reconcile it properly instead.
        if _is_ignored(dest_path, self.ignore_patterns):
            return

        try:
            existing = get_file_by_path(src_path)
            if existing is None:
                # Not a file the knowledge store knows about yet -- nothing
                # to reconcile. Most common case in practice: AFO's own
                # move_and_rename_file moving a just-created file that never
                # had a `files` row at its original path.
                return
            upsert_file(existing["file_id"], dest_path)
            print(f"🔀 Reconciled tracked file move: {src_path} -> {dest_path}")
        except Exception as e:
            # Same "a knowledge-store write failure must never look like --
            # or cause -- a real problem" convention as file_tools.py's
            # T017c/T019 blocks: reconciliation is a best-effort secondary
            # write path, not something that should ever crash the watcher.
            print(f"Warning: failed to reconcile move in knowledge store ({src_path} -> {dest_path}): {e}")

    def on_deleted(self, event):
        """
        T021: mark a tracked file's `files` row as status='deleted' (the
        same soft-delete convention already used everywhere else in the
        knowledge store, e.g. files_repo.mark_status / schema.py's
        files_ad_fts trigger note) instead of leaving a row that still
        claims to live at a path that no longer exists.
        """
        if event.is_directory:
            return

        path = event.src_path
        if _is_ignored(path, self.ignore_patterns):
            # Noise files (e.g. .DS_Store) get created and deleted
            # constantly and were never tracked in the first place.
            return

        try:
            existing = get_file_by_path(path)
            if existing is None:
                # Untracked file deleted -- nothing to reconcile.
                return
            mark_status(existing["file_id"], "deleted")
            print(f"🗑️  Marked deleted in knowledge store: {path}")
        except Exception as e:
            print(f"Warning: failed to reconcile delete in knowledge store ({path}): {e}")


class Watcher:
    """A class that encapsulates the watchdog observer to allow for clean start/stop."""
    def __init__(self, path_to_watch, queue, ignore_patterns=None):
        self.path_to_watch = path_to_watch
        self.queue = queue
        self.event_handler = NewFileHandler(self.queue, ignore_patterns=ignore_patterns)
        self.observer = Observer()

    def start(self):
        """Starts the file observer, recursively (T020)."""
        if not self.path_to_watch or not os.path.exists(self.path_to_watch):
            print(f"⚠️ Warning or Error: Path '{self.path_to_watch}' does not exist. Watcher not started.")
            return

        # T020: recursive=True so files created in subfolders of the
        # monitored folder are no longer invisible to the watcher (was
        # recursive=False before this task).
        self.observer.schedule(self.event_handler, self.path_to_watch, recursive=True)
        self.observer.start()
        print(f"👀 Watcher started on: {self.path_to_watch} (recursive, debounced, noise-filtered, move/delete-aware)")

        # The observer runs in its own thread, but this thread needs to be kept alive.
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        finally:
            # This part runs when observer.stop() is called from another thread
            self.observer.join()
        print("Watcher thread has finished.")

    def stop(self):
        """Stops the file observer."""
        if self.observer.is_alive():
            self.observer.stop()
            print("🛑 Watcher stop command issued.")
