# AgelClaw v3.1 — Architecture Reference

## Overview

AgelClaw is a self-evolving autonomous assistant with multi-provider AI support (Claude + OpenAI), persistent memory, dynamic skills, subagents, and MCP servers. It runs as a Python package installed via pip, with 4 interfaces: Web UI, CLI, Telegram bot, and background daemon.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER MACHINE                                │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  AgelClaw (Python package: src/agelclaw/)                     │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐    │  │
│  │  │  Web UI +   │  │   Daemon     │  │  Telegram Bot     │    │  │
│  │  │  API Server │  │   :8420      │  │  (optional)       │    │  │
│  │  │  :8000      │  │              │  │                   │    │  │
│  │  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘    │  │
│  │         │                │                    │               │  │
│  │         ▼                ▼                    ▼               │  │
│  │  ┌────────────────────────────────────────────────────────┐   │  │
│  │  │              Agent Config + Router                      │   │  │
│  │  │  get_system_prompt() → build_prompt_with_history()      │   │  │
│  │  │  route(task_type) → RouteResult(provider, model)        │   │  │
│  │  └───────────────────────┬────────────────────────────────┘   │  │
│  │                          │                                    │  │
│  │             ┌────────────┼────────────┐                       │  │
│  │             ▼            ▼            ▼                        │  │
│  │          ┌──────┐  ┌──────────┐  ┌──────────┐                │  │
│  │          │Claude│  │  OpenAI  │  │  Script  │                │  │
│  │          │Agent │  │  Agent   │  │  Runner  │                │  │
│  │          │ SDK  │  │   SDK    │  │(subprocess│                │  │
│  │          └──────┘  └──────────┘  └──────────┘                │  │
│  │                          │                                    │  │
│  │             ┌────────────┼────────────┐                       │  │
│  │             ▼            ▼            ▼                        │  │
│  │  ┌──────────────┐ ┌────────────┐ ┌─────────────────┐         │  │
│  │  │ SQLite Memory│ │  Skills    │ │  MCP Servers    │         │  │
│  │  │ (WAL mode)   │ │ .Claude/   │ │  mcp_servers/   │         │  │
│  │  │ tasks, convos│ │ Skills/    │ │  (stdio pipes)  │         │  │
│  │  │ learnings,   │ │            │ │                 │         │  │
│  │  │ rules, kv,   │ │            │ │                 │         │  │
│  │  │ profile      │ │            │ │                 │         │  │
│  │  └──────────────┘ └────────────┘ └─────────────────┘         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Project Dir: ~/.agelclaw/ or AGELCLAW_HOME or cwd w/ config.yaml  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Services

### 1. API Server (`:8000`) — `api_server.py`

FastAPI backend serving the React chat UI and proxying daemon requests.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | SSE streaming chat (Claude or OpenAI) |
| `/api/upload` | POST | File upload + agent analysis |
| `/api/settings` | GET/POST | Config management |
| `/api/skills` | GET | Installed skills list |
| `/api/subagents` | CRUD | Subagent lifecycle + SSE events |
| `/daemon/*` | Proxy | Forward to daemon :8420 (503 if offline) |
| `/` | Static | React chat UI (`react-claude-chat/dist/`) |

### 2. Daemon (`:8420`) — `daemon.py`

Background task processor with fire-and-forget execution.

```
scheduler_loop()
  ├── sleep until next due task or CHECK_INTERVAL
  ├── run_agent_cycle()
  │     ├── gather due + pending tasks
  │     ├── for each task: asyncio.create_task(execute_*)
  │     └── Semaphore limits concurrency (max_concurrent_tasks)
  ├── _maybe_run_heartbeat()
  └── loop
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/task` | POST | Add task + wake scheduler |
| `/wake` | POST | Wake scheduler (no new task) |
| `/events` | GET | SSE stream (task_start, task_end, task_error, agent_text, tool_use) |
| `/status` | GET | Daemon health + stats |
| `/tasks` | GET | Running task list |
| `/scheduled` | GET | Future scheduled tasks |
| `/running` | GET | Currently executing tasks |
| `/cancel/{id}` | POST | Cancel running task |

**Task execution flow:**
1. `scheduler_loop` picks up due/pending tasks
2. Marks `in_progress` in DB before launching
3. `execute_single_task()` for global tasks, `execute_subagent_task()` for assigned tasks
4. Claude path: builds `AgentDefinition` + `ClaudeAgentOptions`, calls `query()`
5. OpenAI path: builds `Agent` + `Runner.run()`
6. Script path: `subprocess.run()` directly (no AI)
7. Safety net: if agent didn't call `complete_task`, daemon does it
8. Telegram notification on completion/failure

**Safety mechanisms:**
- **Watchdog** (`_watchdog_loop`): Runs every 30s, force-kills tasks exceeding timeout + 20% grace
- **Stale cleanup** (`_cleanup_stale_tasks`): Resets stuck `in_progress` tasks on startup
- **Auto-retry**: Subagents with `max_retries > 0` get re-queued on failure
- **Inactivity timeout**: Kills tasks that stop producing messages (default 360s)

### 3. Telegram Bot — `telegram_bot.py`

- Uses `python-telegram-bot` async
- `telegram_allowed_users` whitelist (config.yaml)
- Terminal logging: `[Query start]`, `[Tool #N]`, `[Agent]`, `[Query done]`
- Memory context isolation for group chats
- Notification splitting (4096 char limit per message)

### 4. CLI — `cli.py`

- Interactive chat with streaming query + task management
- Uses same unified system prompt as all interfaces
- Auto-starts daemon on launch

---

## Multi-Provider Routing

`core/agent_router.py` — Routes tasks to the optimal AI provider/model.

| Task Type | Provider | Model | When |
|-----------|----------|-------|------|
| `code` | Claude | `claude-sonnet-4-20250514` | Code writing, debugging |
| `debug` | Claude | `claude-opus-4-0-20250514` | Complex debugging |
| `research` | OpenAI | `gpt-4.1` | Web search, data gathering |
| `simple` | OpenAI | `gpt-4.1-mini` | Quick questions |
| `chat` | Claude | `claude-sonnet-4-20250514` | General conversation |
| `auto` | — | — | Heuristic: keywords in prompt |

**Fallback logic:** If preferred provider has no API key, falls back to available provider. `default_provider` in config.yaml overrides all routing.

**Provider wrappers** (`agent_wrappers/`):
- `claude_agent.py` — Claude SDK `query(prompt=string)` (non-streaming on Windows)
- `openai_agent.py` — OpenAI Agents SDK `Agent` + `Runner.run()`
- Both implement `base_agent.py` abstract interface

---

## Subagent System

Subagents are specialized AI agents defined in `subagents/<name>/SUBAGENT.md`.

### SUBAGENT.md Format

```yaml
---
name: example
description: What this subagent does
provider: claude          # claude | openai | auto
task_type: general        # general | code | research | script
tools: Bash,Read,Write    # Available tools
mcp_servers: [aade]       # Additional MCP servers to load
timeout: 1800             # Override global timeout (seconds)
inactivity_timeout: 600   # Override inactivity timeout
max_turns: 50             # Max agent turns
max_retries: 1            # Auto-retry on failure
command: python script.py # For task_type: script only
---

# Instructions for the subagent
...
```

### Task Types

| Type | Execution | Use Case | Speed |
|------|-----------|----------|-------|
| `script` | `subprocess.run(command)` | Fixed CLI command, no AI needed | ~3s |
| `general` | Full AI agent with tools/MCP | Needs judgment, creativity | ~60-120s |
| `code` | AI routed to Claude Opus | Coding tasks | ~60-120s |
| `research` | AI routed to OpenAI GPT-4.1 | Web search, analysis | ~60-120s |

### Dynamic MCP Tool Injection

When a subagent task runs, `_get_mcp_tools_for_prompt()` reads `SERVER.md` for each loaded MCP server, parses the tools list, and injects a formatted section into the `AgentDefinition.prompt`:

```
## AVAILABLE MCP TOOLS (use directly — no ToolSearch needed)
### aade
- `mcp__aade__send_invoice` — Send invoice to AADE myDATA
- `mcp__aade__get_invoices` — Retrieve sent or received invoices
...
```

This eliminates ToolSearch overhead (~60s saved per task).

### Task Flow

```
User: "Στείλε λογιστικό report"
  → Chat agent recognizes → agelclaw-mem add_subagent_task aade-accounting "..." "..."
  → Daemon picks up task
  → execute_subagent_task()
  → Result logged to shared_chat session
  → Telegram notification
```

### Installed Subagents

Located in `subagents/` under the project directory:

| Name | Type | Description |
|------|------|-------------|
| `aade` | general | AADE myDATA invoice management (AI agent with MCP) |
| `aade-accounting` | script | Daily accounting report (subprocess, ~3s) |
| `coder` | code | General coding tasks (Claude Opus) |
| *(user-created)* | *varies* | Created via `agelclaw-mem create_subagent` |

---

## MCP Server Marketplace

MCP servers live in `mcp_servers/<name>/` with `SERVER.md` (YAML frontmatter) + `server.py`.

### SERVER.md Format

```yaml
---
name: example
description: What this MCP server does
version: 1.0.0
command: python
args: [server.py]
auto_load: false          # true = loaded for ALL queries
scope: all                # all | subagent
tools:
  - tool_name_1
  - tool_name_2
---
```

### Tool Naming Convention

`mcp__{server}__{tool}` — e.g., `mcp__memory-tools__pending`, `mcp__aade__send_invoice`

### Loading

- `auto_load: true` servers are loaded automatically for every query via `build_agent_options()`
- Subagents load additional servers via `mcp_servers: [name]` in SUBAGENT.md
- `agent_config.py` scans and caches server configs (120s TTL)
- Daemon passes MCP configs to all task types

### Installed MCP Servers

| Name | Auto-load | Description |
|------|-----------|-------------|
| `memory-tools` | yes | Native MCP tools for all `agelclaw-mem` operations |
| `aade` | no | AADE myDATA invoicing (14 tools) |
| `diavgeia` | no | Greek public procurement monitoring |
| `weather` | no | Open-Meteo weather data |
| `outlook-email` | no | Microsoft Graph email |
| `sqlite` | no | SQLite database tools |
| `file-manager` | no | File management tools |

---

## Skill System

Skills are reusable instruction packages in `.Claude/Skills/<name>/`.

### Structure

```
.Claude/Skills/<name>/
├── SKILL.md              # YAML frontmatter + instructions
├── scripts/              # Helper scripts
└── references/           # Reference data
```

### Execution Pattern

1. Before any task, agent calls `agelclaw-mem find_skill "<description>"`
2. If match found: load skill content, follow instructions
3. If no match: research, create skill, then execute
4. Skills can include scripts (Python, bash) and reference files

### Hard Rules

Learnings promoted to rules (`is_rule=1`) via `agelclaw-mem promote_rule <id>` are injected into every system prompt via `memory.build_rules_prompt()`. These are persistent behavioral rules the agent always follows.

---

## Memory System — `memory.py`

SQLite with WAL mode. All services share one database at `<project_dir>/data/agent_memory.db`.

### Tables

| Table | Purpose |
|-------|---------|
| `tasks` | Task queue (status, priority, due_at, recurring_cron, assigned_to, metadata) |
| `conversations` | Chat history (session_id, channel_type, chat_id) |
| `learnings` | Knowledge base (category, insight, is_rule, source) |
| `user_profile` | User preferences (category, key, value, confidence, source) |
| `kv_store` | Key-value pairs (last_heartbeat_at, etc.) |

### Scheduling

| Format | Example | Meaning |
|--------|---------|---------|
| `daily_HH:MM` | `daily_09:00` | Every day at 09:00 |
| `weekly_D_HH:MM` | `weekly_0_10:00` | Every Monday at 10:00 |
| `every_Xm` | `every_30m` | Every 30 minutes |
| `every_Xh` | `every_2h` | Every 2 hours |

### Memory CLI

`agelclaw-mem <command>` — Bash-callable non-streaming interface to all memory operations. Used by agents via Bash tool, and by MCP server `memory-tools` as native tool calls.

---

## Persona System

User-editable personality files in `<project_dir>/persona/`:

| File | Loaded By | Description |
|------|-----------|-------------|
| `SOUL.md` | All prompts | Core values, behavior rules, communication style |
| `IDENTITY.md` | All prompts | Agent name, vibe, user info |
| `GUARDRAIL.md` | All prompts | Security rules (external content = DATA ONLY) |
| `DAEMON.md` | Daemon only | Autonomous execution rules (language, task folders, reporting) |
| `BOOTSTRAP.md` | First run | Onboarding flow (auto-deleted after completion) |
| `HEARTBEAT.md` | Heartbeat | User-editable proactive check-in checklist |
| `SYSTEM_PROMPT_<id>.md` | Auto-generated | Per-task prompt offloading (Windows CLI length limit) |

Changes take effect within 120s (prompt cache TTL).

---

## System Prompt Architecture

All interfaces use `agent_config.get_system_prompt()`:

```
1. Persona files (SOUL.md + IDENTITY.md + GUARDRAIL.md)
2. Core system prompt (tools, delegation rules, MCP tools-first rule)
3. Hard rules (promoted learnings)
4. MCP server tool listings (auto-loaded servers)
5. Subagent directory (available subagents for delegation)
6. User profile summary
7. Conversation history (build_prompt_with_history)
```

**Tools available to agents:**
```python
AGENT_TOOLS = ["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch"]
```

Plus MCP tool wildcards: `mcp__memory-tools__*`, `mcp__<server>__*` (per-subagent).

---

## Configuration

### config.yaml

```yaml
anthropic_api_key: "sk-ant-..."
openai_api_key: "sk-..."
default_provider: "auto"          # auto | claude | openai
api_port: 8000
daemon_port: 8420
cost_limit_daily: 10.00
max_concurrent_tasks: 3
check_interval: 300               # Daemon cycle interval (seconds)
task_timeout: 900                 # Max seconds per task
task_inactivity_timeout: 360      # Kill task if no activity
script_timeout: 7200              # Max seconds for script tasks
telegram_bot_token: ""
telegram_allowed_users: ""
heartbeat_enabled: false
heartbeat_interval_hours: 4
heartbeat_quiet_start: 23
heartbeat_quiet_end: 8
outlook_client_id: ""
outlook_client_secret: ""
outlook_tenant_id: ""
outlook_user_email: ""
```

**Env vars override YAML**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AGENT_API_PORT`, `AGENT_DAEMON_PORT`, etc.

### Project Directory Resolution

Priority: `AGELCLAW_HOME` env var > CWD with `config.yaml` > `~/.agelclaw/`

Implemented in `project.py`. MCP server scripts use `_find_project_dir()` (search-upward pattern) since they can't import the package.

---

## Source Code Map

```
proactive/src/agelclaw/               # Python package
├── __init__.py                       # Version
├── __main__.py                       # python -m agelclaw
├── cli_entry.py                      # Click CLI: agelclaw command
├── cli.py                            # Interactive chat
├── api_server.py                     # FastAPI :8000
├── daemon.py                         # FastAPI :8420
├── telegram_bot.py                   # Telegram interface
├── agent_config.py                   # System prompt, tools, MCP, routing
├── agent_run.py                      # Dev: start all services
├── memory.py                         # SQLite memory
├── memory_tools.py                   # MCP tools for memory
├── mem_cli.py                        # CLI bridge (agelclaw-mem)
├── skill_tools.py                    # MCP tools for skills
├── embeddings.py                     # Semantic search (sqlite-vec)
├── project.py                        # Project dir resolution
├── setup_wizard.py                   # Interactive setup
├── _nuitka_compat.py                 # Compiled-mode compatibility
├── core/
│   ├── config.py                     # YAML config loader
│   ├── agent_router.py               # Task→Provider routing
│   └── subagent_manager.py           # Subagent lifecycle + SSE
├── agent_wrappers/
│   ├── base_agent.py                 # Abstract agent interface
│   ├── claude_agent.py               # Claude SDK wrapper
│   ├── openai_agent.py               # OpenAI SDK wrapper
│   └── openai_tools.py               # Function tools for OpenAI
└── data/                             # Bundled (immutable)
    ├── react_dist/                   # Pre-built React chat UI
    ├── skills/                       # Bundled skills
    ├── mcp_servers/                  # Bundled MCP servers
    └── templates/                    # Config + persona templates
```

---

## Build & Deployment

### Development

```bash
cd proactive
pip install -e ".[all]"
agelclaw web --dev        # React dev server on :3000
```

### Production (VPS with PM2)

```bash
# ecosystem.config.js
AGELCLAW_HOME=/opt/AgelClaw
pm2 start ecosystem.config.js
```

### Windows Installer

`build_installer.py` → Nuitka `--standalone` → `AgelClaw.exe` + bundled Node.js 22 + Python 3.12 embeddable → Inno Setup → `AgelClaw-Setup-{version}.exe`

### Linux Installer

`build_installer_linux.py` → Nuitka `--standalone` → `agelclaw` ELF + Node.js 22 → tarball. `install-linux.sh` extracts to `/usr/local/lib/agelclaw/` + systemd user service.

### GitHub Actions CI

`.github/workflows/build-release.yml` builds Windows + Linux artifacts on release publish.

---

## Windows-Specific Notes

- Non-streaming SDK only (`query(prompt=string)`) — streaming has timeout issues
- System prompt offloaded to file when >28K chars (Windows CLI length limit)
- `subprocess.CREATE_NO_WINDOW` for background daemon
- Console encoding: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")`
- PM2 interpreter: `python` (not `python3`)
- Auto-start: `agelclaw_daemon.bat` in Windows Startup folder
