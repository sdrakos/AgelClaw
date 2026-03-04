# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: Keep This File Updated

**Before every commit and push**, update this CLAUDE.md to reflect any changes made in the session:
- New design decisions → add to "Key Design Decisions"
- New files or modules → update "Source Code Map"
- New CLI commands → update "Development"
- New config keys → update "Configuration"
- Architecture changes → update "Architecture"

## What This Is

**AgelClaw v3.1.0** — a self-evolving autonomous assistant with multi-provider support (Claude + OpenAI), persistent memory, skills, and subagents.

Source code lives in `proactive/src/agelclaw/` (Python package, installed via pip). There are also legacy flat-layout files at `proactive/*.py` (older copies, not part of the pip package) — always edit under `proactive/src/agelclaw/`.

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Web UI + API** | `:8000` | FastAPI backend + React chat UI + daemon proxy |
| **Daemon** | `:8420` | Background task processor, SSE events, scheduler |
| **Telegram Bot** | — | Telegram chat interface (optional) |
| **CLI** | — | Interactive terminal chat |

All services share the same SQLite memory database. The daemon auto-starts as a subprocess when running any command (`agelclaw`, `agelclaw web`, `agelclaw telegram`).

## Development

```bash
# ── Install locally (dev) ──
cd proactive
pip install -e .           # editable install
pip install -e ".[all]"    # with all extras (OpenAI, Outlook, embeddings)

# ── Run services ──
agelclaw                   # Interactive chat + auto-start daemon
agelclaw -p "question"     # Single-shot: answer and exit
agelclaw web               # Web UI :8000 + daemon :8420 + opens browser
agelclaw web --dev         # Proxy to Vite :3000 instead of serving build
agelclaw telegram          # Telegram bot + daemon
agelclaw daemon            # Daemon only (:8420)
agelclaw status            # Show daemon status + task stats

# ── React UI (dev) ──
cd proactive/react-claude-chat
npm install && npm run dev       # Vite :3000, proxies /api→:8000 /daemon→:8420
npm run build                    # Production build → dist/ (also bundled in data/react_dist/)

# ── Build release ──
cd proactive
python build_release.py          # Creates versioned zip for GitHub release

# ── Install from GitHub (end users) ──
pip install git+https://github.com/sdrakos/AgelClaw.git
pip install "agelclaw[all] @ git+https://github.com/sdrakos/AgelClaw.git"
agelclaw init              # Create project dir (~/.agelclaw/) with config templates + bundled skills
agelclaw setup             # Interactive wizard: Claude auth, API keys, Telegram, ports

# ── Build Windows installer ──
pip install nuitka ordered-set zstandard   # Prerequisites
cd proactive
python build_installer.py                  # Full build: Nuitka + embed + Inno Setup
python build_installer.py --skip-nuitka    # Re-run Inno Setup only
# Output: build/installer/AgelClaw-Setup-3.1.0.exe

# ── Build Linux release ──
pip install nuitka ordered-set zstandard   # Prerequisites
sudo apt install patchelf ccache           # Linux build deps
cd proactive
python build_installer_linux.py            # Full build: Nuitka + Node.js + tarball
python build_installer_linux.py --skip-nuitka  # Reuse existing dist
# Output: build/agelclaw-3.1.0-linux-x86_64.tar.gz

# ── Install on Linux VPS (end users) ──
curl -sL https://github.com/sdrakos/AgelClaw/releases/download/v3.1.0/install-linux.sh | sudo bash
agelclaw init && agelclaw setup
systemctl --user enable --now agelclaw     # Auto-start daemon
```

**No test suite or linting.** There is no pytest, ruff, mypy, or CI/CD configured. The `proactive/tests/` directory exists but is empty. GitHub Actions CI builds release artifacts (Windows .exe + Linux tarball) on release publish.

### Memory & Subagent CLI

Agents interact with memory via `agelclaw-mem` (Bash-callable, non-streaming):

