# app_tray.py (Final version with live folder changing)
import pystray
from PIL import Image
from tkinter import filedialog, Tk
import threading
from queue import Queue
import time
import os
import sys
import subprocess

from components.config_manager import load_settings, save_settings
from components.file_watcher import Watcher
from components.agent_core import process_file_with_agent


def ask_for_folder():
    """
    Shows a folder selection dialog in a separate process to avoid
    tkinter threading issues, especially on macOS.
    """
    # This script creates a hidden tkinter root window, brings the dialog
    # to the front, and prints the selected path to standard output.
    script = (
        "import tkinter as tk;"
        "from tkinter import filedialog;"
        "root = tk.Tk();"
        "root.withdraw();"
        "root.call('wm', 'attributes', '.', '-topmost', True);"
        "folder_path = filedialog.askdirectory(title='Select a Folder to Monitor');"
        "print(folder_path);"
    )
    try:
        # Run the script using the same python interpreter that is running this app
        process = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, check=False
        )
        # Return the path printed by the script, stripping any whitespace
        if process.returncode == 0 and process.stdout.strip():
            return process.stdout.strip()
        else:
            print(f"Folder dialog was cancelled or failed. Error: {process.stderr.strip()}")
            return None
    except Exception as e:
        print(f"Failed to launch folder dialog subprocess: {e}")
        return None
    


def agent_worker(queue):
    """The real agent worker that calls the agent core for each file."""
    print("✅ Real Agent worker thread started.")
    while True:
        file_path = queue.get()
        if file_path is None: break
        
        # Call the function from our agent_core
        process_file_with_agent(file_path)

        queue.task_done()
    print("Agent worker thread stopped cleanly.")


class MilfoApp:
    def __init__(self):
        self.settings = load_settings()
        self.monitored_path = self.settings.get("monitored_path")
        
        self.file_queue = Queue()
        self.watcher = None
        self.watcher_thread = None

        # Setup the pystray icon and menu
        image = Image.open("icon.png")
        menu = pystray.Menu(
            pystray.MenuItem('Choose Monitored Folder...', self.on_choose_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', self.on_quit)
        )
        self.icon = pystray.Icon("MILFO", image, "MILFO File Organizer", menu)

    def start_watcher_thread(self):
        """Creates and starts a new watcher thread."""
        if self.monitored_path:
            self.watcher = Watcher(self.monitored_path, self.file_queue)
            self.watcher_thread = threading.Thread(target=self.watcher.start, daemon=True)
            self.watcher_thread.start()
            print(f"--> Watcher thread started for {self.monitored_path}")

    def stop_watcher_thread(self):
        """Stops the current watcher thread if it is running."""
        if self.watcher and self.watcher_thread and self.watcher_thread.is_alive():
            self.watcher.stop()
            self.watcher_thread.join(timeout=2) # Wait for the thread to die
            print("<-- Watcher thread stopped.")

    def on_choose_folder(self, icon, item):
        """Callback for the 'Choose Folder' menu item."""
        new_path = ask_for_folder()
        
        if new_path and new_path != self.monitored_path:
            print(f"Changing monitored folder to: {new_path}")
            
            # 1. Stop the current watcher
            self.stop_watcher_thread()
            
            # 2. Update and save the path
            self.monitored_path = new_path
            self.settings["monitored_path"] = new_path
            save_settings(self.settings)
            
            # 3. Start a new watcher with the new path
            self.start_watcher_thread()
            
            self.icon.notify(f"Now watching: {os.path.basename(new_path)}", title="MILFO")

    def on_quit(self, icon, item):
        """Callback for the 'Quit' menu item."""
        print("Quit command received. Shutting down...")
        self.stop_watcher_thread()
        self.file_queue.put(None) # Signal agent to stop
        self.icon.stop()

    def run(self):
        """Starts the application."""
        # Start the initial watcher thread
        self.start_watcher_thread()

        # Start the agent worker thread
        # NOTE: For this test, we are using a dummy agent.
        # Replace `dummy_agent_worker` with the real one when ready.
        agent_thread = threading.Thread(target =agent_worker, args=(self.file_queue,), daemon=True)
        agent_thread.start()

        print("🚀 MILFO is running in the system tray.")
        self.icon.run()


# --- Dummy Agent for Testing ---
# def dummy_agent_worker(queue):
#     print("Agent worker thread started.")
#     while True:
#         file_path = queue.get()
#         if file_path is None: break
#         print(f"--- DUMMY AGENT: Would process '{os.path.basename(file_path)}' ---")
#         time.sleep(5)
#         queue.task_done()
#     print("Agent worker thread stopped cleanly.")

# --- Main Execution ---
def create_tray_icon():
    app = MilfoApp()
    app.run()