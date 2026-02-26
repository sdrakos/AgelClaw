# AgelClaw

**Self-evolving AI agent with persistent memory, skills, and multi-provider routing.**

By **Dr. Stefanos Drakos** | [agel.ai](https://agel.ai)

---

## Install

```bash
pip install git+https://github.com/sdrakos/AgelClaw.git
```

With optional providers:

```bash
pip install "agelclaw[all] @ git+https://github.com/sdrakos/AgelClaw.git"
```

## Quick Start

```bash
# 1. Initialize project directory
agelclaw init

# 2. Configure API keys (interactive wizard)
agelclaw setup

# 3. Start the Telegram bot
agelclaw telegram
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `agelclaw init [dir]` | Create project directory with config templates and default skills |
| `agelclaw setup` | Interactive wizard for API keys, provider, Telegram token |
| `agelclaw daemon` | Start background task daemon (`:8420`) |
| `agelclaw web` | Start web UI + API server (`:8000`) |
| `agelclaw telegram` | Start Telegram bot |
| `agelclaw status` | Show daemon status + task statistics |
| `agelclaw chat` | Interactive CLI chat |
| `agelclaw --version` | Show version |

## Memory CLI (used by agents)

```bash
agelclaw-mem context              # Full context summary
agelclaw-mem pending              # Pending tasks
agelclaw-mem add_task "title" "description" [priority] [due_at] [recurring]
agelclaw-mem skills               # List installed skills
agelclaw-mem search "query"       # Semantic search
```

## Architecture

```
~/.agelclaw/                    # Project directory (mutable user data)
├── config.yaml                 # API keys, provider, ports
├── .env                        # Environment variables
├── data/agent_memory.db        # SQLite persistent memory
├── logs/                       # Daemon & API logs
├── tasks/task_<id>/            # Task output folders
├── subagents/                  # Subagent definitions
├── reports/                    # Generated reports
└── .Claude/Skills/             # Installed skills (14 bundled)
```

### Multi-Provider Routing

AgelClaw routes tasks to the best provider automatically:

- **Claude** (Anthropic) — code, debugging, skill creation
- **OpenAI** — research, web search, analysis
- **Auto** — routes based on task type heuristics

### Persistent Memory

SQLite-based memory with:
- Task management (create, schedule, recurring tasks)
- Conversation history (shared across all channels)
- Learnings and insights
- User profile (auto-personalizes interactions)
- Semantic search via embeddings (optional)

### Skills System

Self-evolving skill library:
- 14 bundled skills (email, PDF, PPTX, XLSX, task notifications, etc.)
- Agent creates new skills automatically when encountering new domains
- Skills include executable scripts and reference docs

### Channels

All channels share the same memory and conversation history:
- **Web UI** — React chat interface at `localhost:8000`
- **Telegram** — Chat via Telegram bot
- **CLI** — Interactive terminal chat
- **Daemon** — Autonomous background task execution

## Project Directory Resolution

The project directory (where all mutable data lives) is resolved in this order:

1. `AGELCLAW_HOME` environment variable
2. Current directory if it contains `config.yaml` or `.agelclaw` marker
3. `~/.agelclaw/` default

You can override per-command: `agelclaw --home /path/to/project daemon`

## Requirements

- Python >= 3.11
- Claude Agent SDK (`pip install claude-agent-sdk`)
- At least one API key (Anthropic or OpenAI)

## Optional Dependencies

```bash
pip install "agelclaw[openai]"       # OpenAI Agents SDK
pip install "agelclaw[outlook]"      # Microsoft Graph email
pip install "agelclaw[embeddings]"   # Semantic search
pip install "agelclaw[all]"          # Everything
```

## Running with PM2

For production deployment:

```bash
agelclaw init
cp ~/.agelclaw/ecosystem.config.js .
pm2 start ecosystem.config.js
```

## License

MIT