```bash
# Tasks
agelclaw-mem context | pending | due | scheduled | stats
agelclaw-mem add_task "title" "desc" [priority] [due_at] [recurring]
agelclaw-mem start_task <id> | complete_task <id> "result" | fail_task <id> "error"
agelclaw-mem cancel_task <id> | delete_task <id>

# Knowledge
agelclaw-mem log "what happened"
agelclaw-mem add_learning "category" "content"
agelclaw-mem rules | promote_rule <id> | demote_rule <id>
agelclaw-mem profile [category] | set_profile <cat> <key> "<value>" [confidence] [source]

# Skills
agelclaw-mem skills | find_skill "description" | skill_content <name>
agelclaw-mem create_skill <name> "desc" "body"
agelclaw-mem add_script <name> <file> "code" | add_ref <name> <file> "content"
agelclaw-mem update_skill <name> "body"

# Subagents
agelclaw-mem subagents | subagent_content <name>
agelclaw-mem create_subagent <name> "desc" "body" [provider] [task_type] [tools_csv]
agelclaw-mem add_subagent_script <name> <file> "code" | add_subagent_ref <name> <file> "content"
agelclaw-mem add_subagent_task <subagent> "title" "desc" [pri] [due_at] [recurring]
agelclaw-mem subagent_tasks <name> [status] [limit] | subagent_stats <name>

# MCP Servers
agelclaw-mem mcp_servers | mcp_server_content <name>
agelclaw-mem create_mcp_server <name> "desc" "server_code"
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
  ├── _maybe_run_heartbeat(): proactive check after each cycle (if enabled)
  ├── execute_single_task() / execute_subagent_task()  — fire-and-forget via asyncio.create_task
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
├── _nuitka_compat.py             # Compiled-mode compatibility (IS_COMPILED, path helpers)
├── memory.py                     # SQLite WAL: tasks, conversations, learnings, kv_store, user_profile
├── mem_cli.py                    # CLI bridge: agelclaw-mem <command> (Bash-callable, non-streaming)
├── skill_tools.py                # MCP tools for skill CRUD (7 tools)
├── memory_tools.py               # MCP tools for memory operations
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
    ├── skills/                   # 15 bundled skills (pdf, xlsx, pptx, email, skill-creator, subagent-creator, etc.)
    ├── mcp_servers/              # Bundled MCP servers (memory-tools auto-loaded)
    └── templates/                # Config + persona templates copied on init
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
├── mcp_servers/<name>/           # MCP server definitions (SERVER.md + server.py)
├── persona/                      # Agent personality & onboarding
│   ├── SOUL.md, IDENTITY.md     # Core values, name/vibe (loaded into every system prompt)
│   ├── BOOTSTRAP.md              # First-run onboarding (auto-deleted after completion)
│   └── HEARTBEAT.md              # User-editable heartbeat checklist
├── reports/                      # Generated reports
├── uploads/                      # Uploaded files
└── .Claude/Skills/               # Project-specific skills (copied from bundled on init)
```

## Key Design Decisions

**Package-based install.** Source in `src/agelclaw/`, installed via `pip install git+...`. CLI entry points: `agelclaw` (main) and `agelclaw-mem` (memory CLI). Bundled data (React build, skills, templates) in `data/`. Build system: hatchling (`pyproject.toml`).

**Unified system prompt.** All 3 interfaces (CLI, Web UI, Telegram) use `agent_config.get_system_prompt()` and `agent_config.build_prompt_with_history()`. Same tools (`AGENT_TOOLS`), same session (`SHARED_SESSION_ID`).

**Auto-start daemon.** `cli_entry.py` has `_ensure_daemon(port)` / `_stop_daemon(proc)` helpers. Every command checks if daemon is running via port check, starts it as subprocess if not, terminates on exit. `--no-daemon` flag to opt out.

