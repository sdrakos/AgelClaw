# AgelClaw Telegram Bot Example

## Quick Start

```bash
# Install
pip install git+https://github.com/sdrakos/AgelClaw.git

# Initialize and configure
agelclaw init
agelclaw setup

# Start the bot
agelclaw telegram
```

## What You Get

- Chat with an AI agent via Telegram
- Persistent memory across conversations
- Background task execution
- Skill-based task routing
- Multi-provider support (Claude + OpenAI)

## Configuration

During `agelclaw setup`, you'll be asked for:

1. **API Key** — at least one (Anthropic or OpenAI)
2. **Telegram Bot Token** — get from [@BotFather](https://t.me/BotFather)
3. **Allowed User IDs** — comma-separated Telegram user IDs (empty = all users)
