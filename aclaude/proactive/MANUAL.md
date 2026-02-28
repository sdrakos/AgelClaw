# AgelClaw Proactive Agent — Complete Manual

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Running the System](#6-running-the-system)
7. [Web Chat UI](#7-web-chat-ui)
8. [Telegram Bot](#8-telegram-bot)
9. [Background Daemon](#9-background-daemon)
10. [Multi-Provider Routing](#10-multi-provider-routing)
11. [Subagents](#11-subagents)
12. [Skills System](#12-skills-system)
13. [Memory System](#13-memory-system)
14. [API Reference](#14-api-reference)
15. [PM2 Production Setup](#15-pm2-production-setup)
16. [Troubleshooting](#16-troubleshooting)
17. [File Reference](#17-file-reference)

---

## 1. Overview

AgelClaw Proactive Agent is an autonomous AI assistant system with:

- **Multi-provider support**: Routes tasks between Claude (Anthropic) and OpenAI (GPT-4.1)
- **Web Chat UI**: React-based chat interface at `http://localhost:8000`
- **Telegram Bot**: Chat with the agent via Telegram
- **Background Daemon**: Processes scheduled and pending tasks automatically
- **Persistent Memory**: SQLite database stores conversations, tasks, learnings, user profile
- **Skills System**: Self-creating and reusable skill templates
- **Subagents**: Spawn parallel AI agents for complex tasks
- **Auto-routing**: Automatically picks the best provider per task type

### How it works (simplified)

```
User (Web/Telegram)
    |
    v
API Server (port 8000)          Telegram Bot
    |                               |
    v                               v
Agent Router -----> Claude Agent SDK (streaming)
    |                    or
    +-------------> OpenAI Agents SDK (full response)
    |
    v
Memory (SQLite) <---- Daemon (port 8420, background tasks)
    |
    v
Skills (.Claude/Skills/)
```

---

## 2. Architecture

### Processes

The system runs as **3 independent processes** (+ optional 4th):

| Process | Script | Port | Purpose |
|---------|--------|------|---------|
| API Server | `api_server.py` | 8000 | Web Chat API + React UI |
| Daemon | `daemon_v2.py` | 8420 | Background task execution |
| Telegram Bot | `telegram_bot.py` | — | Telegram chat interface |
| Email Digest | `outlook_digest.py` | — | Optional email notifications |

### Key Components

```
proactive/
  |
  +-- core/                    # Core engine
  |   +-- config.py            # YAML config loader + env overrides
  |   +-- agent_router.py      # Claude vs OpenAI routing
  |   +-- subagent_manager.py  # Parallel subagent lifecycle
  |
  +-- agent_wrappers/          # Provider-specific agent implementations
  |   +-- base_agent.py        # Abstract interface
  |   +-- claude_agent.py      # Claude Agent SDK wrapper
  |   +-- openai_agent.py      # OpenAI Agents SDK wrapper
  |   +-- openai_tools.py      # Tool implementations for OpenAI (Bash, Read, Write, etc.)
  |
  +-- agent_config.py          # System prompt + shared config
  |   +-- SYSTEM_PROMPT        # Agent instructions (memory, skills, subagents)
  |   +-- get_agent()          # Factory: returns ClaudeAgent or OpenAIAgent
  |   +-- get_router()         # Singleton AgentRouter
  |
  +-- memory.py                # SQLite memory system
  +-- mem_cli.py               # CLI bridge (agents call this via Bash)
  +-- skill_tools.py           # Skill CRUD operations
  +-- memory_tools.py          # Memory tool definitions
  |
  +-- api_server.py            # FastAPI: chat, config, subagents, skills
  +-- daemon_v2.py             # Background task processor
  +-- telegram_bot.py          # Telegram integration
  |
  +-- config.yaml              # User configuration
  +-- data/agent_memory.db     # SQLite database
  +-- react-claude-chat/       # React frontend
  +-- logs/                    # Process logs
  +-- reports/                 # Generated reports
```

### Data Flow

1. **User sends message** (Web UI or Telegram)
2. **Conversation history** loaded from SQLite (shared across channels)
3. **Agent Router** picks provider (Claude/OpenAI) based on config + task type
4. **Agent wrapper** executes the query with tools (Bash, Read, Write, Skills, etc.)
5. **Response streamed** back to user (Claude: real-time SSE, OpenAI: single response)
6. **Conversation saved** to SQLite memory

---

## 3. Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for React UI build, optional)
- **At least one API key**: Anthropic (Claude) or OpenAI
- **PM2** (optional, for production process management)

### Python packages

```
claude-agent-sdk    # Claude Agent SDK
openai-agents       # OpenAI Agents SDK
fastapi             # Web framework
uvicorn             # ASGI server
httpx               # HTTP client
pyyaml              # YAML config
python-dotenv       # .env file loading
python-telegram-bot # Telegram integration
```

---

## 4. Installation

### Quick Install

```bash
cd C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive
python install.py
```

This will:
1. Check Python version (3.11+)
2. Install all pip dependencies from `requirements.txt`
3. Create `data/`, `logs/`, `reports/` directories
4. Build React UI (if Node.js available)
5. Run the setup wizard interactively

### Manual Install

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Create directories
mkdir data logs reports

# 3. Build React UI (optional)
cd react-claude-chat
npm install
npm run build
cd ..

# 4. Configure
python setup_wizard.py
```

---

## 5. Configuration

Configuration comes from **two sources** (env vars override YAML):

### config.yaml

```yaml
anthropic_api_key: ""        # or set ANTHROPIC_API_KEY env var
openai_api_key: ""           # or set OPENAI_API_KEY env var
default_provider: "auto"     # claude | openai | auto
telegram_bot_token: ""       # or set TELEGRAM_BOT_TOKEN env var
telegram_allowed_users: ""   # comma-separated Telegram user IDs
api_port: 8000
daemon_port: 8420
cost_limit_daily: 10.00
max_concurrent_tasks: 3
check_interval: 300          # daemon cycle interval in seconds
```

### .env file

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
TELEGRAM_BOT_TOKEN=7000000000:AAH...
TELEGRAM_ALLOWED_USERS=123456789
```

### Priority order

```
Environment variables  >  config.yaml  >  defaults
```

If `ANTHROPIC_API_KEY` is set in both `.env` and `config.yaml`, the `.env` value wins.

### Setup Wizard

Run interactively to configure everything:

```bash
python setup_wizard.py
```

It will prompt for:
1. API keys (Anthropic and/or OpenAI)
2. Default provider preference (claude / openai / auto)
3. Telegram bot token (optional)
4. Port settings
5. Cost and concurrency limits

---

## 6. Running the System

### Development (3 separate terminals)

**Terminal 1 — API Server:**
```bash
cd C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive
python api_server.py
```
Output:
```
Starting API server on http://localhost:8000 [PRODUCTION]
  Serving React build from ...\react-claude-chat\dist
  Daemon proxy: /daemon/* -> localhost:8420
```

**Terminal 2 — Daemon:**
```bash
cd C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive
python daemon_v2.py
```
Output:
```
Agent Daemon v2 starting (parallel execution)
   API: http://localhost:8420
   Interval: 300s
   Max concurrent: 3
```

**Terminal 3 — Telegram Bot:**
```bash
cd C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive
python telegram_bot.py
```
Output:
```
Starting Telegram bot...
Bot is running. Press Ctrl+C to stop.
```

### Production (PM2)

```bash
cd C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive
pm2 start ecosystem.config.js
pm2 status
pm2 logs
```

PM2 manages all 3 processes (+ optional email digest) with auto-restart.

### Verify Everything Works

```bash
# Health check
curl http://localhost:8000/api/health

# Config (no secrets)
curl http://localhost:8000/api/config

# Chat with auto-routing
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"hello\"}"

# Chat with specific provider
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"hello\", \"provider\": \"openai\"}"

# Daemon status
curl http://localhost:8420/status

# Task stats
curl http://localhost:8000/api/stats
```

---

## 7. Web Chat UI

### Access

Open **http://localhost:8000** in your browser.

The React UI connects to the API server and provides:
- Real-time chat with streaming responses (Claude) or full responses (OpenAI)
- Tool use visibility (shows when agent uses Bash, Read, Write, etc.)
- Sidebar with task stats, skills, daemon status
- Provider indicator (shows which AI is responding)

### Development Mode (with hot reload)

```bash
# Terminal 1: API server
python api_server.py

# Terminal 2: React dev server (separate)
cd react-claude-chat
npm run dev
```
- React dev server: http://localhost:3000 (proxies API calls to :8000)
- Vite handles hot module replacement

### Production Mode

```bash
cd react-claude-chat
npm run build
cd ..
python api_server.py
```
- API server serves the React build from `react-claude-chat/dist/`
- Everything runs on http://localhost:8000

### Chat API Format

The chat endpoint streams **Server-Sent Events (SSE)**:

```
POST /api/chat
Content-Type: application/json

{
  "message": "your message here",
  "provider": "claude"    // optional: "claude" | "openai" | "auto" | null
}
```

SSE events received:
```
data: {"type": "provider", "provider": "claude", "model": "claude-sonnet-4-5-20250929"}
data: {"type": "text", "content": "Hello! "}
data: {"type": "text", "content": "How can I help?"}
data: {"type": "tool", "name": "Bash"}
data: {"type": "text", "content": "I ran the command..."}
data: [DONE]
```

---

## 8. Telegram Bot

### Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get the bot token
3. Add it to `.env` or `config.yaml`:
   ```
   TELEGRAM_BOT_TOKEN=7000000000:AAHxxxxxxxxx
   ```
4. (Optional) Restrict to specific users:
   ```
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   ```
   Leave empty to allow all users.

### Running

```bash
python telegram_bot.py
```

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/status` | Task statistics |
| `/skills` | List installed skills |
| `/tasks` | View pending tasks |
| Any text | Chat with the agent |

### How It Works

1. User sends a message on Telegram
2. Conversation history loaded from shared SQLite memory
3. Agent Router picks provider (same as web chat)
4. **Claude**: streams progress updates ("Working: Running command...", "Working: Reading file... (step 3)")
5. **OpenAI**: shows single progress message ("Processing with OpenAI (gpt-4.1)...")
6. Response sent back as Telegram message (auto-split if > 4096 chars)
7. Conversation saved to shared memory

### Shared Memory

Web Chat and Telegram share the **same conversation history**. If you discuss something on Telegram, the web chat agent knows about it too.

---

## 9. Background Daemon

### What It Does

The daemon runs autonomously in the background:
- Checks for **due tasks** (scheduled tasks whose time has come)
- Checks for **pending tasks** (manually created tasks waiting execution)
- Executes tasks in **parallel** (up to `max_concurrent_tasks`)
- Each task gets its own independent AI agent query
- Sends **email notifications** when tasks complete
- Emits **SSE events** for real-time UI monitoring

### Task Lifecycle

```
pending  -->  in_progress  -->  completed
                |
                +--> failed (retryable)
```

### Creating Tasks

**Via Web Chat or Telegram:**
```
"add task: Scrape competitor prices daily"
```
The agent will create a recurring task automatically.

**Via API:**
```bash
curl -X POST http://localhost:8420/task \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Scrape competitor prices",
    "description": "Check prices on sites X, Y, Z",
    "priority": 2,
    "wake_agent": true
  }'
```

**Scheduled/Recurring:**
```bash
curl -X POST http://localhost:8420/task \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Daily email digest",
    "description": "Run outlook email summary",
    "priority": 3,
    "due_at": "2026-02-24T09:00:00",
    "recurring_cron": "daily_09:00"
  }'
```

Recurring formats:
- `daily_HH:MM` — every day at HH:MM
- `weekly_D_HH:MM` — every week (0=Mon, 6=Sun)
- `every_Xm` — every X minutes
- `every_Xh` — every X hours

### Task with Provider Override

Tasks can specify which provider to use:
```bash
curl -X POST http://localhost:8420/task \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Research market trends",
    "description": "Analyze AI market trends for Q1 2026",
    "priority": 3,
    "context": {"provider": "openai"}
  }'
```

### Smart Scheduling

The daemon doesn't just sleep for a fixed interval. It calculates when the next scheduled task is due and wakes up at exactly the right time. If a task is due in 30 seconds, it sleeps 30 seconds (not 300).

### Monitoring

**SSE Events (real-time):**
```bash
curl -N http://localhost:8420/events
```

Events: `cycle_start`, `task_start`, `agent_text`, `tool_use`, `task_end`, `task_error`, `cycle_end`

**Status endpoint:**
```bash
curl http://localhost:8420/status
```

Returns:
```json
{
  "agent": {
    "state": "running",
    "running_tasks": {
      "5": {"title": "Scrape prices", "started_at": "..."}
    }
  },
  "tasks": {"pending": 3, "in_progress": 1, "completed": 42}
}
```

---

## 10. Multi-Provider Routing

### Providers

| Provider | Models | Best For |
|----------|--------|----------|
| Claude | claude-sonnet-4-5 | Code, refactoring, debugging, general tasks |
| OpenAI | gpt-4.1 | Research, analysis, web search |
| OpenAI | gpt-4.1-mini | Simple/chat tasks (fast, cheap) |

### Routing Modes

**`default_provider: "claude"`** — All tasks go to Claude

**`default_provider: "openai"`** — All tasks go to OpenAI

**`default_provider: "auto"`** — Smart routing by task type:

| Task Type | Provider | Model | Why |
|-----------|----------|-------|-----|
| code | Claude | claude-sonnet-4-5 | Best at code generation |
| debug | Claude | claude-sonnet-4-5 | Best at debugging |
| refactor | Claude | claude-sonnet-4-5 | Best at refactoring |
| research | OpenAI | gpt-4.1 | Good at research synthesis |
| web_search | OpenAI | gpt-4.1 | Better web integration |
| analysis | OpenAI | gpt-4.1 | Good at data analysis |
| simple | OpenAI | gpt-4.1-mini | Fast, cheap for simple tasks |
| chat | OpenAI | gpt-4.1-mini | Fast for conversation |
| general | Claude | claude-sonnet-4-5 | Default to Claude |

### Fallback

If the requested provider's API key is missing, the router automatically falls back to the other one:
- Requested Claude but no Anthropic key → uses OpenAI
- Requested OpenAI but no OpenAI key → uses Claude
- No keys at all → defaults to Claude (may use local config)

### Per-Request Override

In web chat:
```json
{"message": "explain this code", "provider": "claude"}
```

In daemon tasks:
```json
{"title": "...", "context": {"provider": "openai"}}
```

### Check Current Routing

```bash
curl http://localhost:8000/api/config
```
Returns:
```json
{
  "default_provider": "auto",
  "available_providers": ["claude", "openai"],
  "has_claude_key": true,
  "has_openai_key": true
}
```

---

## 11. Subagents

Subagents are independent AI agents spawned for parallel task execution.

### When to Use

- Split complex tasks into independent subtasks
- Research multiple topics simultaneously
- Generate code and tests in parallel
- Any "do X and Y at the same time" scenario

### API

**Create a subagent:**
```bash
curl -X POST http://localhost:8000/api/subagents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "research-pricing",
    "prompt": "Research competitor pricing for product X",
    "provider": null,
    "task_type": "research",
    "max_turns": 30
  }'
```
Response: `{"id": "a1b2c3d4", "status": "running", "provider": "openai", "model": "gpt-4.1"}`

**List subagents:**
```bash
curl http://localhost:8000/api/subagents
curl http://localhost:8000/api/subagents?status=running
```

**Get result:**
```bash
curl http://localhost:8000/api/subagents/a1b2c3d4
```
Returns full result, status, cost estimate, etc.

**Cancel:**
```bash
curl -X DELETE http://localhost:8000/api/subagents/a1b2c3d4
```

**SSE Events:**
```bash
curl -N http://localhost:8000/api/subagents/events
```
Events: `subagent_start`, `subagent_end`, `subagent_error`

### Example: Parallel Research

```bash
# Spawn 3 research subagents simultaneously
curl -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
  -d '{"name": "market-size", "prompt": "Research AI market size 2026", "task_type": "research"}'

curl -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
  -d '{"name": "competitors", "prompt": "List top 10 AI agent competitors", "task_type": "research"}'

curl -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
  -d '{"name": "trends", "prompt": "Identify key AI agent trends for 2026", "task_type": "research"}'

# Wait, then get results
curl http://localhost:8000/api/subagents
```

### The Agent Uses Subagents Too

The system prompt instructs the agent to create subagents via curl when it encounters complex tasks. It can:
1. Analyze the task
2. Split into independent subtasks
3. Spawn subagents via the API
4. Poll results
5. Combine into a final answer

---

## 12. Skills System

Skills are reusable task templates that the agent creates and follows.

### Where Skills Live

- **Project skills**: `aclaude/.Claude/Skills/<skill-name>/`
- **User skills**: `~/.claude/skills/<skill-name>/`

### Skill Structure

```
.Claude/Skills/my-skill/
  SKILL.md          # Instructions (YAML frontmatter + markdown body)
  scripts/          # Executable scripts
    main.py
    helper.sh
  references/       # Reference docs, API schemas, etc.
    api_docs.md
```

### CLI Commands

```bash
# List all skills
python mem_cli.py skills

# Find a skill matching a description
python mem_cli.py find_skill "send email via Outlook"

# Get full skill content
python mem_cli.py skill_content outlook-email-digest

# Create a new skill
python mem_cli.py create_skill my-scraper "Web scraper skill" "## Instructions\n1. Use requests..."

# Add a script to a skill
python mem_cli.py add_script my-scraper scraper.py "import requests\n..."

# Add a reference document
python mem_cli.py add_ref my-scraper api_docs.md "# API Documentation\n..."

# Update skill body
python mem_cli.py update_skill my-scraper "## Updated Instructions\n..."
```

### Skill-First Execution

The agent follows a **skill-first** pattern for every task:

1. Search for existing skill: `find_skill "<task>"`
2. If found: load it and follow instructions
3. If not found:
   a. Research the topic
   b. Create a new skill with instructions + scripts
   c. Execute using the skill
4. Update skill if improvements discovered

This means the agent gets **better over time** — it never solves the same problem from scratch twice.

### Installed Skills (examples)

| Skill | Description |
|-------|-------------|
| outlook-email-digest | Daily Outlook email summaries |
| task-completion-notifier | Email notifications on task completion |
| openai-agents-sdk | OpenAI Agents SDK documentation |
| claude-sdk-subagents | Claude subagent patterns |

---

## 13. Memory System

### SQLite Database

Location: `proactive/data/agent_memory.db`

### Tables

| Table | Purpose |
|-------|---------|
| tasks | All tasks (pending, in_progress, completed, failed) |
| conversations | Chat history (shared across web + telegram) |
| skills | Installed skills registry |
| learnings | Agent discoveries and patterns (+ `is_rule` for hard rules) |
| kv_store | Key-value storage (daemon state, etc.) |
| user_profile | User facts organized by category |

### Memory CLI

```bash
# Full context summary (profile + recent conversations + tasks)
python mem_cli.py context

# Recent conversations
python mem_cli.py conversations 10

# Search conversations by keyword
python mem_cli.py conversations "email" 5

# Task management
python mem_cli.py pending
python mem_cli.py due
python mem_cli.py scheduled
python mem_cli.py stats

# User profile
python mem_cli.py profile
python mem_cli.py profile work
python mem_cli.py set_profile work tech_stack "Python, React, FastAPI" 0.9 stated
python mem_cli.py del_profile work old_key

# Learnings
python mem_cli.py add_learning "python" "Use asyncio.gather for parallel tasks"
python mem_cli.py get_learnings python

# Hard Rules (promoted learnings injected into system prompt)
python mem_cli.py rules                     # List active hard rules
python mem_cli.py promote_rule <id>         # Promote learning → hard rule
python mem_cli.py demote_rule <id>          # Demote rule → regular learning
```

### Hard Rules

Learnings can be promoted to **hard rules** — these are injected directly into the agent's system prompt as a `## HARD RULES` section, ensuring they are always followed.

```bash
# List all active rules
python mem_cli.py rules

# Promote a learning (by ID) to a hard rule
python mem_cli.py promote_rule 15

# Demote back to a regular learning
python mem_cli.py demote_rule 15
```

Hard rules appear in every system prompt (both chat and daemon) via `memory.build_rules_prompt()`. Use this for critical operational lessons that must never be forgotten, e.g., "always run find_skill before executing a task."

### Shared Conversation Memory

All channels (Web Chat, Telegram) write to the same `session_id = "shared_chat"`. This means:
- Start a conversation on Telegram, continue it on the web
- The agent remembers everything regardless of channel
- Keyword search works across all conversations

### User Profile

The agent learns about the user over time:

| Category | Examples |
|----------|----------|
| identity | name, email, company, role |
| work | projects, tech_stack, clients |
| preferences | language, schedule, communication_style |
| relationships | colleagues, contacts |
| habits | working_hours, common_requests |
| interests | topics, hobbies |

---

## 14. API Reference

### API Server (port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Public config (no secrets) |
| GET | `/api/stats` | Task statistics |
| GET | `/api/skills` | Installed skills list |
| GET | `/api/daemon-url` | Daemon SSE endpoint URL |
| POST | `/api/chat` | Chat with agent (SSE streaming) |
| GET | `/api/subagents` | List subagents |
| POST | `/api/subagents` | Create and run subagent |
| GET | `/api/subagents/{id}` | Get subagent details/result |
| DELETE | `/api/subagents/{id}` | Cancel running subagent |
| GET | `/api/subagents/events` | SSE stream for subagent events |
| GET | `/daemon/{path}` | Proxy to daemon API |

### Daemon API (port 8420)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/task` | Submit a new task |
| GET | `/status` | Daemon state + task stats |
| GET | `/tasks?status=pending` | List tasks by status |
| GET | `/tasks/{id}` | Get task with conversation history |
| DELETE | `/tasks/{id}` | Cancel a pending task |
| GET | `/scheduled` | Future scheduled tasks |
| POST | `/wake` | Trigger daemon cycle immediately |
| GET | `/events` | SSE real-time events |
| GET | `/history` | Recent conversation history |
| GET | `/learnings` | Agent learnings |
| GET | `/skills` | Installed skills |

---

## 15. PM2 Production Setup

### ecosystem.config.js

The project includes a PM2 config that manages all processes:

```bash
# Start everything
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs                    # All processes
pm2 logs agent-api          # API server only
pm2 logs agent-daemon       # Daemon only
pm2 logs telegram-bot       # Telegram bot only

# Restart
pm2 restart all
pm2 restart agent-api

# Stop
pm2 stop all

# Auto-start on Windows boot
pm2 save
pm2-startup install
```

### Processes managed:

| PM2 Name | Script | Port |
|----------|--------|------|
| agent-api | api_server.py | 8000 |
| agent-daemon | daemon_v2.py | 8420 |
| telegram-bot | telegram_bot.py | — |
| email-digest | outlook_digest.py | — |

---

## 16. Troubleshooting

### Port already in use (Error 10048)

```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**Fix**: Kill the process using the port:
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill it (replace PID with actual number)
taskkill /F /PID <PID>

# Or kill all Python processes
taskkill /F /IM python.exe
```

### No API keys configured

```bash
# Check what keys are available
python -c "from core.config import load_config; cfg = load_config(); print('Claude:', bool(cfg.get('anthropic_api_key'))); print('OpenAI:', bool(cfg.get('openai_api_key')))"
```

Make sure keys are in `.env` or `config.yaml`.

### Telegram bot not responding

1. Check the token is correct in `.env`
2. Check `TELEGRAM_ALLOWED_USERS` — if set, only those users can interact
3. Check logs: `pm2 logs telegram-bot` or terminal output

### Claude Agent SDK timeout

On Windows, streaming mode may timeout. The system uses non-streaming `query()` for the daemon, which works reliably. If chat streaming fails, check that `claude-agent-sdk` is up to date:
```bash
pip install --upgrade claude-agent-sdk
```

### OpenAI agent errors

```bash
# Verify OpenAI SDK is installed
python -c "from agents import Agent; print('OK')"

# Check key
python -c "from core.config import load_config; print(load_config().get('openai_api_key', '')[:10])"
```

### Database locked

If multiple processes clash on SQLite:
```bash
# The system uses WAL mode to prevent this, but if it happens:
# Stop all processes, then restart them
pm2 stop all
pm2 start ecosystem.config.js
```

### React UI not showing

```bash
# Check if build exists
ls react-claude-chat/dist/

# If not, build it
cd react-claude-chat
npm install
npm run build
cd ..

# Restart API server
python api_server.py
```

---

## 17. File Reference

### Entry Points

| File | Purpose | Run |
|------|---------|-----|
| `api_server.py` | Web Chat API + React UI | `python api_server.py` |
| `daemon_v2.py` | Background task processor | `python daemon_v2.py` |
| `telegram_bot.py` | Telegram bot | `python telegram_bot.py` |
| `setup_wizard.py` | Interactive setup | `python setup_wizard.py` |
| `install.py` | One-click installer | `python install.py` |

### Core Modules

| File | Purpose |
|------|---------|
| `core/config.py` | Load config.yaml + .env + env vars |
| `core/agent_router.py` | Route tasks to Claude or OpenAI |
| `core/subagent_manager.py` | Manage parallel subagent lifecycle |
| `agent_config.py` | System prompt, tools, agent factory |
| `memory.py` | SQLite memory system |
| `mem_cli.py` | CLI bridge for memory/skills (used by agents via Bash) |
| `skill_tools.py` | Skill CRUD operations |
| `memory_tools.py` | Memory tool definitions |

### Agent Wrappers

| File | Purpose |
|------|---------|
| `agent_wrappers/base_agent.py` | Abstract agent interface |
| `agent_wrappers/claude_agent.py` | Claude Agent SDK wrapper |
| `agent_wrappers/openai_agent.py` | OpenAI Agents SDK wrapper |
| `agent_wrappers/openai_tools.py` | Bash, Read, Write, Grep, Glob for OpenAI |

### Configuration

| File | Purpose |
|------|---------|
| `config.yaml` | User configuration (ports, provider, limits) |
| `.env` | API keys and secrets |
| `ecosystem.config.js` | PM2 process management |

### Data

| File | Purpose |
|------|---------|
| `data/agent_memory.db` | SQLite database (tasks, conversations, skills, learnings) |
| `logs/` | Process logs (daemon, API, telegram) |
| `reports/` | Generated report files |

### Frontend

| Directory | Purpose |
|-----------|---------|
| `react-claude-chat/src/` | React TypeScript source code |
| `react-claude-chat/dist/` | Production build (served by API server) |