**Graceful daemon proxy.** `api_server.py` catches `httpx.ConnectError` on daemon proxy — returns SSE `daemon_offline` event for `/daemon/events` or HTTP 503 for other paths. No crash when daemon is down.

**Multi-provider routing.** `core/agent_router.py` routes tasks: code/debug→Claude Opus, research→OpenAI GPT-4.1, simple→GPT-4.1-mini, chat→Claude Sonnet. Returns `RouteResult(provider, model, reason)`. Fallback to available provider.

**YAML config + env var overrides.** `core/config.py` loads `config.yaml`, maps keys to env vars (e.g. `anthropic_api_key` → `ANTHROPIC_API_KEY`). Env vars win. Singleton with `load_config(force_reload=True)`.

**Non-streaming SDK on Windows.** Claude Agent SDK streaming has initialization timeouts on Windows. All services use non-streaming `query(prompt=string)`. SDK-created MCP servers require streaming, but **external stdio MCP servers work** in `--print` mode.

**MCP Marketplace.** Standalone MCP server directory `mcp_servers/<name>/` (SERVER.md + server.py). `auto_load: true` servers loaded for all queries. Subagents reference additional servers via `mcp_servers:` in SUBAGENT.md. Tool pattern: `mcp__{server}__{tool}`. `agent_config.py` has `_scan_mcp_servers()` (returns configs + prompt text), `load_mcp_server_config(name)` (per-server loading), `_build_mcp_tool_wildcards()` (builds `mcp__name__*` entries). `build_agent_options()` automatically includes auto-loaded MCP servers. Daemon passes MCP configs to all task types (global, subagent, heartbeat).

**memory-tools MCP server.** Bundled auto-loaded MCP server that provides native tool access to all `agelclaw-mem` operations: tasks (pending, due, stats, add_task, complete_task), learnings, profile, skills, subagents. Replaces `Bash("agelclaw-mem <cmd>")` with direct `mcp__memory-tools__<cmd>` calls — 1 tool call instead of 4. Agent can still use `agelclaw-mem` via Bash as fallback.

**MCP tools-first rule.** System prompt includes a general rule: if an MCP tool (`mcp__<server>__<tool>`) exists for an operation, always use it before falling back to Bash. MCP tools are native tool calls (faster) vs `agelclaw-mem` subprocess spawn (slower). This applies to all operations, not just memory — any MCP server's tools take priority over equivalent Bash commands. The coder subagent (SUBAGENT.md) also includes this rule with a full list of available MCP memory tools.

**Search-upward .env pattern for skill scripts.** Skill scripts that need credentials (e.g. Outlook email) must NOT use hardcoded parent directory counts (`Path(__file__).parent.parent.parent.parent / ".env"`) because the depth varies between dev install and pip install. Instead, traverse parent directories upward looking for `proactive/.env` or `.env`. This rule is enforced in skill-creator SKILL.md and subagent-creator SKILL.md.

**Notification script multi-path search.** `daemon.py`'s `send_task_notification()` searches multiple locations for the notification script: `~/.claude/skills/`, `get_skills_dir()`, and parent directory fallback (for when cwd is `proactive/` but skills are in `aclaude/.Claude/Skills/`).

**Task execution safety (anti-double-run).** Daemon marks tasks as `in_progress` in the database BEFORE launching the query. `get_pending_tasks()` only returns `status='pending'`. After query finishes, a safety net checks if the agent called `complete_task`; if not, the daemon marks it completed itself.

**Task timeouts.** `task_timeout` (default 900s) limits total task duration. `task_inactivity_timeout` (default 360s) kills tasks that stop producing messages. On timeout, task is marked `failed` with diagnostic info (last tool, turn count, last output) and Telegram notification. All timeout defaults are in `core/config.py` with env var overrides.

