import os
import json
import platformdirs

# APP constants
APP_NAME = "MILFO"
APP_AUTHOR = "MILFODevelopers"


# Finding the correct config directory based on OS
config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
config_file_path = os.path.join(config_dir, "settings.json")

def load_settings():
    """ Default settings if config file doesn't exist """
    if not os.path.exists(config_file_path):
        return {
            "monitored_path": None,  # Default path to monitor
            "google_api_key": None
        }
    try:
        with open(config_file_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print("Error reading config file. Using default settings.")
        return {
            "monitored_path": None,
            "google_api_key": None
        }
    
def save_settings(settings):
    """ Save settings to the config file """
    os.makedirs(config_dir, exist_ok=True)
    try:
        with open(config_file_path, 'w') as f:
            json.dump(settings, f, indent=4)
    except IOError as e:
        print(f"Error: Could not save settings to {config_file_path}. Reason: {e}")

