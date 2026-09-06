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
behind this interface. T006 (this update) adds the first new backend -
OpenAI - following the same shape. Anthropic, Grok, and the local/offline
model are still T007-T009 and still raise a clear NotImplementedError rather
than silently returning None, so a user who picks one of those as
`active_provider` today gets an honest error instead of a mysteriously
"unconfigured" agent.
"""

# Same Gemini model name agent_core.py was already hard-coding.
GEMINI_MODEL = "gemini-3.5-flash"

# Default OpenAI chat model for the new T006 backend. Chosen as a small,
# tool-calling-capable, currently-supported model - not hard-coded anywhere
# else in the repo yet, so this is the single source of truth for it.
OPENAI_MODEL = "gpt-4o-mini"


def get_llm(settings):
    """
    Return a LangChain chat-model instance for whichever provider is set as
    `active_provider` in `settings` (the dict returned by
    `components.config_manager.load_settings()`).

    Returns `None` when the active provider is "google" but no API key is
    configured — this mirrors the previous agent_core.py behavior (agent
    stays unconfigured, no crash) rather than introducing a new failure mode.

    Raises:
        NotImplementedError: `active_provider` is a recognized provider that
            isn't implemented yet (anthropic/openai/grok/local - T006-T009).
        ValueError: `active_provider` isn't a recognized provider name at all.
    """
    active_provider = settings.get("active_provider", "google")
    providers = settings.get("providers", {})

    if active_provider == "google":
        api_key = providers.get("google", {}).get("api_key")
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
        raise NotImplementedError(
            "active_provider is 'anthropic', but the Anthropic backend isn't "
            "implemented yet - see implementation.md T007."
        )

    if active_provider == "openai":
        api_key = providers.get("openai", {}).get("api_key")
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
        raise NotImplementedError(
            "active_provider is 'grok', but the Grok (xAI) backend isn't "
            "implemented yet - see implementation.md T008."
        )

    if active_provider == "local":
        raise NotImplementedError(
            "active_provider is 'local', but the local/offline model backend "
            "isn't implemented yet - see implementation.md T009."
        )

    raise ValueError(
        f"Unknown active_provider '{active_provider}' in settings.json. "
        f"Expected one of: google, anthropic, openai, grok, local."
    )