**Per-subagent timeout overrides.** SUBAGENT.md YAML frontmatter supports `timeout`, `inactivity_timeout`, `max_turns`, and `max_retries` fields. These override global defaults for that subagent. Example: `timeout: 1800` gives a subagent 30 minutes instead of the default 15.

**Watchdog safety net.** `_watchdog_loop()` runs every 30s as a background coroutine. It checks all running tasks against their effective timeout + 20% grace period. If a task exceeds the hard limit (timeout failed to fire), the watchdog force-cancels it, marks it failed, and sends a Telegram notification. Started automatically in daemon lifespan.

**Stale task cleanup on startup.** When the daemon starts, `_cleanup_stale_tasks()` queries for any tasks stuck in `in_progress` (from a previous crash) and resets them to `pending`. This prevents tasks from being permanently stuck after a daemon restart.

**Auto-retry for failed tasks.** Subagents can specify `max_retries` in SUBAGENT.md frontmatter (default 0). When a task fails (timeout or exception) and retries remain, the daemon resets it to `pending` with incremented `retry_count` in task metadata, then wakes the scheduler. Telegram notification includes retry status.

**Tool hallucination guard.** System prompt explicitly lists the ONLY available tools and warns against using non-existent tools (e.g. `TodoWrite`, `Task`, `TodoRead`) which cause the agent to freeze waiting for a response that never comes.

**Skill-first execution.** Before any task, agents call `agelclaw-mem find_skill "<description>"`. If no match: research, create skill (SKILL.md + scripts/ + references/), then execute.

**Hard rules (promoted learnings).** Learnings promoted to rules (`is_rule=1`) are injected into every system prompt via `memory.build_rules_prompt()`.

**Subagent system.** Defined in `subagents/<name>/SUBAGENT.md` (YAML frontmatter: provider, task_type, tools) with optional `scripts/` and `references/` dirs. Daemon routes assigned tasks to `execute_subagent_task()` which uses `AgentDefinition` (Claude) or custom system prompt (OpenAI).

**Subagent delegation.** System prompt enforces that the chat agent MUST delegate to an existing subagent instead of executing long-running work inline. Agent creates a task via `add_subagent_task` and responds immediately, freeing the chat. Daemon executes the subagent in the background.

**Immediate vs scheduled execution.** Subagent tasks run IMMEDIATELY by default — no `due_at` parameter. Date/time references in user requests are the TARGET of the report (e.g. "forecast tomorrow" = run NOW, forecast for tomorrow), not when to execute. `due_at` is ONLY set when the user explicitly says "schedule"/"προγραμμάτισε".

**Shared conversation session.** All 3 interfaces use `session_id="shared_chat"`. When a subagent task completes, the daemon logs a summary to `shared_chat` so the chat agent immediately knows what happened. Group Telegram chats use a separate `"group_chat"` session for privacy.

**Memory context isolation.** In group Telegram chats, the system: (1) skips persona files from the prompt, (2) excludes user profile from context, (3) uses separate "group_chat" session, (4) doesn't recall private conversation history.

**Persona files.** `persona/SOUL.md`, `persona/IDENTITY.md`, and `persona/GUARDRAIL.md` are loaded at the top of every system prompt via `_load_persona_files()`. `persona/BOOTSTRAP.md` triggers first-run onboarding — auto-deleted after completion. Changes take effect within 120s (prompt cache TTL).

**GUARDRAIL.md (security rules).** Loaded into every system prompt. Enforces strict block policy: external content (emails, file uploads, scraped pages, API responses, group chat) is DATA ONLY — never instructions. Blocks file operations, tool execution, config changes, credential exposure, and memory manipulation when triggered by external content. Includes prompt injection detection patterns and notification protocol (log + Telegram alert to owner). User-editable at `persona/GUARDRAIL.md`.

**Heartbeat proactivity.** Daemon runs `_maybe_run_heartbeat()` after each scheduler cycle. Controlled by `heartbeat_enabled`, `heartbeat_interval_hours`, `heartbeat_quiet_start/end` in config.yaml. Reads `persona/HEARTBEAT.md` for a user-editable checklist. Sends Telegram messages only when actionable.

