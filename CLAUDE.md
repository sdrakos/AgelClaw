# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**AgelClaw v3.1.0** — a self-evolving autonomous assistant with multi-provider support (Claude + OpenAI), persistent memory, skills, and subagents.

Source code lives in `proactive/src/agelclaw/` (Python package, installed via pip).

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Web UI + API** | `:8000` | FastAPI backend + React chat UI + daemon proxy |
| **Daemon** | `:8420` | Background task processor, SSE events, scheduler |
| **Telegram Bot** | — | Telegram chat interface (optional) |
| **CLI** | — | Interactive terminal chat |

All services share the same SQLite memory database. The daemon auto-starts as a subprocess when running any command (`agelclaw`, `agelclaw web`, `agelclaw telegram`).

## Installation & Commands

```bash
# ── Install from GitHub ──
pip install git+https://github.com/sdrakos/AgelClaw.git
pip install "agelclaw[all] @ git+https://github.com/sdrakos/AgelClaw.git"  # with OpenAI, Outlook, embeddings

# ── Or install locally (dev) ──
cd proactive
pip install -e .           # editable install
pip install -e ".[all]"    # with all extras

# ── Quick start ──
agelclaw init              # Create project dir (~/.agelclaw/) with config templates + bundled skills
agelclaw setup             # Interactive wizard: Claude auth, API keys, Telegram, ports
agelclaw                   # Interactive chat (daemon auto-starts)
agelclaw web               # Web UI :8000 + daemon :8420 + opens browser
agelclaw telegram          # Telegram bot + daemon :8420

# ── All CLI commands ──
agelclaw                   # Interactive chat + auto-start daemon
agelclaw -p "question"     # Single-shot: answer and exit
agelclaw web               # Web UI + daemon + browser
agelclaw web --no-daemon   # Web only, no daemon
agelclaw web --no-open     # Don't open browser
agelclaw web --dev         # Proxy to Vite :3000 instead of serving build
agelclaw telegram          # Telegram bot + daemon
agelclaw telegram --no-daemon
agelclaw daemon            # Daemon only (:8420)
agelclaw status            # Show daemon status + task stats
agelclaw update            # pip upgrade from GitHub
agelclaw --home /path web  # Override project directory
agelclaw --version

# ── Memory CLI (used by agents via Bash) ──
agelclaw-mem context                  # Full context summary
agelclaw-mem pending                  # Pending tasks
agelclaw-mem due                      # Due tasks (next_run_at <= now)
agelclaw-mem scheduled                # Future scheduled tasks
agelclaw-mem stats                    # Task statistics
agelclaw-mem add_task "title" "desc" [priority] [due_at] [recurring]
agelclaw-mem start_task <id>
agelclaw-mem complete_task <id> "result"
agelclaw-mem fail_task <id> "error"
agelclaw-mem log "what happened"
agelclaw-mem add_learning "category" "content"
agelclaw-mem rules                    # List active hard rules
agelclaw-mem promote_rule <id>        # Learning → hard rule
agelclaw-mem demote_rule <id>         # Rule → regular learning
agelclaw-mem profile [category]       # View user profile
agelclaw-mem set_profile <cat> <key> "<value>" [confidence] [source]
agelclaw-mem skills                   # List installed skills
agelclaw-mem find_skill "description" # Find matching skill
agelclaw-mem skill_content <name>     # Load skill body + resources
agelclaw-mem create_skill <name> "desc" "body"
agelclaw-mem add_script <name> <file> "code"
agelclaw-mem add_ref <name> <file> "content"
agelclaw-mem update_skill <name> "body"

# ── React UI (dev) ──
cd proactive/react-claude-chat
npm install && npm run dev       # Vite :3000, proxies /api→:8000 /daemon→:8420
npm run build                    # Production build to dist/

# ── PM2 (production) ──
pm2 start ecosystem.config.js
pm2 logs && pm2 monit

# ── Build release ──
cd proactive
python build_release.py          # Creates versioned zip for GitHub release
```

## Architecture

