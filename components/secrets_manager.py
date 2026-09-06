"""
components/secrets_manager.py

API key storage for AFO (T014, implementation.md Phase 0).

Prior to T014, API keys lived in plaintext in settings.json
(`providers.<name>.api_key`). This module moves the source of truth to the
OS keychain via the `keyring` package, with an environment-variable
override that always wins - useful for headless boxes, CI, or anyone who
just doesn't want a key sitting in the keychain at all.

Resolution order for get_api_key(provider):
    1. Environment variable `AFO_<PROVIDER>_API_KEY` (e.g. AFO_GOOGLE_API_KEY,
       AFO_OPENAI_API_KEY, AFO_ANTHROPIC_API_KEY, AFO_GROK_API_KEY).
       Always checked first and always wins over the keychain.
    2. OS keychain, via `keyring.get_password(APP_NAME, "<provider>_api_key")`
       - macOS Keychain, Windows Credential Locker, or the Secret
       Service/kwallet on Linux, depending on what `keyring` finds
       available on the host.
    3. Neither set, or the keychain backend itself is unreachable (e.g. a
       headless Linux session with no Secret Service running) -> print a
       warning and return None. This matches the existing "unconfigured,
       don't crash" convention every provider branch in llm/provider.py
       already used for a missing key.

set_api_key/delete_api_key are thin wrappers around
keyring.set_password/delete_password, for a settings UI (Phase 4, T037) or
migrate_plaintext_keys() below to write/clear a key without ever touching
settings.json.

migrate_plaintext_keys(settings) is called by
components.config_manager.load_settings() on every load: it walks
providers.{google,anthropic,openai,grok} and, for any provider that still
has a non-null providers.<name>.api_key, writes that value into the
keychain via set_api_key and clears the field in the dict in place. Returns
True if anything was migrated (so the caller knows to re-save
settings.json), False otherwise.
"""
import os

import keyring
from keyring.errors import KeyringError

from constants import APP_NAME

# Providers whose keys this module manages. Kept in sync with
# config_manager.SUPPORTED_PROVIDERS - "local" is intentionally excluded,
# since it has no API key, just enabled/model flags read directly from
# settings.json.
_MANAGED_PROVIDERS = ["google", "anthropic", "openai", "grok"]


def _keychain_username(provider):
    return f"{provider}_api_key"


def _env_var_name(provider):
    return f"AFO_{provider.upper()}_API_KEY"


def get_api_key(provider):
    """
    Resolve the API key for `provider` (e.g. "google", "anthropic", "openai",
    "grok"): environment variable override first, then the OS keychain.
    Returns None (with a printed warning) if neither is set, or if the
    keychain backend itself is unreachable.
    """
    env_value = os.environ.get(_env_var_name(provider))
    if env_value:
        return env_value

    try:
        return keyring.get_password(APP_NAME, _keychain_username(provider))
    except KeyringError as e:
        print(
            f"Warning: could not read '{provider}' API key from the OS keychain "
            f"({e}). Set the {_env_var_name(provider)} environment variable as "
            f"a fallback, or configure a keychain/Secret Service backend."
        )
        return None


def set_api_key(provider, api_key):
    """ Store `api_key` for `provider` in the OS keychain. """
    try:
        keyring.set_password(APP_NAME, _keychain_username(provider), api_key)
        return True
    except KeyringError as e:
        print(f"Warning: could not write '{provider}' API key to the OS keychain ({e}).")
        return False


def delete_api_key(provider):
    """ Remove any stored key for `provider` from the OS keychain, if present. """
    try:
        keyring.delete_password(APP_NAME, _keychain_username(provider))
        return True
    except KeyringError as e:
        print(f"Warning: could not delete '{provider}' API key from the OS keychain ({e}).")
        return False


def migrate_plaintext_keys(settings):
    """
    Move any plaintext API keys still sitting in
    settings["providers"][<name>]["api_key"] into the OS keychain, clearing
    the field in `settings` in place. Returns True if anything was migrated
    (caller should then re-save settings.json), False otherwise.
    """
    migrated_any = False
    providers = settings.get("providers", {})

    for provider in _MANAGED_PROVIDERS:
        provider_settings = providers.get(provider)
        if not provider_settings:
            continue

        plaintext_key = provider_settings.get("api_key")
        if not plaintext_key:
            continue

        if set_api_key(provider, plaintext_key):
            provider_settings["api_key"] = None
            migrated_any = True
            print(f"Migrated '{provider}' API key out of settings.json and into the OS keychain (T014).")

    return migrated_any