**Clean notifications.** Telegram notifications use the task's `result` field from `complete_task()` — not raw agent text with internal reasoning.

**Windows installer (Nuitka + Inno Setup).** `build_installer.py` compiles the package with Nuitka `--standalone` into `AgelClaw.exe`, bundles Node.js 22 portable (for npm/Claude CLI), Python 3.12 embeddable (for MCP scripts), and runs Inno Setup → `AgelClaw-Setup-{version}.exe`. All runtime changes in `_nuitka_compat.py` behind `IS_COMPILED` guards — dev mode unchanged. See `proactive/INSTALLER_MANUAL.md`.

**Linux installer (Nuitka + tarball).** `build_installer_linux.py` compiles the package with Nuitka `--standalone` → `agelclaw` (ELF binary), bundles Node.js 22 for Linux, creates `agelclaw-mem` symlink (filename-based dispatch), and packages into `agelclaw-{version}-linux-x86_64.tar.gz`. No Python embed needed — MCP scripts use system `python3`. `install-linux.sh` extracts to `/usr/local/lib/agelclaw/`, symlinks binaries to `/usr/local/bin/`, and copies systemd user service.

**GitHub Actions CI.** `.github/workflows/build-release.yml` builds both Windows and Linux artifacts on `release: published` or manual `workflow_dispatch`. Artifacts uploaded to the GitHub Release automatically.

**Linux auto-start (systemd).** `project.py`'s `init_project()` calls `_install_systemd_service()` on Linux, which copies `agelclaw.service` template to `~/.config/systemd/user/`. User enables with `systemctl --user enable --now agelclaw`.

**Telegram notification splitting.** `send_telegram_notification()` splits long results into multiple messages (4096 char limit per message) instead of truncating.

**cancel_task fallback.** `cancel_task` in mem_cli first tries the daemon endpoint (for running tasks). If daemon returns 404, falls back to `delete_task` (removes from database).

**Confirmation = Execute.** When the user says "ναι", "yes", "nai", "ok" in response to a proposed action, the agent executes immediately — no re-description, no second confirmation.

**Fire-and-forget task execution.** Daemon uses `asyncio.create_task()` instead of `await asyncio.gather()` for task execution. The scheduler loop no longer blocks until all tasks finish — it launches tasks and immediately continues to the next cycle. This prevents long-running tasks (e.g. 2-hour Instagram scripts) from blocking the pickup of new tasks. Semaphore still limits concurrency (`max_concurrent_tasks`). Each task's `finally` block handles its own cleanup.

**Auto-start daemon on Windows login.** `project.py`'s `init_project()` calls `_install_startup_script()` on Windows, which creates `agelclaw_daemon.bat` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`. The bat file `cd`s to the project directory and runs `start /min agelclaw daemon`. Only created once — skipped if the file already exists. Non-critical: failure doesn't block init.

**Port-aware service startup.** `agent_run.py` (dev runner) checks if a service's port is already in use before starting it. If the daemon is already running on `:8420` or the API server on `:8000`, it skips that service instead of crashing with `Address already in use`.

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
task_timeout: 900                 # Max seconds per task (15 min)
task_inactivity_timeout: 360      # Kill task if no activity for 6 min
script_timeout: 7200              # Max seconds for direct script tasks (2 hours)
telegram_bot_token: ""
telegram_allowed_users: ""        # Comma-separated Telegram user IDs (empty = allow all)
heartbeat_enabled: false
heartbeat_interval_hours: 4
heartbeat_quiet_start: 23         # Don't heartbeat 23:00-08:00
heartbeat_quiet_end: 8
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

Agents prefer MCP tools (`mcp__memory-tools__*`) for memory/task operations — faster than Bash. Use `agelclaw-mem` via Bash only as fallback.