```
agelclaw web / agelclaw telegram / agelclaw
  │
  ├── _ensure_daemon()  ──→  subprocess: agelclaw daemon (:8420)
  │
  └── main service (web :8000 / telegram / cli)
        │
        ├── agent_config.build_prompt_with_history()
        ├── agent_router.route(task_type, prefer)  ──→  RouteResult(provider, model)
        ├── get_agent(provider, model)  ──→  ClaudeAgent or OpenAIAgent
        └── agent.run() / query()  ──→  response + memory.log_conversation()

daemon (:8420) — Parallel Execution
  ├── scheduler_loop(): sleeps until next due task or CHECK_INTERVAL
  ├── run_agent_cycle(): gathers due + pending tasks
  ├── execute_single_task() / execute_subagent_task()  — parallel via asyncio.gather
  ├── Semaphore limits concurrency (max_concurrent_tasks)
  ├── POST /task → add + wake daemon
  ├── GET /events → SSE (task_start, task_end, task_error, agent_text, tool_use)
  └── GET /status, /tasks, /scheduled, /running

api_server (:8000)
  ├── POST /api/chat → SSE streaming (Claude or OpenAI)
  ├── POST /api/upload → file upload + agent analysis
  ├── GET/POST /api/settings → config management
  ├── GET /api/skills → installed skills
  ├── CRUD /api/subagents → subagent lifecycle + SSE events
  ├── GET /daemon/* → proxy to daemon :8420 (graceful 503 if offline)
  └── Static files → react-claude-chat/dist/ (production)
```

## Source Code Map

```
proactive/src/agelclaw/           # Python package (pip install)
├── __init__.py                   # Version 3.1.0
├── __main__.py                   # python -m agelclaw entry point
├── cli_entry.py                  # Click CLI: agelclaw command + daemon auto-start helpers
├── cli.py                        # Interactive chat (streaming query + task management)
├── api_server.py                 # FastAPI :8000 (chat SSE, uploads, settings, skills, subagents, daemon proxy)
├── daemon.py                     # FastAPI :8420 (scheduler, parallel tasks, SSE, notifications)
├── telegram_bot.py               # Telegram bot interface
├── agent_config.py               # System prompt, AGENT_TOOLS, build_agent_options(), get_agent(), get_router()
├── agent_run.py                  # Dev: start all services concurrently
├── memory.py                     # SQLite WAL: tasks, conversations, learnings, kv_store, user_profile
├── memory_tools.py               # MCP tools for memory operations
├── mem_cli.py                    # CLI bridge: agelclaw-mem <command> (Bash-callable, non-streaming)
├── skill_tools.py                # MCP tools for skill CRUD (7 tools)
├── embeddings.py                 # sqlite-vec + OpenAI embeddings for semantic search
├── project.py                    # Project dir resolution (AGELCLAW_HOME → cwd → ~/.agelclaw)
├── setup_wizard.py               # Interactive config wizard
├── core/
│   ├── config.py                 # YAML + env var config loader (singleton, cached)
│   ├── agent_router.py           # Task→Provider router: code→Claude, research→OpenAI, auto heuristics
│   └── subagent_manager.py       # Subagent lifecycle (create, track, cancel) + SSE broadcasting
├── agent_wrappers/
│   ├── base_agent.py             # Abstract: run(), run_streaming()
│   ├── claude_agent.py           # Claude SDK wrapper (query() with ClaudeAgentOptions)
│   ├── openai_agent.py           # OpenAI Agents SDK wrapper (Agent + Runner)
│   └── openai_tools.py           # Function tools for OpenAI (bash, read, write, glob, grep)
└── data/                         # Bundled package data (immutable)
    ├── react_dist/               # Pre-built React chat UI
    ├── skills/                   # 14 bundled skills (pdf, xlsx, pptx, email, skill-creator, etc.)
    └── templates/                # config.yaml.example, .env.example, ecosystem.config.js
```

### Project Directory (mutable user data)

```
~/.agelclaw/                      # Default (or AGELCLAW_HOME, or cwd with config.yaml)
├── config.yaml                   # API keys, provider, ports, limits
├── .env                          # Environment variables (generated from config)
├── .agelclaw                     # Marker file
├── data/agent_memory.db          # SQLite persistent memory
├── logs/daemon.log               # Daemon execution logs
├── tasks/task_<id>/              # Per-task output folders (task_info.json, result.md, artifacts)
├── subagents/<name>/SUBAGENT.md  # Subagent definitions (YAML frontmatter + instructions)
├── reports/                      # Generated reports
├── uploads/                      # Uploaded files
└── .Claude/Skills/               # Project-specific skills (copied from bundled on init)
```

## Key Design Decisions

