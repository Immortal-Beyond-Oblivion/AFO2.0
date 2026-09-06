"""
llm/provider.py

Provider-neutral LLM interface (T005, implementation.md Phase 0).

`agent_core.py` previously constructed `ChatGoogleGenerativeAI` directly and
read the API key straight off the old flat `GOOGLE_API_KEY` settings key.
This module gives it (and any future caller) a single `get_llm(settings)`
entry point that reads the new multi-provider `settings.json` schema from
T003 (see docs/config_schema.md) and returns a LangChain chat-model object
supporting the same `.bind_tools()` / `.invoke()` interface agent_core.py
already relies on.

Scope for T005 was a refactor only: migrate the existing Google Gemini path
behind this interface. T006 added the second backend - OpenAI - following
the same shape. T007 added the third - Anthropic - again following the same
shape. T008 added the fourth - Grok (xAI) - same shape again. T009 adds the
fifth and final Phase-0 backend - a local/offline model via Ollama - which
never makes a network call to any cloud provider (it only ever talks to a
local Ollama server on localhost). With T009 done, every provider listed
in the settings schema (docs/config_schema.md) is wired up: google,
anthropic, openai, grok, local.

T014 changes *where this module gets its API keys from*: it now calls
components.secrets_manager.get_api_key(provider) (env var override, then OS
keychain) instead of reading providers.<name>.api_key straight off the
settings dict. settings.json no longer holds cleartext keys once
config_manager.load_settings() has run its T014 migration once - see
components/secrets_manager.py. The `settings` dict is still consulted for
everything that isn't a secret (active_provider, providers.local.enabled/
model), so this module's public signature (get_llm(settings)) is unchanged.
"""
from components import secrets_manager

# Same Gemini model name agent_core.py was already hard-coding.
GEMINI_MODEL = "gemini-3.5-flash"

# Default OpenAI chat model for the T006 backend. Chosen as a small,
# tool-calling-capable, currently-supported model - not hard-coded anywhere
# else in the repo yet, so this is the single source of truth for it.
OPENAI_MODEL = "gpt-4o-mini"

# Default Anthropic chat model for the T007 backend. Chosen as a small,
# fast, tool-calling-capable, currently-supported model - same reasoning as
# OPENAI_MODEL above, and likewise not hard-coded anywhere else in the repo.
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# Default Grok (xAI) chat model for the new T008 backend. Chosen as a small,
# fast, tool-calling-capable, currently-supported model - same reasoning as
# OPENAI_MODEL/ANTHROPIC_MODEL above, and likewise not hard-coded anywhere
# else in the repo.
GROK_MODEL = "grok-4-fast"

# Default local Ollama server address for the T009 backend. Deliberately
# hard-coded to localhost rather than read from settings, so this backend
# can never be pointed at a remote host - the whole point of "local/offline"
# is that it never leaves the user's machine or hits a cloud API.
OLLAMA_BASE_URL = "http://localhost:11434"


def get_llm(settings):
    """
    Return a LangChain chat-model instance for whichever provider is set as
    `active_provider` in `settings` (the dict returned by
    `components.config_manager.load_settings()`).

    Returns `None` when the active cloud provider has no API key configured,
    or when `active_provider` is "local" but `providers.local.enabled` is
    false or `providers.local.model` is unset — this mirrors the previous
    agent_core.py behavior (agent stays unconfigured, no crash) rather than
    introducing a new failure mode.

    Raises:
        ValueError: `active_provider` isn't a recognized provider name at all.
    """
    active_provider = settings.get("active_provider", "google")
    providers = settings.get("providers", {})

    if active_provider == "google":
        # T014: key comes from the OS keychain (or an env var override),
        # not from settings["providers"]["google"]["api_key"] - that field
        # is now always None once config_manager's T014 migration has run.
        api_key = secrets_manager.get_api_key("google")
        if not api_key:
            return None
        # Imported lazily so importing this module never requires the
        # langchain_google_genai package unless the google backend is
        # actually selected (matters more once T006-T009 add sibling
        # provider SDKs that a given install may not have pulled in).
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
            temperature=0,
        )

    if active_provider == "anthropic":
        api_key = secrets_manager.get_api_key("anthropic")  # T014: keychain/env, not settings.json
        if not api_key:
            return None
        # Imported lazily, same reasoning as the google/openai branches above:
        # don't require langchain_anthropic to be installed unless this
        # backend is actually selected.
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=ANTHROPIC_MODEL,
            api_key=api_key,
            temperature=0,
        )

    if active_provider == "openai":
        api_key = secrets_manager.get_api_key("openai")  # T014: keychain/env, not settings.json
        if not api_key:
            return None
        # Imported lazily, same reasoning as the google branch above: don't
        # require langchain_openai to be installed unless this backend is
        # actually selected.
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=api_key,
            temperature=0,
        )

    if active_provider == "grok":
        api_key = secrets_manager.get_api_key("grok")  # T014: keychain/env, not settings.json
        if not api_key:
            return None
        # Imported lazily, same reasoning as the google/openai/anthropic
        # branches above: don't require langchain_xai to be installed unless
        # this backend is actually selected. xAI's Grok API is OpenAI-compatible,
        # but we use the dedicated langchain-xai integration (ChatXAI) rather
        # than pointing ChatOpenAI at a custom base_url, so this backend gets
        # the same first-class LangChain support (tool-calling, streaming,
        # etc.) as the other three instead of being a workaround.
        from langchain_xai import ChatXAI
        return ChatXAI(
            model=GROK_MODEL,
            api_key=api_key,
            temperature=0,
        )

    if active_provider == "local":
        local_settings = providers.get("local", {})
        # Both checks matter: `enabled` is an explicit opt-in (so a stray
        # `model` value left over from a previous experiment doesn't
        # silently activate local mode), and `model` has to actually be set
        # since there's no sane default Ollama tag to fall back to - unlike
        # the cloud providers, we can't assume a specific model is pulled.
        if not local_settings.get("enabled") or not local_settings.get("model"):
            return None
        # Imported lazily, same reasoning as the other branches above: don't
        # require langchain_ollama to be installed unless this backend is
        # actually selected.
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=local_settings["model"],
            # Hard-coded to OLLAMA_BASE_URL (localhost) rather than reading a
            # host from settings - this is what makes "local/offline"
            # actually guaranteed local: there is no config field that lets
            # this backend be pointed at a remote server or cloud endpoint.
            base_url=OLLAMA_BASE_URL,
            temperature=0,
        )

    raise ValueError(
        f"Unknown active_provider '{active_provider}' in settings.json. "
        f"Expected one of: google, anthropic, openai, grok, local."
    )
