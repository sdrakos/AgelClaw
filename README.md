# AgelClaw

**Self-evolving AI agent with persistent memory, skills, and multi-provider routing.**

By **Dr. Stefanos Drakos** | [agel.ai](https://agel.ai)

---

## Quick Install (Windows — no experience needed)

Download and double-click **[install.bat](https://raw.githubusercontent.com/sdrakos/AgelClaw/main/install.bat)** — it installs everything automatically:

- Python, Node.js (if missing)
- Claude Code + login
- AgelClaw + project setup
- Desktop shortcut

After installation, just double-click **AgelClaw** on your Desktop to chat.

---

## Manual Installation (developers)

### Prerequisites

| Requirement | How to get it |
|-------------|---------------|
| **Python 3.11+** | [python.org/downloads](https://www.python.org/downloads/) |
| **Node.js 18+** | [nodejs.org](https://nodejs.org/) |
| **Claude subscription** | Max or Pro plan at [claude.ai](https://claude.ai/) |

## Installation (5 minutes)

### Step 1 — Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### Step 2 — Log in to your Claude account

```bash
claude auth login
```

This opens your browser. Sign in with the account that has a Max or Pro subscription.

Verify:
```bash
claude auth status
# Should show: loggedIn: true, subscriptionType: max (or pro)
```

### Step 3 — Install AgelClaw

```bash
pip install git+https://github.com/sdrakos/AgelClaw.git
```

With all optional features (OpenAI, Outlook email, semantic search):
```bash
pip install "agelclaw[all] @ git+https://github.com/sdrakos/AgelClaw.git"
```

### Step 4 — Initialize and configure

```bash
agelclaw init
agelclaw setup
```

The setup wizard will:
1. Verify your Claude subscription (or help you log in)
2. Ask for API keys (OpenAI is optional)
3. Configure Telegram bot (optional)
4. Set ports and limits

### Step 5 — Start using

```bash
# Interactive chat (like claude)
agelclaw

# Or start the Telegram bot
agelclaw telegram

# Or start the web UI
agelclaw web
```

---

## Usage

### Interactive Chat

```bash
agelclaw                          # Open interactive chat
agelclaw "summarize my tasks"     # Chat with initial prompt
agelclaw -p "what tasks are due?" # Single answer, then exit
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `agelclaw` | Interactive chat (default) |
| `agelclaw init [dir]` | Create project directory with config templates and default skills |
| `agelclaw setup` | Interactive wizard for Claude auth, API keys, Telegram |
| `agelclaw daemon` | Start background task daemon (`:8420`) |
| `agelclaw web` | Start web UI + API server (`:8000`) |
| `agelclaw telegram` | Start Telegram bot |
| `agelclaw status` | Show daemon status + task statistics |
| `agelclaw --version` | Show version |

### Memory CLI (used by agents internally)

```bash
agelclaw-mem context              # Full context summary
agelclaw-mem pending              # Pending tasks
agelclaw-mem add_task "title" "description" [priority] [due_at] [recurring]
agelclaw-mem skills               # List installed skills
agelclaw-mem search "query"       # Semantic search
```

---

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