**Package-based install.** Source in `src/agelclaw/`, installed via `pip install git+...`. CLI entry points: `agelclaw` (main) and `agelclaw-mem` (memory CLI). Bundled data (React build, skills, templates) in `data/`.

**Auto-start daemon.** `cli_entry.py` has `_ensure_daemon(port)` / `_stop_daemon(proc)` helpers. Every command (`agelclaw`, `web`, `telegram`) checks if daemon is running via port check, starts it as subprocess if not, terminates on exit. `--no-daemon` flag to opt out.

**Graceful daemon proxy.** `api_server.py` catches `httpx.ConnectError` on daemon proxy — returns SSE `daemon_offline` event for `/daemon/events` or HTTP 503 for other paths. No crash when daemon is down.

**Multi-provider routing.** `core/agent_router.py` routes tasks: code/debug→Claude Opus, research→OpenAI GPT-4.1, simple→GPT-4.1-mini, chat→Claude Sonnet. Returns `RouteResult(provider, model, reason)`. Fallback to available provider.

**YAML config + env var overrides.** `core/config.py` loads `config.yaml`, maps keys to env vars (e.g. `anthropic_api_key` → `ANTHROPIC_API_KEY`). Env vars win. Singleton with `load_config(force_reload=True)`.

**Parallel task execution.** Daemon runs tasks via `asyncio.gather()` with semaphore concurrency limit. Each task gets independent `query()` call. SSE events tagged with `task_id` for per-task UI tracking.

**Non-streaming SDK on Windows.** Claude Agent SDK streaming has initialization timeouts on Windows. All services use non-streaming `query(prompt=string)`. MCP tools replaced by `agelclaw-mem` CLI called via Bash.

**Skill-first execution.** Before any task, agents call `agelclaw-mem find_skill "<description>"`. If no match: research, create skill (SKILL.md + scripts/ + references/), then execute. Skills in `.Claude/Skills/` (project) or `~/.claude/skills/` (user).

**Hard rules (promoted learnings).** Learnings promoted to rules (`is_rule=1`) are injected into every system prompt via `memory.build_rules_prompt()`. Manage via `agelclaw-mem promote_rule/demote_rule/rules`.

**Subagent system.** Defined in `subagents/<name>/SUBAGENT.md` (YAML frontmatter: provider, task_type, tools). Daemon routes assigned tasks to `execute_subagent_task()` which uses `AgentDefinition` (Claude) or custom system prompt (OpenAI).

## Configuration (config.yaml)

```yaml
anthropic_api_key: "sk-ant-..."
openai_api_key: "sk-..."
default_provider: "auto"          # auto | claude | openai
api_port: 8000
daemon_port: 8420
cost_limit_daily: 10.00
max_concurrent_tasks: 3
check_interval: 300               # Seconds between daemon cycles
telegram_bot_token: ""
telegram_allowed_users: ""
outlook_client_id: ""
outlook_client_secret: ""
outlook_tenant_id: ""
outlook_user_email: ""
```

Env vars override YAML: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AGENT_DEFAULT_PROVIDER`, `AGENT_API_PORT`, `AGENT_DAEMON_PORT`, `AGENT_COST_LIMIT_DAILY`, `AGENT_MAX_CONCURRENT`, `AGENT_CHECK_INTERVAL`, `TELEGRAM_BOT_TOKEN`, etc.

## Scheduling Syntax

Used in `agelclaw-mem add_task`:

| Format | Example | Meaning |
|--------|---------|---------|
| `daily_HH:MM` | `daily_09:00` | Every day at 09:00 |
| `weekly_D_HH:MM` | `weekly_0_10:00` | Every Monday at 10:00 (0=Mon) |
| `every_Xm` | `every_30m` | Every 30 minutes |
| `every_Xh` | `every_2h` | Every 2 hours |

`due_at` uses ISO datetime: `"2026-02-16T09:00:00"`

## Windows Notes

- Console encoding: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")`
- PM2 interpreter: `python` (not `python3`)
- Claude SDK streaming has timeout issues — use non-streaming `query(prompt=string)`
- SdkMcpTool: `.name` for tool name, `.handler(args_dict)` for async call
- `subprocess.CREATE_NO_WINDOW` flag for background daemon on Windows

## AGENT_TOOLS

Tools available to agents (defined in `agent_config.py`):

```python
AGENT_TOOLS = ["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch"]
```

Agents use `agelclaw-mem <command>` via Bash for all memory, skill, and profile operations.
