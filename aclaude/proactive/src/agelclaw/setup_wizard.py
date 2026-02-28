#!/usr/bin/env python3
"""
Setup Wizard
=============
Interactive CLI to configure the agent system.
Creates/updates config.yaml with API keys, provider preference, and settings.

Usage:
    python setup_wizard.py
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from agelclaw.core.config import load_config, save_config, CONFIG_PATH


def _check_claude_auth() -> dict | None:
    """Check Claude Code auth status. Returns status dict or None."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None
    try:
        result = subprocess.run(
            [claude_bin, "auth", "status"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _run_claude_login() -> bool:
    """Run claude auth login (opens browser). Returns True on success."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return False
    try:
        result = subprocess.run(
            [claude_bin, "auth", "login"],
            timeout=120,
        )
        return result.returncode == 0
    except Exception:
        return False


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

    # Step 1: Claude Code Subscription
    print("1. Claude Code Subscription")
    print("   Required for the agent to work (Max or Pro plan).")
    print()

    auth = _check_claude_auth()
    if auth and auth.get("loggedIn"):
        plan = auth.get("subscriptionType", "unknown")
        email = auth.get("email", "")
        print(f"   Already logged in: {email} ({plan} plan)")
        print()
    else:
        if shutil.which("claude"):
            print("   Claude Code is installed but not logged in.")
            answer = input("  Open browser to log in now? [Y/n]: ").strip().lower()
            if answer != "n":
                print("   Opening browser for login...")
                success = _run_claude_login()
                if success:
                    auth = _check_claude_auth()
                    if auth and auth.get("loggedIn"):
                        print(f"   Logged in as: {auth.get('email', '')} ({auth.get('subscriptionType', '')} plan)")
                    else:
                        print("   Login completed. Run 'claude auth status' to verify.")
                else:
                    print("   Login was cancelled or failed.")
                print()
        else:
            print("   Claude Code not found. Install it first:")
            print("   npm install -g @anthropic-ai/claude-code")
            print("   Then run: claude auth login")
            print()

    # Step 2: API Keys (optional — for direct API access or OpenAI)
    print("2. API Keys (optional)")
    print("   Only needed if you want direct API access or OpenAI routing.")
    print()
    config["anthropic_api_key"] = prompt_value(
        "Anthropic API Key (optional if logged in above)",
        current=config.get("anthropic_api_key", ""),
        secret=True,
    )
    config["openai_api_key"] = prompt_value(
        "OpenAI API Key",
        current=config.get("openai_api_key", ""),
        secret=True,
    )

    # Step 3: Default Provider
    print()
    print("3. Default Provider")
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

    # Step 4: Telegram (optional)
    print()
    print("4. Telegram Bot (optional)")
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

    # Step 5: Ports
    print()
    print("5. Port Settings")
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

    # Step 6: Limits
    print()
    print("6. Limits")
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
    # Check Claude auth status for summary
    auth = _check_claude_auth()
    claude_status = "Not configured"
    if auth and auth.get("loggedIn"):
        claude_status = f"{auth.get('email', '')} ({auth.get('subscriptionType', '')})"

    providers = []
    if auth and auth.get("loggedIn"):
        providers.append("Claude (subscription)")
    if config.get("anthropic_api_key"):
        providers.append("Claude (API)")
    if config.get("openai_api_key"):
        providers.append("OpenAI")

    print("Summary:")
    print(f"  Claude Code: {claude_status}")
    print(f"  Available providers: {', '.join(providers) if providers else 'None'}")
    print(f"  Default provider: {config['default_provider']}")
    print(f"  API port: {config['api_port']}")
    print(f"  Daemon port: {config['daemon_port']}")
    print(f"  Telegram: {'Configured' if config.get('telegram_bot_token') else 'Not configured'}")
    print()
    print("Next steps:")
    print("  agelclaw web         — Start the chat API + web UI")
    print("  agelclaw daemon      — Start the background daemon")
    if config.get("telegram_bot_token"):
        print("  agelclaw telegram    — Start the Telegram bot")
    print()


if __name__ == "__main__":
    main()
