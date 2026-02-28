"""
Configuration Loader
====================
Loads config.yaml with environment variable overrides.
Env vars always take priority over YAML values.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from agelclaw.project import get_project_dir, get_config_path, get_env_path

CONFIG_PATH = get_config_path()

# Load .env so API keys are available via os.getenv
load_dotenv(get_env_path())

_config_cache: dict | None = None

# Map of config keys → env var names
_ENV_MAP = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
    "default_provider": "AGENT_DEFAULT_PROVIDER",
    "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    "telegram_allowed_users": "TELEGRAM_ALLOWED_USERS",
    "api_port": "AGENT_API_PORT",
    "daemon_port": "AGENT_DAEMON_PORT",
    "cost_limit_daily": "AGENT_COST_LIMIT_DAILY",
    "max_concurrent_tasks": "AGENT_MAX_CONCURRENT",
    "check_interval": "AGENT_CHECK_INTERVAL",
    "outlook_client_id": "OUTLOOK_CLIENT_ID",
    "outlook_client_secret": "OUTLOOK_CLIENT_SECRET",
    "outlook_tenant_id": "OUTLOOK_TENANT_ID",
    "outlook_user_email": "OUTLOOK_USER_EMAIL",
}

# Type coercions for non-string fields
_TYPE_MAP = {
    "api_port": int,
    "daemon_port": int,
    "cost_limit_daily": float,
    "max_concurrent_tasks": int,
    "check_interval": int,
}


def load_config(force_reload: bool = False) -> dict[str, Any]:
    """Load config.yaml, with env var overrides. Cached as singleton."""
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache

    # 1. Load YAML (or empty dict if missing)
    config: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # 2. Override with env vars
    for key, env_var in _ENV_MAP.items():
        env_val = os.getenv(env_var)
        if env_val is not None:
            config[key] = env_val
        elif key not in config:
            # Set defaults for missing keys
            config[key] = _get_default(key)

    # 3. Type coercion
    for key, type_fn in _TYPE_MAP.items():
        if key in config and config[key] is not None:
            try:
                config[key] = type_fn(config[key])
            except (ValueError, TypeError):
                config[key] = _get_default(key)

    _config_cache = config
    return config


def get(key: str, default: Any = None) -> Any:
    """Get a single config value."""
    return load_config().get(key, default)


def save_config(config: dict[str, Any]) -> None:
    """Save config dict back to config.yaml."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    # Invalidate cache
    global _config_cache
    _config_cache = None


def save_env_file(config: dict[str, Any]) -> None:
    """Write sensitive config to .env file for services that read env vars directly."""
    env_lines = []
    for yaml_key, env_var in _ENV_MAP.items():
        val = config.get(yaml_key, "")
        if val:
            env_lines.append(f"{env_var}={val}")
    env_path = get_env_path()
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")


def _get_default(key: str) -> Any:
    """Default values for config keys."""
    defaults = {
        "anthropic_api_key": "",
        "openai_api_key": "",
        "google_api_key": "",
        "default_provider": "claude",
        "telegram_bot_token": "",
        "telegram_allowed_users": "",
        "api_port": 8000,
        "daemon_port": 8420,
        "cost_limit_daily": 10.0,
        "max_concurrent_tasks": 3,
        "check_interval": 300,
        "outlook_client_id": "",
        "outlook_client_secret": "",
        "outlook_tenant_id": "",
        "outlook_user_email": "",
    }
    return defaults.get(key, "")
