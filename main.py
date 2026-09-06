from app_tray import create_tray_icon
from components.events_log import init_db

if __name__ == "__main__":
    print("Starting AFO application...")
    # T012: make sure the events (audit log) table exists before anything
    # tries to write to it. Idempotent - safe on every startup.
    init_db()
    create_tray_icon()
    print("AFO application has been shut down.")