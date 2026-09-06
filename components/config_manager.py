import os
import json
import platformdirs
from constants import APP_NAME, APP_AUTHOR


config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
config_file_path = os.path.join(config_dir, "settings.json")

# Providers supported by the multi-provider schema (T003). See docs/config_schema.md.
SUPPORTED_PROVIDERS = ["google", "anthropic", "openai", "grok"]


def _default_settings():
    """ Default settings, per the multi-provider schema documented in docs/config_schema.md """
    return {
        "monitored_path": None,
        "active_provider": "google",
        "providers": {
            "google": {"api_key": None},
            "anthropic": {"api_key": None},
            "openai": {"api_key": None},
            "grok": {"api_key": None},
            "local": {"enabled": False, "model": None},
        },
    }


def _is_new_schema(raw):
    """ True if `raw` already matches the post-T003 shape. """
    return isinstance(raw, dict) and "providers" in raw and "active_provider" in raw


def _migrate_legacy_settings(raw):
    """
    Convert a pre-T003 flat settings dict (monitored_path + google_api_key/GOOGLE_API_KEY)
    into the new multi-provider schema.

    The old code read the key inconsistently as both `google_api_key` (per README) and
    `GOOGLE_API_KEY` (per agent_core.py/check_models.py) - see state.md Section 2. We honor
    whichever is present, preferring the lowercase/README-documented form if both exist.
    Any other keys we don't recognize are preserved under "_legacy" rather than dropped,
    in case a later task still needs them.
    """
    migrated = _default_settings()
    migrated["monitored_path"] = raw.get("monitored_path")

    legacy_key = raw.get("google_api_key") or raw.get("GOOGLE_API_KEY")
    if legacy_key:
        migrated["providers"]["google"]["api_key"] = legacy_key

    known_keys = {"monitored_path", "google_api_key", "GOOGLE_API_KEY"}
    leftovers = {k: v for k, v in raw.items() if k not in known_keys}
    if leftovers:
        migrated["_legacy"] = leftovers

    return migrated


def load_settings():
    """
    Load settings.json, migrating it from the pre-T003 flat schema to the new
    multi-provider schema if needed (see docs/config_schema.md). If the file is
    already in the new schema, any provider missing from it (e.g. one added in a
    later task) is back-filled with its default so callers can always safely do
    settings["providers"]["<name>"] without a KeyError.
    """
    if not os.path.exists(config_file_path):
        return _default_settings()

    try:
        with open(config_file_path, 'r') as f:
            raw = json.load(f)
    except (json.JSONDecodeError, IOError):
        print("Error reading config file. Using default settings.")
        return _default_settings()

    if _is_new_schema(raw):
        defaults = _default_settings()
        raw.setdefault("providers", {})
        for provider, provider_defaults in defaults["providers"].items():
            raw["providers"].setdefault(provider, provider_defaults)
        raw.setdefault("active_provider", defaults["active_provider"])
        raw.setdefault("monitored_path", None)
        return raw

    print("Detected pre-multi-provider settings.json - migrating to the new schema (T003).")
    migrated = _migrate_legacy_settings(raw)
    save_settings(migrated)
    return migrated


def save_settings(settings):
    """ Save settings to the config file """
    os.makedirs(config_dir, exist_ok=True)
    try:
        with open(config_file_path, 'w') as f:
            json.dump(settings, f, indent=4)
    except IOError as e:
        print(f"Error: Could not save settings to {config_file_path}. Reason: {e}")
