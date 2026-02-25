# AgelClaw Proactive Agent

**A self-evolving autonomous AI assistant with persistent memory, multi-provider routing, and parallel task execution.**

By **Dr. Stefanos Drakos** | [github.com/sdrakos/AgelClaw](https://github.com/sdrakos/AgelClaw)

---

## Quick Start (Windows)

1. **Download:** Click `Code` → `Download ZIP` from GitHub
2. **Extract** the zip anywhere on your computer
3. **Double-click** `start.bat`
4. **Wait** — it automatically installs everything (first time takes ~2 minutes)
5. **Browser opens** → go to **Settings** → paste your API key → **Save**
6. **Done!** Start chatting with your AI agent

> You need at least one API key: [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/api-keys)

### Quick Start (Mac / Linux)

```bash
chmod +x start.sh
./start.sh
```

---

## What Does start.bat Do?

The launcher handles everything automatically:

1. Checks that Python 3.11+ is installed
2. Creates a virtual environment (`.venv/`)
3. Installs all Python dependencies
4. Creates `data/`, `logs/`, `reports/` directories
5. Installs 14 bundled AI skills
6. Creates `config.yaml` from template (first run)
7. Starts the web server
8. Opens your browser to `http://localhost:8000`

No terminal knowledge needed. No Node.js required.

---

## What Is This?

AgelClaw is an AI agent system that runs on your machine. It learns from every interaction, creates reusable skills, executes tasks in the background, and gets smarter over time.

**Three services can run together:**

| Service | Port | Description |
|---------|------|-------------|
| **API Server** | `:8000` | Web Chat UI + REST API + SSE streaming |
| **Daemon** | `:8420` | Background task processor with parallel execution |
| **Telegram Bot** | — | Chat with the agent from Telegram (optional) |

All three share the same **SQLite memory database** — conversations started on the web continue seamlessly on Telegram, and the daemon knows everything discussed.

---

## Key Features

### Multi-Provider AI Routing
Routes tasks between **Claude** (Anthropic) and **OpenAI** (GPT-4.1) based on task type:
- Code tasks → Claude Sonnet (best at code generation)
- Research/analysis → OpenAI GPT-4.1
- Simple/chat → GPT-4.1-mini (fast & cheap)
- Force a specific provider per request, or let auto-routing decide

### Persistent Memory
SQLite database stores everything across sessions:
- **Tasks** — pending, scheduled, recurring, completed, with priorities and dependencies
- **Conversations** — shared across web, Telegram, and daemon channels
- **Learnings** — agent discoveries, promotable to hard rules
- **User Profile** — identity, work, preferences, relationships, habits
- **Skills** — reusable task templates with scripts and references
- **Semantic Search** — vector embeddings for AI-powered memory recall

### Self-Evolving Skills
The agent follows a **skill-first** pattern:
1. Search for an existing skill matching the task
2. If found — follow its instructions and scripts
3. If not — research the topic, create a new skill, then execute
4. Update the skill if improvements are discovered

### Background Daemon (Parallel Execution)
The daemon runs tasks autonomously:
- **Parallel execution** — up to N tasks simultaneously (configurable)
- **Smart scheduling** — wakes exactly when the next task is due
- **Recurring tasks** — daily, weekly, or interval-based (`daily_09:00`, `every_2h`)
- **SSE event stream** — real-time monitoring from the web UI
- **Auto-retry** — failed tasks retry automatically

### Hard Rules (Promoted Learnings)
Promote learnings to **hard rules** injected into every system prompt as enforceable instructions. Critical lessons are never forgotten.

---

## Architecture

```
React UI (:3000 dev / :8000 prod)
  ├── POST /api/chat   →  api_server.py  →  Agent Router
  ├── GET /daemon/events →  proxy  →  daemon_v2.py SSE
  └── static files      →  react-claude-chat/dist/

Agent Router
  ├── Claude Agent SDK (code, general tasks)
  └── OpenAI Agents SDK (research, analysis, simple)

daemon_v2.py (:8420)
  ├── Scheduler loop: checks memory for due/pending tasks
  ├── Each task: independent query() call (parallel via asyncio.gather)
  ├── Semaphore limits concurrency (default 3)
  └── SSE events: cycle_start, task_start, agent_text, tool_use, task_end

Shared Memory: memory.py → data/agent_memory.db (SQLite WAL)
  Tables: tasks, conversations, skills, learnings, kv_store, user_profile
```

---

## Advanced Setup

### Production (PM2)

For running all services 24/7:

```bash
# First, run launcher.py once to create .venv and install deps
python launcher.py

# Then use PM2
npm install -g pm2
pm2 start ecosystem.config.js
pm2 start ecosystem.config.js --env production    # 10-min daemon cycle

pm2 status        # Check processes
pm2 logs          # Live logs
pm2 monit         # CPU/RAM monitor
pm2 stop all      # Stop everything
```

### Development (3 terminals)

```bash
# Activate venv first
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

python api_server.py      # API + Web UI on :8000
python daemon_v2.py       # Daemon on :8420
python telegram_bot.py    # Telegram bot (optional)
```

### Configuration

Edit `config.yaml` directly or use the Settings page in the UI:

```yaml
anthropic_api_key: "sk-ant-..."
openai_api_key: "sk-proj-..."
default_provider: "auto"          # auto | claude | openai
api_port: 8000
daemon_port: 8420
max_concurrent_tasks: 3
check_interval: 300               # daemon cycle interval (seconds)
```

---

## Bundled Skills

AgelClaw comes with 14 pre-installed skills:

| Skill | Description |
|-------|-------------|
| **claude-sdk-subagents** | Spawn parallel Claude subagents |
| **list-directory** | Browse and list directory contents |
| **list-skills** | List all installed skills |
| **mcp-installer** | Install MCP servers |
| **mcp-server-creator** | Create custom MCP servers |
| **microsoft-graph-email** | Send/read email via Microsoft Graph |
| **openai-agents-sdk** | Create OpenAI agent pipelines |
| **outlook-email-digest** | Daily Outlook email summaries |
| **pdf** | Generate and manipulate PDF files |
| **pptx** | Create PowerPoint presentations |
| **react-chat-ui** | Build React chat interfaces |
| **skill-creator** | Create new skills from scratch |
| **task-completion-notifier** | Email notifications on task completion |
| **xlsx** | Create and edit Excel spreadsheets |

---

## Memory CLI Reference

Agents interact with memory through `mem_cli.py`. Also useful for manual inspection:

### Tasks
```bash
python mem_cli.py pending [limit]                    # Pending tasks
python mem_cli.py due                                # Due now
python mem_cli.py stats                              # Task statistics
python mem_cli.py add_task "title" "desc" [pri] [due_at] [recurring]
python mem_cli.py start_task <id>
python mem_cli.py complete_task <id> "result"
```

### Skills
```bash
python mem_cli.py skills                             # List installed
python mem_cli.py find_skill "description"           # Find matching
python mem_cli.py create_skill <name> "desc" "body" [location]
```

### Learnings & Hard Rules
```bash
python mem_cli.py add_learning "category" "insight"
python mem_cli.py rules                              # Active hard rules
python mem_cli.py promote_rule <id>                  # Learning → hard rule
```

### User Profile
```bash
python mem_cli.py profile [category]
python mem_cli.py set_profile <cat> <key> "<value>" [confidence] [source]
```

### Semantic Search
```bash
python mem_cli.py search "query" [limit]
python mem_cli.py embed_backfill                     # Backfill embeddings
```

---

## API Reference

### API Server (`:8000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Public config (no secrets) |
| GET | `/api/settings` | Full settings (for Settings page) |
| PUT | `/api/settings` | Update settings |
| GET | `/api/stats` | Task statistics |
| GET | `/api/skills` | Installed skills list |
| POST | `/api/chat` | Chat with agent (SSE streaming) |
| GET | `/api/subagents` | List subagents |
| POST | `/api/subagents` | Create and run subagent |
| GET | `/daemon/{path}` | Proxy to daemon API |

### Daemon (`:8420`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/task` | Submit a new task |
| GET | `/status` | Daemon state + running tasks |
| GET | `/tasks?status=pending` | List tasks by status |
| POST | `/wake` | Trigger daemon cycle immediately |
| GET | `/events` | SSE real-time events |

---

## Scheduling Syntax

| Format | Example | Meaning |
|--------|---------|---------|
| `daily_HH:MM` | `daily_09:00` | Every day at 09:00 |
| `weekly_D_HH:MM` | `weekly_0_10:00` | Every Monday at 10:00 |
| `every_Xm` | `every_30m` | Every 30 minutes |
| `every_Xh` | `every_2h` | Every 2 hours |

---

## File Structure

```
proactive/
├── launcher.py             # One-click auto-installer + server launcher
├── start.bat               # Windows launcher (double-click)
├── start.sh                # Linux/macOS launcher
├── api_server.py           # Chat API (FastAPI :8000 + React UI)
├── daemon_v2.py            # Background daemon (FastAPI :8420 + scheduler)
├── telegram_bot.py         # Telegram bot integration
├── cli.py                  # Terminal chat interface
│
├── memory.py               # SQLite memory system
├── mem_cli.py              # CLI bridge (agents call via Bash)
├── agent_config.py         # System prompt, tools, agent factory
├── embeddings.py           # Vector embedding store (sqlite-vec)
│
├── core/
│   ├── config.py           # YAML config loader + env overrides
│   ├── agent_router.py     # Claude vs OpenAI routing logic
│   └── subagent_manager.py # Parallel subagent lifecycle
│
├── agent_wrappers/
│   ├── claude_agent.py     # Claude Agent SDK wrapper
│   └── openai_agent.py     # OpenAI Agents SDK wrapper
│
├── skills/                 # Bundled skills (14 pre-installed)
│
├── react-claude-chat/      # Vite + React 18 + TypeScript + Tailwind
│   └── dist/               # Pre-built UI (no Node.js needed)
│
├── config.yaml.example     # Template (copied to config.yaml on first run)
├── config.yaml             # Your configuration (git-ignored)
├── ecosystem.config.js     # PM2 process management
└── requirements.txt        # Python dependencies
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CHECK_INTERVAL` | `300` | Seconds between daemon cycles |
| `AGENT_MAX_TASKS` | `5` | Max tasks gathered per cycle |
| `AGENT_MAX_CONCURRENT` | `3` | Max parallel tasks |
| `AGENT_API_PORT` | `8420` | Daemon HTTP port |

Environment variables override `config.yaml` values.

---

## Troubleshooting

### "Python is not installed" on start.bat
Download Python 3.11+ from https://www.python.org/downloads/ — make sure to check "Add Python to PATH" during installation.

### Port already in use
```bash
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

### Claude SDK timeout on Windows
The system uses non-streaming `query()` to avoid this. Update the SDK if issues persist:
```bash
pip install --upgrade claude-agent-sdk
```

### React UI not showing
The UI is pre-built in `react-claude-chat/dist/`. If it's missing, rebuild:
```bash
cd react-claude-chat && npm install && npm run build
```

---

## Cost Considerations

Each daemon cycle uses ~1000-5000 tokens. With 5-minute intervals: ~288 cycles/day.

**Recommendations:**
- Production: 10-30 minute intervals (`--env production`)
- Stop daemon when idle: `pm2 stop agent-daemon`
- Auto-routing sends simple tasks to GPT-4.1-mini (cheapest)

---

## License

Proprietary. All rights reserved.

**Author:** Dr. Stefanos Drakos
**Repository:** [github.com/sdrakos/AgelClaw](https://github.com/sdrakos/AgelClaw)
