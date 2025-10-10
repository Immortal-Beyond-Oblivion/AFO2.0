import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class NewFileHandler(FileSystemEventHandler):
    """A handler for new file events that puts file paths onto a queue."""
    def __init__(self, queue):
        self.queue = queue

    def on_created(self, event):
        if not event.is_directory:
            print(f"✅ New file detected: {event.src_path}. Adding to queue.")
            self.queue.put(event.src_path)

class Watcher:
    """A class that encapsulates the watchdog observer to allow for clean start/stop."""
    def __init__(self, path_to_watch, queue):
        self.path_to_watch = path_to_watch
        self.queue = queue
        self.event_handler = NewFileHandler(self.queue)
        self.observer = Observer()

    def start(self):
        """Starts the file observer."""
        if not self.path_to_watch or not os.path.exists(self.path_to_watch):
            print(f"⚠️ Warning or Error: Path '{self.path_to_watch}' does not exist. Watcher not started.")
            return

        self.observer.schedule(self.event_handler, self.path_to_watch, recursive=False)
        self.observer.start()
        print(f"👀 Watcher started on: {self.path_to_watch}")
        
        # The observer runs in its own thread, but this thread needs to be kept alive.
        # We'll join it here, and the stop() method will break this loop.
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