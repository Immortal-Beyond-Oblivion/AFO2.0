import os
import time
import fnmatch
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
    A handler for new file events that debounces (waits for the file to
    finish being written) and filters out OS/editor noise before putting a
    file path onto the processing queue.
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
        print(f"👀 Watcher started on: {self.path_to_watch} (recursive, debounced, noise-filtered)")

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
