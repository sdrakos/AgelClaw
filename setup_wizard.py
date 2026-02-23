#!/usr/bin/env python3
"""
Setup Wizard
=============
Interactive CLI to configure the agent system.
Creates/updates config.yaml with API keys, provider preference, and settings.

Usage:
    python setup_wizard.py
"""

import sys
from pathlib import Path

# Ensure we can import core modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import load_config, save_config, CONFIG_PATH


def prompt_value(label: str, current: str = "", secret: bool = False, default: str = "") -> str:
    """Prompt user for a value with optional default."""
    display_current = "***" if secret and current else current
    if display_current:
        hint = f" [{display_current}]"
    elif default:
        hint = f" [{default}]"
    else:
        hint = ""

    val = input(f"  {label}{hint}: ").strip()
    if not val:
        return current if current else default
    return val


def main():
    print()
    print("=" * 50)
    print("  AgelClaw Agent — Setup Wizard")
    print("=" * 50)
    print()
    print(f"Config file: {CONFIG_PATH}")
    print()

    # Load existing config
    config = load_config()

    # Step 1: API Keys
    print("1. API Keys")
    print("   At least one is required (Claude or OpenAI).")
    print()
    config["anthropic_api_key"] = prompt_value(
        "Anthropic API Key",
        current=config.get("anthropic_api_key", ""),
        secret=True,
    )
    config["openai_api_key"] = prompt_value(
        "OpenAI API Key",
        current=config.get("openai_api_key", ""),
        secret=True,
    )

    if not config.get("anthropic_api_key") and not config.get("openai_api_key"):
        print()
        print("  WARNING: No API keys configured. You'll need at least one to use the agent.")
        print()

    # Step 2: Default Provider
    print()
    print("2. Default Provider")
    print("   claude  — Use Claude (Anthropic) for all tasks")
    print("   openai  — Use OpenAI for all tasks")
    print("   auto    — Route automatically based on task type")
    print()
    config["default_provider"] = prompt_value(
        "Default provider",
        current=config.get("default_provider", ""),
        default="claude",
    )
    if config["default_provider"] not in ("claude", "openai", "auto"):
        print(f"  Invalid provider '{config['default_provider']}', using 'claude'")
        config["default_provider"] = "claude"

    # Step 3: Telegram (optional)
    print()
    print("3. Telegram Bot (optional)")
    print("   Create a bot via @BotFather on Telegram to get a token.")
    print()
    config["telegram_bot_token"] = prompt_value(
        "Telegram Bot Token",
        current=config.get("telegram_bot_token", ""),
        secret=True,
    )
    config["telegram_allowed_users"] = prompt_value(
        "Allowed user IDs (comma-separated, empty=all)",
        current=config.get("telegram_allowed_users", ""),
    )

    # Step 4: Ports
    print()
    print("4. Port Settings")
    print()
    config["api_port"] = int(prompt_value(
        "API server port",
        current=str(config.get("api_port", "")),
        default="8000",
    ))
    config["daemon_port"] = int(prompt_value(
        "Daemon port",
        current=str(config.get("daemon_port", "")),
        default="8420",
    ))

    # Step 5: Limits
    print()
    print("5. Limits")
    print()
    config["cost_limit_daily"] = float(prompt_value(
        "Daily cost limit ($)",
        current=str(config.get("cost_limit_daily", "")),
        default="10.00",
    ))
    config["max_concurrent_tasks"] = int(prompt_value(
        "Max concurrent tasks",
        current=str(config.get("max_concurrent_tasks", "")),
        default="3",
    ))
    config["check_interval"] = int(prompt_value(
        "Check interval (seconds)",
        current=str(config.get("check_interval", "")),
        default="300",
    ))

    # Save
    save_config(config)
    print()
    print(f"Config saved to: {CONFIG_PATH}")
    print()

    # Summary
    providers = []
    if config.get("anthropic_api_key"):
        providers.append("Claude")
    if config.get("openai_api_key"):
        providers.append("OpenAI")
    print("Summary:")
    print(f"  Available providers: {', '.join(providers) if providers else 'None (add API keys)'}")
    print(f"  Default provider: {config['default_provider']}")
    print(f"  API port: {config['api_port']}")
    print(f"  Daemon port: {config['daemon_port']}")
    print(f"  Telegram: {'Configured' if config.get('telegram_bot_token') else 'Not configured'}")
    print()
    print("Next steps:")
    print("  python api_server.py        — Start the chat API")
    print("  python daemon_v2.py         — Start the background daemon")
    if config.get("telegram_bot_token"):
        print("  python telegram_bot.py      — Start the Telegram bot")
    print()


if __name__ == "__main__":
    main()
