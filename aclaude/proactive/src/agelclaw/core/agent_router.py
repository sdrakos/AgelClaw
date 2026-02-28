"""
Agent Router
============
Routes tasks to Claude or OpenAI based on:
- User preference (default_provider in config)
- Task type heuristics (code→Claude, research→OpenAI, simple→mini)
- API key availability (fallback if requested provider unavailable)
"""

from enum import Enum
from dataclasses import dataclass

from agelclaw.core.config import load_config


class Provider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    AUTO = "auto"


@dataclass
class RouteResult:
    """Result of routing a task to a provider."""
    provider: Provider
    model: str
    reason: str


# Task type → preferred provider mapping for AUTO mode
# Chat = cheap mini model (dispatcher only)
# Daemon/subagent tasks = powerful models (Opus 4.6 / GPT-4.1)
_TASK_ROUTING = {
    "code": (Provider.CLAUDE, "claude-opus-4-6"),
    "debug": (Provider.CLAUDE, "claude-opus-4-6"),
    "refactor": (Provider.CLAUDE, "claude-opus-4-6"),
    "skill_create": (Provider.CLAUDE, "claude-opus-4-6"),
    "subagent_create": (Provider.CLAUDE, "claude-opus-4-6"),
    "research": (Provider.OPENAI, "gpt-4.1"),
    "web_search": (Provider.OPENAI, "gpt-4.1"),
    "analysis": (Provider.OPENAI, "gpt-4.1"),
    "simple": (Provider.OPENAI, "gpt-4.1-mini"),
    "chat": (Provider.CLAUDE, "claude-sonnet-4-5-20250929"),
    "general": (Provider.CLAUDE, "claude-opus-4-6"),
}

# Default models per provider
_DEFAULT_MODELS = {
    Provider.CLAUDE: "claude-opus-4-6",
    Provider.OPENAI: "gpt-4.1",
}


class AgentRouter:
    """Routes tasks to the appropriate AI provider."""

    def __init__(self):
        self._config = load_config()

    def _has_key(self, provider: Provider) -> bool:
        """Check if a provider is available.
        Claude is ALWAYS available — the SDK uses subscription auth (claude.ai login)
        even without an explicit API key. Only OpenAI requires an API key."""
        if provider == Provider.CLAUDE:
            # Always available: SDK uses bundled CLI with subscription auth
            return True
        elif provider == Provider.OPENAI:
            return bool(self._config.get("openai_api_key"))
        return False

    def _fallback(self, preferred: Provider) -> Provider | None:
        """If preferred provider unavailable, try the other one."""
        other = Provider.OPENAI if preferred == Provider.CLAUDE else Provider.CLAUDE
        if self._has_key(other):
            return other
        return None

    def route(self, task_type: str = "general", prefer: Provider | str | None = None) -> RouteResult:
        """Route a task to a provider.

        Args:
            task_type: Type of task (code, research, simple, chat, general, etc.)
            prefer: Explicit provider preference (overrides config default)

        Returns:
            RouteResult with provider, model, and reason.
        """
        # Reload config to pick up any changes
        self._config = load_config()

        # Determine preferred provider
        if prefer:
            if isinstance(prefer, str):
                try:
                    preferred = Provider(prefer.lower())
                except ValueError:
                    preferred = Provider(self._config.get("default_provider", "claude"))
            else:
                preferred = prefer
        else:
            preferred = Provider(self._config.get("default_provider", "claude"))

        # AUTO mode: use task type heuristics
        if preferred == Provider.AUTO:
            task_pref, model = _TASK_ROUTING.get(
                task_type, (Provider.CLAUDE, _DEFAULT_MODELS[Provider.CLAUDE])
            )
            if self._has_key(task_pref):
                return RouteResult(provider=task_pref, model=model, reason=f"auto:{task_type}")

            # Fallback
            fb = self._fallback(task_pref)
            if fb:
                return RouteResult(
                    provider=fb,
                    model=_DEFAULT_MODELS[fb],
                    reason=f"auto:{task_type}→fallback:{fb.value}",
                )
            # No keys at all — default to claude (SDK might use env/config)
            return RouteResult(
                provider=Provider.CLAUDE,
                model=_DEFAULT_MODELS[Provider.CLAUDE],
                reason="auto:no_keys_fallback_claude",
            )

        # Explicit provider requested
        if self._has_key(preferred):
            model = _DEFAULT_MODELS.get(preferred, _DEFAULT_MODELS[Provider.CLAUDE])
            return RouteResult(provider=preferred, model=model, reason=f"explicit:{preferred.value}")

        # Fallback to other provider
        fb = self._fallback(preferred)
        if fb:
            return RouteResult(
                provider=fb,
                model=_DEFAULT_MODELS[fb],
                reason=f"fallback:{preferred.value}→{fb.value}",
            )

        # No keys — still return requested (Claude SDK might use its own config)
        return RouteResult(
            provider=preferred,
            model=_DEFAULT_MODELS.get(preferred, _DEFAULT_MODELS[Provider.CLAUDE]),
            reason=f"no_keys:{preferred.value}",
        )

    @property
    def available_providers(self) -> list[Provider]:
        """List providers that have API keys configured."""
        self._config = load_config()
        return [p for p in [Provider.CLAUDE, Provider.OPENAI] if self._has_key(p)]
