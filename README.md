# AgelClaw Proactive Agent

**A self-evolving autonomous AI assistant with persistent memory, multi-provider routing, and parallel task execution.**

By **Dr. Stefanos Drakos** | [github.com/sdrakos/AgelClaw](https://github.com/sdrakos/AgelClaw)

---

## What Is This?

AgelClaw Proactive is an AI agent system that runs autonomously on your machine. It learns from every interaction, creates reusable skills, executes tasks in the background, and gets smarter over time — without cloud dependencies beyond the LLM API calls.

**Three services run together via PM2:**

| Service | Port | Description |
|---------|------|-------------|
| **API Server** | `:8000` | Web Chat UI (React) + REST API + SSE streaming |
| **Daemon** | `:8420` | Background task processor with parallel execution |
| **Telegram Bot** | — | Chat with the agent from Telegram |

All three share the same **SQLite memory database** — conversations started on the web continue seamlessly on Telegram, and the daemon knows everything discussed.

---

## Key Features

### Multi-Provider AI Routing
Routes tasks between **Claude** (Anthropic) and **OpenAI** (GPT-4.1) based on task type:
- Code tasks --> Claude Sonnet (best at code generation)
- Research/analysis --> OpenAI GPT-4.1
- Simple/chat tasks --> GPT-4.1-mini (fast & cheap)
- Force a specific provider per request, or let auto-routing decide

### Persistent Memory
SQLite database stores everything across sessions:
- **Tasks** — pending, scheduled, recurring, completed, with priorities and dependencies
- **Conversations** — shared across web, Telegram, and daemon channels
- **Learnings** — agent discoveries, promotable to hard rules
- **User Profile** — identity, work, preferences, relationships, habits
- **Skills** — reusable task templates with scripts and references
- **Semantic Search** — vector embeddings (OpenAI) for AI-powered memory recall

### Self-Evolving Skills
The agent follows a **skill-first** pattern:
1. Search for an existing skill matching the task
2. If found — follow its instructions and scripts
3. If not — research the topic, create a new skill, then execute
4. Update the skill if improvements are discovered

Skills are stored as markdown instructions + executable scripts and get better over time.

### Background Daemon (Parallel Execution)
The daemon runs tasks autonomously:
- **Parallel execution** — up to N tasks simultaneously (configurable semaphore)
- **Smart scheduling** — calculates sleep time to wake exactly when next task is due
- **Recurring tasks** — daily, weekly, or interval-based (`daily_09:00`, `every_2h`)
- **SSE event stream** — real-time monitoring from the web UI
- **Email notifications** — get notified when tasks complete
- **Auto-retry** — failed tasks retry up to `max_retries` times

### Hard Rules (Promoted Learnings)
Promote learnings to **hard rules** that are injected into every system prompt as enforceable instructions:
```bash
python mem_cli.py promote_rule 15   # Learning #15 becomes an enforced rule
python mem_cli.py rules             # List active rules
python mem_cli.py demote_rule 15    # Demote back to regular learning
```
Hard rules ensure critical lessons (e.g., "always run find_skill first") are never forgotten.

### Subagents
Spawn parallel AI agents for complex tasks:
```bash
curl -X POST http://localhost:8000/api/subagents \
  -H "Content-Type: application/json" \
  -d '{"name": "research-pricing", "prompt": "Research competitor pricing", "task_type": "research"}'
```

### User Profile & Personalization
The agent learns about the user over time:
- **Stated** facts (user told directly) — confidence 0.9
- **Inferred** facts (deduced from context) — confidence 0.6
- **Observed** patterns (repeated behavior) — confidence 0.5

Profile is injected at the top of every agent context for personalized interactions.

---

## Architecture

```
React UI (:3000 dev / :8000 prod)
  +-- POST /api/chat   -->  api_server.py  -->  Agent Router
  +-- GET /daemon/events -->  proxy  -->  daemon_v2.py SSE
  +-- static files      -->  react-claude-chat/dist/

Agent Router
  +-- Claude Agent SDK (code, general tasks)
  +-- OpenAI Agents SDK (research, analysis, simple)

daemon_v2.py (:8420)
  +-- Scheduler loop: checks memory for due/pending tasks
  +-- Each task: independent query() call (parallel via asyncio.gather)
  +-- Semaphore limits concurrency (default 3)
  +-- SSE events: cycle_start, task_start, agent_text, tool_use, task_end

Shared Memory: memory.py --> data/agent_memory.db (SQLite WAL)
  Tables: tasks, conversations, skills, learnings (+hard rules), kv_store, user_profile
```

### How the Daemon Cycle Works

```
1. Wake up (every N seconds, or instantly via POST /task or /wake)
2. Load context: user profile, pending/due tasks, skills, learnings, hard rules
3. For each due/pending task (parallel, up to max_concurrent):
   a. start_task <id>  -->  marks as in_progress
   b. find_skill  -->  check if skill exists, create if missing
   c. Execute the task (Bash, file I/O, API calls, etc.)
   d. complete_task <id> "<result>"  -->  stores outcome
   e. If recurring  -->  auto-reschedule next run
   f. If failed  -->  auto-retry (up to max_retries)
4. SSE broadcast events to connected React UIs
5. Log everything to memory
6. Calculate next wake time  -->  sleep  -->  back to step 1
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for React UI build)
- **At least one API key**: Anthropic (Claude) or OpenAI
- **PM2** (optional, for production process management): `npm install -g pm2`

---

## Quick Start

### 1. Install

```bash
cd proactive
pip install -r requirements.txt

# Build React UI
cd react-claude-chat
npm install && npm run build
cd ..
```

Or use the one-click installer:
```bash
python install.py
```

### 2. Configure

```bash
python setup_wizard.py
```

Or edit `config.yaml` directly:

```yaml
anthropic_api_key: "sk-ant-..."
openai_api_key: "sk-proj-..."
default_provider: "auto"          # auto | claude | openai
telegram_bot_token: ""            # optional
api_port: 8000
daemon_port: 8420
max_concurrent_tasks: 3
check_interval: 300               # daemon cycle interval (seconds)
```

### 3. Run

**Development (3 terminals):**
```bash
python api_server.py      # API + Web UI on :8000
python daemon_v2.py       # Daemon on :8420
python telegram_bot.py    # Telegram bot (optional)
```

**Production (PM2):**
```bash
pm2 start ecosystem.config.js
pm2 start ecosystem.config.js --env development   # 1-min cycle
pm2 start ecosystem.config.js --env production    # 10-min cycle

pm2 status        # Check processes
pm2 logs          # Live logs
pm2 monit         # CPU/RAM monitor
pm2 stop all      # Stop everything
```

### 4. Open

Navigate to **http://localhost:8000** to start chatting.

---

## Memory CLI Reference

Agents interact with memory through `mem_cli.py` via Bash. Also useful for manual inspection:

### Memory & Tasks
```bash
python mem_cli.py context                            # Full context summary
python mem_cli.py conversations [limit]              # Recent conversations
python mem_cli.py conversations "keyword" [limit]    # Search by keyword
python mem_cli.py pending [limit]                    # Pending tasks
python mem_cli.py due                                # Due now
python mem_cli.py scheduled                          # Future scheduled
python mem_cli.py stats                              # Task statistics
python mem_cli.py add_task "title" "desc" [pri] [due_at] [recurring]
python mem_cli.py start_task <id>
python mem_cli.py complete_task <id> "result"
python mem_cli.py fail_task <id> "error"
python mem_cli.py task_folder <id>                   # Get/create task folder
```

### Learnings & Hard Rules
```bash
python mem_cli.py add_learning "category" "insight"  # Add a learning
python mem_cli.py get_learnings [category]           # List learnings
python mem_cli.py rules                              # Active hard rules
python mem_cli.py promote_rule <id>                  # Learning --> hard rule
python mem_cli.py demote_rule <id>                   # Hard rule --> learning
```

### User Profile
```bash
python mem_cli.py profile [category]                                    # View
python mem_cli.py set_profile <cat> <key> "<value>" [confidence] [source]  # Upsert
python mem_cli.py del_profile <cat> <key>                               # Delete
```

### Skills
```bash
python mem_cli.py skills                             # List installed
python mem_cli.py find_skill "description"           # Find matching
python mem_cli.py skill_content <name>               # Full content
python mem_cli.py create_skill <name> "desc" "body" [location]
python mem_cli.py add_script <skill> <file> "code"
python mem_cli.py add_ref <skill> <file> "content"
python mem_cli.py update_skill <name> "body"
```

### Subagent Definitions
```bash
python mem_cli.py subagents                          # List definitions
python mem_cli.py subagent_content <name>            # Full content
python mem_cli.py create_subagent <name> "desc" "body"
```

### Semantic Search
```bash
python mem_cli.py search "query" [limit]             # Search all tables
python mem_cli.py search "query" --table conversations  # Search specific table
python mem_cli.py embed_backfill                     # Backfill embeddings
python mem_cli.py embed_stats                        # Coverage stats
```

---

## Scheduling Syntax

Used in `mem_cli.py add_task` and the daemon API:

| Format | Example | Meaning |
|--------|---------|---------|
| `daily_HH:MM` | `daily_09:00` | Every day at 09:00 |
| `weekly_D_HH:MM` | `weekly_0_10:00` | Every Monday at 10:00 (0=Mon, 6=Sun) |
| `every_Xm` | `every_30m` | Every 30 minutes |
| `every_Xh` | `every_2h` | Every 2 hours |

One-time scheduling uses ISO datetime via `due_at`: `"2026-03-01T09:00:00"`

**Examples:**
```bash
# One-time task
python mem_cli.py add_task "Generate report" "Compile Q1 results" 3

# Scheduled task
python mem_cli.py add_task "Send digest" "Email summary" 3 "2026-03-01T09:00:00"

# Recurring task (daily at 9am)
python mem_cli.py add_task "Daily digest" "Run email digest" 3 "2026-03-01T09:00:00" "daily_09:00"

# Recurring task (every 2 hours)
python mem_cli.py add_task "Check prices" "Scrape competitor prices" 2 "" "every_2h"
```

---

## API Reference

### API Server (`:8000`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Public config (no secrets) |
| GET | `/api/stats` | Task statistics |
| GET | `/api/skills` | Installed skills list |
| POST | `/api/chat` | Chat with agent (SSE streaming) |
| GET | `/api/subagents` | List subagents |
| POST | `/api/subagents` | Create and run subagent |
| GET | `/api/subagents/{id}` | Subagent details/result |
| DELETE | `/api/subagents/{id}` | Cancel running subagent |
| GET | `/api/subagents/events` | SSE stream for subagent events |
| GET | `/daemon/{path}` | Proxy to daemon API |

### Daemon (`:8420`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/task` | Submit a new task (optionally wakes daemon) |
| GET | `/status` | Daemon state + running tasks + stats |
| GET | `/tasks?status=pending` | List tasks by status |
| GET | `/tasks/{id}` | Task with conversation history |
| DELETE | `/tasks/{id}` | Cancel a pending/failed task |
| GET | `/scheduled` | Future scheduled tasks |
| POST | `/wake` | Trigger daemon cycle immediately |
| GET | `/events` | SSE real-time events |
| GET | `/history` | Recent conversation history |
| GET | `/learnings` | Agent learnings |
| GET | `/skills` | Installed skills |

---

## File Structure

```
proactive/
+-- daemon_v2.py            # Background daemon (FastAPI :8420 + scheduler + SSE)
+-- api_server.py            # Chat API (FastAPI :8000 + React UI + daemon proxy)
+-- telegram_bot.py          # Telegram bot integration
+-- cli.py                   # Terminal chat interface
|
+-- memory.py                # SQLite memory system
+-- mem_cli.py               # CLI bridge (agents call via Bash)
+-- agent_config.py          # System prompt, tools, agent factory
+-- skill_tools.py           # Skill CRUD operations (SdkMcpTool)
+-- memory_tools.py          # Memory tool definitions
+-- embeddings.py            # Vector embedding store (sqlite-vec)
|
+-- core/
|   +-- config.py            # YAML config loader + env overrides
|   +-- agent_router.py      # Claude vs OpenAI routing logic
|   +-- subagent_manager.py  # Parallel subagent lifecycle
|
+-- agent_wrappers/
|   +-- base_agent.py        # Abstract agent interface
|   +-- claude_agent.py      # Claude Agent SDK wrapper
|   +-- openai_agent.py      # OpenAI Agents SDK wrapper
|   +-- openai_tools.py      # Bash, Read, Write, Grep, Glob for OpenAI
|
+-- react-claude-chat/       # Vite + React 18 + TypeScript + Tailwind
|   +-- src/App.tsx           # Main: chat + SSE + daemon logs
|   +-- src/components/
|   |   +-- DaemonLogs.tsx    # Real-time SSE feed from daemon
|   |   +-- MessageList.tsx   # Chat messages with auto-scroll
|   |   +-- Message.tsx       # Markdown rendering (react-markdown)
|   |   +-- InputArea.tsx     # Chat input (Enter=send, Shift+Enter=newline)
|   |   +-- Header.tsx        # App header + logs toggle
|   |   +-- Sidebar.tsx       # Skills, tasks, stats sidebar
|   |   +-- ModelsPage.tsx    # Provider model selection
|   |   +-- SkillsPage.tsx    # Skills browser
|   +-- dist/                 # Production build (served by api_server)
|   +-- vite.config.ts        # Proxy: /api-->:8000, /daemon-->:8420
|
+-- subagents/               # Persistent subagent definitions (SUBAGENT.md + scripts/)
+-- tasks/                   # Task working folders (task_<id>/)
+-- reports/                 # Generated reports
+-- logs/                    # Process logs
+-- data/agent_memory.db     # SQLite database
+-- config.yaml              # User configuration
+-- ecosystem.config.js      # PM2 process management
+-- requirements.txt         # Python dependencies
+-- install.py               # One-click installer
+-- setup_wizard.py          # Interactive setup wizard
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CHECK_INTERVAL` | `300` | Seconds between daemon cycles |
| `AGENT_MAX_TASKS` | `5` | Max tasks gathered per cycle |
| `AGENT_MAX_CONCURRENT` | `3` | Max parallel tasks |
| `AGENT_API_PORT` | `8420` | Daemon HTTP port |
| `AGENT_WEBHOOK_URL` | _(empty)_ | POST cycle summaries to this URL |

Environment variables override `config.yaml` values.

---

## Key Design Decisions

- **Non-streaming SDK on Windows.** Claude Agent SDK streaming (`--input-format stream-json`) has initialization timeouts on Windows. All services use non-streaming `query(prompt=string)`. MCP tools are replaced by `mem_cli.py` called via Bash.
- **Skill-first execution.** Before any task, agents search for a matching skill. If none exists, they create one first, then execute. This means the agent gets better over time.
- **Smart scheduling.** The daemon calculates the exact sleep time until the next due task instead of sleeping a fixed interval. A task due in 30 seconds won't wait 5 minutes.
- **Hard rules.** Critical learnings are promoted to hard rules and injected into every system prompt, ensuring they're always enforced — not just passively listed in context.
- **Agent autonomy.** All system prompts include: "NEVER ASK THE USER TO RUN COMMANDS." Agents execute, install, and schedule everything themselves.
- **Shared conversation memory.** Web Chat, Telegram, and Daemon all write to the same `session_id = "shared_chat"`. Start a conversation on Telegram, continue it on the web.
- **User personalization.** Profile facts are injected at the top of every agent context. Agents automatically learn and save new facts from conversations.

---

## Troubleshooting

### Port already in use
```bash
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

### Claude SDK timeout on Windows
The system already uses non-streaming `query()` for the daemon. For chat streaming issues, update the SDK:
```bash
pip install --upgrade claude-agent-sdk
```

### Database locked
SQLite uses WAL mode to prevent this. If it still happens:
```bash
pm2 stop all && pm2 start ecosystem.config.js
```

### React UI not showing
```bash
cd react-claude-chat && npm install && npm run build && cd ..
python api_server.py
```

### No API keys configured
```bash
python -c "from core.config import load_config; c = load_config(); print('Claude:', bool(c.get('anthropic_api_key'))); print('OpenAI:', bool(c.get('openai_api_key')))"
```

---

## Cost Considerations

Each daemon cycle uses ~1000-5000 tokens minimum (context loading). With 5-minute intervals: ~288 cycles/day.

**Recommendations:**
- Production: 10-30 minute intervals (`--env production`)
- Use `pm2 stop agent-daemon` when no pending tasks
- Check task queue: `python mem_cli.py stats`
- Auto-routing sends simple tasks to GPT-4.1-mini (cheapest)

---

## License

Proprietary. All rights reserved.

**Author:** Dr. Stefanos Drakos
**Repository:** [github.com/sdrakos/AgelClaw](https://github.com/sdrakos/AgelClaw)
