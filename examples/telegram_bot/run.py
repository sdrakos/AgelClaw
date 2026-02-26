#!/usr/bin/env python3
"""
Minimal Telegram bot example using AgelClaw.

Prerequisites:
    pip install git+https://github.com/sdrakos/AgelClaw.git
    agelclaw init
    agelclaw setup   # set Telegram bot token + API keys

Then run:
    python run.py
    # or simply: agelclaw telegram
"""

from agelclaw.telegram_bot import main

if __name__ == "__main__":
    main()
