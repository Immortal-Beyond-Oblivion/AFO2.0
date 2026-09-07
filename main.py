from app_tray import create_tray_icon
from components.events_log import init_db
from components.knowledge_store import init_db as init_knowledge_db

if __name__ == "__main__":
    print("Starting AFO application...")
    # T012: make sure the events (audit log) table exists before anything
    # tries to write to it. Idempotent - safe on every startup.
    init_db()
    # T017c: knowledge_store now has a real writer (move_and_rename_file in
    # file_tools.py), so make sure its tables exist up front too, same
    # belt-and-suspenders reasoning as the events init_db() call above.
    # get_connection() would also lazily create these on first write
    # regardless -- this just guarantees it (and prints the ready message)
    # before the tray/watcher starts.
    init_knowledge_db()
    create_tray_icon()
    print("AFO application has been shut down.")