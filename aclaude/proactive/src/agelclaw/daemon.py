"""
Agent Daemon v2 — Parallel Execution
=====================================
Autonomous agent with:
- Parallel task execution (semaphore-controlled concurrency)
- Scheduled cycles (PM2/cron)
- HTTP API for instant task submission
- SSE event streaming with per-task tracking

Architecture:
  - FastAPI server runs on port 8420 (always on)
  - Background task runs the agent cycle every INTERVAL
  - Each task gets its own independent query() call
  - Semaphore limits concurrent tasks (AGENT_MAX_CONCURRENT, default 3)
  - POST /task → adds task + wakes the agent immediately
  - GET /status → returns current state with running tasks
  - GET /events → SSE with task-level events (task_start, task_end, task_error)

Run with PM2:
  pm2 start ecosystem.config.js
"""

import asyncio
import io
import json
import os
import re
import sys
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows cp1253 encoding — emojis and unicode must not crash the logger
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from contextlib import asynccontextmanager

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AgentDefinition,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)

from agelclaw.memory import Memory
from agelclaw.memory_tools import ALL_MEMORY_TOOLS
from agelclaw.skill_tools import ALL_SKILL_TOOLS

# ─────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────

from agelclaw.core.config import load_config
from agelclaw.core.agent_router import AgentRouter, Provider
from agelclaw.agent_config import get_agent, get_system_prompt, AGENT_TOOLS, ALLOWED_TOOLS, _scan_mcp_servers, _build_mcp_tool_wildcards, load_mcp_server_config

_cfg = load_config()
CHECK_INTERVAL = _cfg.get("check_interval", 300)
MAX_TASKS_PER_CYCLE = int(os.getenv("AGENT_MAX_TASKS", "5"))
MAX_CONCURRENT_TASKS = _cfg.get("max_concurrent_tasks", 3)
API_PORT = _cfg.get("daemon_port", 8420)
WEBHOOK_URL = os.getenv("AGENT_WEBHOOK_URL", "")  # POST cycle summaries here
TASK_TIMEOUT = int(_cfg.get("task_timeout", 300))  # 5 min max per task
TASK_INACTIVITY_TIMEOUT = int(_cfg.get("task_inactivity_timeout", 120))  # 2 min no activity = kill
SCRIPT_TIMEOUT = int(_cfg.get("script_timeout", 7200))  # 2 hours max for direct script tasks

_router = AgentRouter()
from agelclaw.project import get_project_dir, get_log_dir, get_skills_dir, get_persona_dir
LOG_DIR = get_log_dir()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "daemon.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("agent-daemon")

memory = Memory()

# Event to wake up the daemon immediately
wake_event = asyncio.Event()

# Semaphore to limit concurrent task execution
task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# Track which task IDs are currently running (prevent duplicate execution)
running_task_ids: set[int] = set()

# Track asyncio.Task references for cancellation support
running_asyncio_tasks: dict[int, asyncio.Task] = {}

# Current status — tracks multiple running tasks
agent_status = {
    "state": "idle",          # idle | running
    "running_tasks": {},      # {task_id: {"title": ..., "started_at": ...}}
    "last_cycle": None,
}

# SSE subscribers: list of asyncio.Queue objects for live event streaming
sse_subscribers: list[asyncio.Queue] = []

# MCP Servers
memory_server = create_sdk_mcp_server(name="memory", version="1.0.0", tools=ALL_MEMORY_TOOLS)
skill_server = create_sdk_mcp_server(name="skill-manager", version="1.0.0", tools=ALL_SKILL_TOOLS)


# ─────────────────────────────────────────────────────────
# Task Completion Notification
# ─────────────────────────────────────────────────────────

def send_telegram_notification(task_id: int, task_title: str, status: str, result: str, duration: float = None):
    """Send Telegram notification when a task completes/fails."""
    try:
        from agelclaw.core.config import load_config as _load_cfg
        cfg = _load_cfg(force_reload=True)
        bot_token = cfg.get("telegram_bot_token", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        allowed_users = cfg.get("telegram_allowed_users", "") or os.getenv("TELEGRAM_ALLOWED_USERS", "")

        if not bot_token or not allowed_users:
            return

        if status == "completed":
            icon = "\u2705"
        elif status == "cancelled":
            icon = "\u26d4"
        elif status == "started":
            icon = "\u25b6\ufe0f"
        else:
            icon = "\u274c"
        dur_str = f" ({duration:.0f}\u03b4\u03b5\u03c5\u03c4.)" if duration else ""
        # Build human-friendly message - just the result, no technical details
        result_clean = result or ""
        # Remove technical prefixes the agent might have added
        for prefix in ("Successfully ", "Completed: ", "Done: ", "Result: "):
            if result_clean.startswith(prefix):
                result_clean = result_clean[len(prefix):]
                break
        header = f"{icon} *{task_title}*{dur_str}\n\n"

        # Split long results into multiple Telegram messages (4096 char limit)
        max_result_len = 4096 - len(header) - 50  # safety margin
        chunks = []
        remaining = result_clean
        while remaining:
            if len(remaining) <= max_result_len:
                chunks.append(remaining)
                break
            # Try to split at newline
            split_pos = remaining.rfind("\n", 0, max_result_len)
            if split_pos == -1 or split_pos < max_result_len // 2:
                split_pos = remaining.rfind(" ", 0, max_result_len)
            if split_pos == -1 or split_pos < max_result_len // 2:
                split_pos = max_result_len
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos:].lstrip("\n")

        if not chunks:
            chunks = [""]

        import urllib.request
        import json as _json
        for uid in allowed_users.split(","):
            uid = uid.strip()
            if not uid:
                continue
            for i, chunk in enumerate(chunks):
                text = f"{header}{chunk}" if i == 0 else chunk
                payload = _json.dumps({
                    "chat_id": int(uid),
                    "text": text,
                    "parse_mode": "Markdown",
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception as te:
                    # Retry without Markdown if parsing fails
                    payload = _json.dumps({
                        "chat_id": int(uid),
                        "text": text.replace("*", ""),
                    }).encode("utf-8")
                    req2 = urllib.request.Request(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    try:
                        urllib.request.urlopen(req2, timeout=10)
                    except Exception:
                        pass
        log.info(f"Telegram notification sent for task #{task_id}")

        # Log to shared_chat so the chat agent has context about completed tasks
        if status in ("completed", "failed"):
            try:
                dur_info = f" ({duration:.0f}s)" if duration else ""
                if status == "completed":
                    chat_log = f"[Task #{task_id} completed{dur_info}] {task_title}: {result_clean[:500]}"
                else:
                    chat_log = f"[Task #{task_id} failed{dur_info}] {task_title}: {result_clean[:300]}"
                memory.log_conversation(
                    role="assistant",
                    content=chat_log,
                    session_id="shared_chat",
                )
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Failed to send Telegram notification for task #{task_id}: {e}")


def send_task_notification(task_id: int, task_title: str, status: str, result: str, duration: float = None):
    """Send email notification when a task completes"""
    try:
        # Get path to notification script — search multiple locations
        notifier_rel = Path("task-completion-notifier") / "scripts" / "task_notifier.py"
        candidates = [
            Path.home() / ".claude" / "skills" / notifier_rel,
            get_skills_dir() / notifier_rel,
            # Skills may be in parent dir (e.g. aclaude/.Claude/Skills/ when cwd is proactive/)
            get_skills_dir().parent.parent.parent / ".Claude" / "Skills" / notifier_rel,
        ]
        script_path = None
        for c in candidates:
            if c.exists():
                script_path = c
                break

        if not script_path:
            log.warning(f"Notification script not found (searched {len(candidates)} locations)")
            return

        # Build command
        from agelclaw._nuitka_compat import get_python_exe
        cmd = [
            get_python_exe(),
            str(script_path),
            "--task-id", str(task_id),
            "--task-title", task_title,
            "--status", status,
            "--result", result[:500],  # Limit result length
        ]

        if duration is not None:
            cmd.extend(["--duration", str(round(duration, 1))])

        # Run in background (don't wait)
        subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        log.info(f"Notification queued for task #{task_id}")

    except Exception as e:
        log.error(f"Failed to send notification for task #{task_id}: {e}")


# ─────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────

_DAEMON_EXTENSIONS = """

## DAEMON MODE — AUTONOMOUS BACKGROUND EXECUTION
You are running as the background daemon. You execute tasks from persistent memory WITHOUT human input.

## LANGUAGE
ALWAYS write task results (complete_task) in GREEK. The user speaks Greek.
Example: agelclaw-mem complete_task 25 "Δημιουργήθηκαν 4 εικόνες book cover και αποθηκεύτηκαν στο tasks/task_25/"
NEVER write results in English.

## TASK FOLDERS
Each task has a dedicated folder: `tasks/task_<id>/`
- `task_info.json` — metadata (title, status, timestamps)
- `result.md` — final result text
- Save ALL task outputs (reports, data files, scripts) into this folder.

## MANDATORY: USE CLAUDE OPUS 4.6 FOR CREATION
When creating Skills or Subagents, you MUST:
- Think with Claude Opus 4.6 quality — complete, working, tested
- NEVER create empty/placeholder definitions
- ALWAYS include working scripts with real code
- TEST every script after creation
VIOLATION: Creating a skill/subagent with just `import X` or a bare template is FORBIDDEN.

## STARTUP PROCEDURE (every cycle)
1. Run: agelclaw-mem context
2. Run: agelclaw-mem due
3. Run: agelclaw-mem pending
4. Execute tasks in priority order

## SKILL-FIRST EXECUTION (MANDATORY for EVERY task)
Before executing ANY task:
1. Run: agelclaw-mem find_skill "<task description>"
2. If skill found → run: agelclaw-mem skill_content <name> → follow instructions
3. If NO skill found:
   a. Read the skill-creator guide FIRST: cat .Claude/Skills/skill-creator/SKILL.md
   b. Research the topic using available tools (Bash, Read, Grep, WebSearch)
   c. Create skill following the skill-creator guide:
      agelclaw-mem create_skill <name> "<desc>" "<body>"
   d. Add scripts: agelclaw-mem add_script <name> <file> "<code>"
   e. Add references if needed: agelclaw-mem add_ref <name> <file> "<content>"
   f. Execute the task using the newly created skill
4. After execution: agelclaw-mem update_skill <name> "<updated body>" if improvements found

## TASK EXECUTION
For each task:
1. agelclaw-mem start_task <id>
2. Follow SKILL-FIRST EXECUTION above (find or create skill)
3. Execute the task using skill scripts and instructions
4. agelclaw-mem complete_task <id> "<result summary>"
5. If failed: agelclaw-mem fail_task <id> "<error>"
6. agelclaw-mem log "<what you did>"
7. agelclaw-mem add_learning "<category>" "<content>" when you learn something

## SKILL CREATION RULES
- Create skills proactively — every new domain should get a skill
- ALWAYS follow the skill-creator guide at .Claude/Skills/skill-creator/SKILL.md
- Scripts must be self-contained, handle errors, and work on Windows
- Test scripts after creating them (run with python)
- Include real working examples in skill body, not placeholders
- Add API docs or schemas as references when dealing with external services
- For long code: use Write tool to create files, then add_script with a short wrapper

## TASK REPORTING
After completing a task, ALWAYS:
1. Write a detailed result via: agelclaw-mem complete_task <id> "<full result summary>"
2. If the task requested a "report" or "summary", also save it as a file:
   - Write the report to: proactive/reports/report_<task_id>_<YYYYMMDD_HHMMSS>.md
   - Include: task title, what was done, results, any data/findings
3. Log what you did: agelclaw-mem log "<summary>"
4. Add learnings if applicable

## AUTONOMY RULES
- No human to ask — make your best judgment
- Always log what you do
- Respect task dependencies
- Don't repeat completed work
- Scheduled tasks with future next_run_at are NOT shown in pending — they appear only when due
- Be efficient with tokens

## CRITICAL: NEVER ASK THE USER TO DO ANYTHING
- You are FULLY AUTONOMOUS. NEVER say "run this command" or "you can do X".
- If something needs to run → RUN IT YOURSELF via Bash.
- If something needs scheduling → CREATE THE RECURRING TASK yourself via mem_cli.py add_task with due_at and recurring params.
- If a script needs to be installed/configured → DO IT YOURSELF.
- If dependencies are missing → INSTALL THEM YOURSELF (pip install, npm install, etc).
- The daemon handles recurring tasks automatically — no need for --schedule flags.
"""


def _get_daemon_prompt() -> str:
    """Build daemon system prompt: shared base + daemon extensions + rules."""
    return get_system_prompt() + _DAEMON_EXTENSIONS + memory.build_rules_prompt()


# ─────────────────────────────────────────────────────────
# Subagent Helpers
# ─────────────────────────────────────────────────────────

proactive_dir = get_project_dir()


def _parse_subagent_md(name: str) -> dict:
    """Parse subagents/<name>/SUBAGENT.md and return structured config.

    Returns: {'name', 'description', 'provider', 'task_type', 'tools', 'body'}
    """
    import re
    import yaml

    sub_md = proactive_dir / "subagents" / name / "SUBAGENT.md"
    if not sub_md.exists():
        return {"name": name, "description": "", "provider": "auto", "task_type": "general", "tools": None, "body": ""}

    content = sub_md.read_text(encoding="utf-8", errors="replace")

    result = {"name": name, "description": "", "provider": "auto", "task_type": "general", "tools": None, "command": "", "body": "",
              "timeout": None, "inactivity_timeout": None, "max_turns": None, "max_retries": 0, "mcp_servers": []}

    # Parse YAML frontmatter
    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        try:
            fm_data = yaml.safe_load(fm_match.group(1))
            if isinstance(fm_data, dict):
                result["description"] = fm_data.get("description", "")
                result["provider"] = fm_data.get("provider", "auto")
                result["task_type"] = fm_data.get("task_type", "general")
                result["tools"] = fm_data.get("tools")  # None means use defaults
                result["command"] = fm_data.get("command", "")  # Direct script execution command
                # Per-subagent timeout overrides
                if "timeout" in fm_data:
                    result["timeout"] = int(fm_data["timeout"])
                if "inactivity_timeout" in fm_data:
                    result["inactivity_timeout"] = int(fm_data["inactivity_timeout"])
                if "max_turns" in fm_data:
                    result["max_turns"] = int(fm_data["max_turns"])
                if "max_retries" in fm_data:
                    result["max_retries"] = int(fm_data["max_retries"])
                if "mcp_servers" in fm_data:
                    mcp_list = fm_data["mcp_servers"]
                    if isinstance(mcp_list, list):
                        result["mcp_servers"] = mcp_list
        except Exception:
            pass  # Fall back to regex parsing
            d = re.search(r'description:\s*(.+)', fm_match.group(1))
            if d:
                result["description"] = d.group(1).strip().strip('"\'')
            p = re.search(r'provider:\s*(\S+)', fm_match.group(1))
            if p:
                result["provider"] = p.group(1)
            t = re.search(r'task_type:\s*(\S+)', fm_match.group(1))
            if t:
                result["task_type"] = t.group(1)

        # Body = everything after frontmatter
        body_start = fm_match.end()
        result["body"] = content[body_start:].strip()
    else:
        result["body"] = content.strip()

    return result


# ─────────────────────────────────────────────────────────
# Agent Cycle
# ─────────────────────────────────────────────────────────

def _broadcast_event(event_type: str, data: dict):
    """Send an event to all SSE subscribers and log it."""
    payload = json.dumps({"type": event_type, "time": datetime.now().isoformat(), **data})
    dead = []
    for i, q in enumerate(sse_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(i)
    # Clean up dead subscribers
    for i in reversed(dead):
        sse_subscribers.pop(i)


async def _send_webhook(data: dict):
    """POST cycle summary to configured webhook URL (fire-and-forget)."""
    if not WEBHOOK_URL:
        return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(WEBHOOK_URL, json=data)
            log.info(f"Webhook POST {WEBHOOK_URL} → {resp.status_code}")
    except Exception as e:
        log.warning(f"Webhook failed: {e}")


async def execute_single_task(task: dict, cycle_session: str):
    """Execute a single task with its own independent query() call.

    Acquires the semaphore to respect concurrency limits.
    All SSE events are tagged with task_id and task_title.
    """
    task_id = task["id"]
    task_title = task.get("title", f"Task #{task_id}")
    task_start = datetime.now()
    session_id = f"task_{task_id}_{task_start.strftime('%Y%m%d_%H%M%S')}"

    async with task_semaphore:
        # Register as running — both in-memory AND in database
        running_task_ids.add(task_id)
        memory.start_task(task_id)  # DB: status='in_progress' BEFORE query starts
        agent_status["running_tasks"][task_id] = {
            "title": task_title,
            "started_at": task_start.isoformat(),
            "session_id": session_id,
            "timeout": TASK_TIMEOUT,
        }
        agent_status["state"] = "running"

        log.info(f">>> Task #{task_id} started: {task_title}")
        _broadcast_event("task_start", {
            "session_id": session_id,
            "task_id": task_id,
            "task_title": task_title,
            "cycle_session": cycle_session,
        })
        send_telegram_notification(task_id, task_title, "started", "Started executing...")

        # Build a focused prompt for this single task
        context = memory.build_context_summary()
        proactive_dir = get_project_dir()
        task_desc = task.get("description", "")
        task_priority = task.get("priority", 5)
        task_category = task.get("category", "general")

        # Create task folder early so it's available in the prompt
        task_folder = memory.get_task_folder(task_id)

        prompt_text = (
            f"TASK EXECUTION: {session_id}\n"
            f"TIME: {task_start.isoformat()}\n\n"
            f"## YOUR SINGLE TASK\n"
            f"Task ID: {task_id}\n"
            f"Title: {task_title}\n"
            f"Description: {task_desc}\n"
            f"Priority: {task_priority}\n"
            f"Category: {task_category}\n"
            f"Task Folder: {task_folder}\n\n"
            f"{context}\n\n"
            f"---\n"
            f"WORKING DIR: {proactive_dir}\n\n"
            f"## STRICT RULES\n"
            f"- Execute ONLY what the task description says. Nothing more.\n"
            f"- Do NOT fix, improve, or change anything outside the task scope.\n"
            f"- Do NOT restart services, edit configs, or modify infrastructure.\n"
            f"- Do NOT create reports unless the task explicitly asks for one.\n"
            f"- Once you call complete_task, you are DONE. STOP immediately.\n\n"
            f"## RESULT FORMAT (CRITICAL)\n"
            f"The result in complete_task is sent directly to the user as a Telegram notification.\n"
            f"- Write in GREEK, in natural human language\n"
            f"- Write ONLY the outcome, like you're telling a friend what happened\n"
            f"- NO technical steps, NO \"I'll execute\", NO \"Perfect!\", NO \"Now I'll...\"\n"
            f"- NO English, NO skill names, NO script names, NO tool names\n"
            f"- GOOD: \"Στάλθηκε η εικόνα book cover στο stefanos.drakos@gmail.com\"\n"
            f"- BAD: \"I'll send the image via microsoft-graph-email skill's send_email.py\"\n\n"
            f"## STEPS (follow exactly)\n"
            f"1. `agelclaw-mem start_task {task_id}`\n"
            f"2. Do ONLY what the task description says\n"
            f"3. Save outputs to {task_folder}\n"
            f"4. `agelclaw-mem complete_task {task_id} \"<result in Greek>\"`\n"
            f"5. STOP. Do not continue after complete_task.\n\n"
            f"Use `agelclaw-mem <command> [args]` via Bash for memory/skill operations."
        )

        # Route task to provider (tasks can specify provider in context metadata)
        task_context = task.get("context") or {}
        if isinstance(task_context, str):
            try:
                task_context = json.loads(task_context)
            except (json.JSONDecodeError, TypeError):
                task_context = {}
        task_provider = task_context.get("provider")
        route = _router.route(task_type=task_category, prefer=task_provider)

        full_response = []
        tools_used = []
        turn_count = 0

        try:
            if route.provider == Provider.OPENAI:
                # OpenAI execution path
                log.info(f"[Task #{task_id}] Using OpenAI ({route.model})")
                _broadcast_event("agent_text", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "text": f"Processing with OpenAI ({route.model})...",
                })
                agent = get_agent(provider="openai", model=route.model)
                result = await agent.run(
                    prompt=prompt_text,
                    system_prompt=_get_daemon_prompt(),
                    tools=ALLOWED_TOOLS,
                    cwd=str(proactive_dir),
                    max_turns=30,
                )
                full_response.append(result)
                _broadcast_event("agent_text", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "text": result[:500],
                })
            else:
                # Claude execution path — let SDK find bundled claude.exe
                log.info(f"[Task #{task_id}] Using Claude ({route.model})")

                # Load auto-loaded MCP servers
                mcp_configs, _ = _scan_mcp_servers()
                allowed = list(AGENT_TOOLS)
                if mcp_configs:
                    allowed += _build_mcp_tool_wildcards(mcp_configs)

                options = ClaudeAgentOptions(
                    system_prompt=_get_daemon_prompt(),
                    allowed_tools=allowed,
                    setting_sources=["user", "project"],
                    permission_mode="bypassPermissions",
                    cwd=str(proactive_dir),
                    max_turns=30,
                )
                if mcp_configs:
                    options.mcp_servers = mcp_configs

                last_progress_log = task_start
                last_activity_g = datetime.now()
                turn_count = 0

                async def _stream_global_task():
                    """Wrap query() with inactivity timeout for global tasks."""
                    nonlocal last_activity_g
                    agen = query(prompt=prompt_text, options=options).__aiter__()
                    while True:
                        try:
                            msg = await asyncio.wait_for(
                                agen.__anext__(),
                                timeout=TASK_INACTIVITY_TIMEOUT,
                            )
                            last_activity_g = datetime.now()
                            yield msg
                        except asyncio.TimeoutError:
                            idle = (datetime.now() - last_activity_g).total_seconds()
                            raise TimeoutError(
                                f"Task #{task_id} idle for {idle:.0f}s "
                                f"(inactivity timeout: {TASK_INACTIVITY_TIMEOUT}s)"
                            )
                        except StopAsyncIteration:
                            break

                async for message in _stream_global_task():
                    if isinstance(message, AssistantMessage):
                        turn_count += 1
                        elapsed = (datetime.now() - task_start).total_seconds()
                        if elapsed > TASK_TIMEOUT:
                            raise TimeoutError(
                                f"Task #{task_id} exceeded timeout "
                                f"({TASK_TIMEOUT}s, ran for {elapsed:.0f}s)"
                            )
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_response.append(block.text)
                                log.info(f"[Task #{task_id}] [{elapsed:.0f}s] Agent: {block.text[:150]}")
                                _broadcast_event("agent_text", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "text": block.text[:500],
                                })
                            elif isinstance(block, ToolUseBlock):
                                tools_used.append(block.name)
                                log.info(f"[Task #{task_id}] [{elapsed:.0f}s] Tool: {block.name}")
                                _broadcast_event("tool_use", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "tool": block.name,
                                })
                        # Periodic progress log every 60s
                        now = datetime.now()
                        if (now - last_progress_log).total_seconds() >= 60:
                            log.info(f"[Task #{task_id}] PROGRESS: {elapsed:.0f}s elapsed, {turn_count} turns, {len(tools_used)} tools, {len(full_response)} text blocks")
                            last_progress_log = now

            duration = (datetime.now() - task_start).total_seconds()
            summary = "\n".join(full_response)[:2000]

            # SAFETY NET: ensure task is marked completed in DB
            task_now = memory.get_task(task_id)
            if task_now and task_now.get("status") != "completed":
                log.warning(f"[Task #{task_id}] Agent did NOT call complete_task — daemon marking completed")
                memory.complete_task(task_id, result=summary[:500] if summary else "Completed by daemon (agent did not call complete_task)")

            # Write execution log to task folder
            try:
                log_file = task_folder / "logs.txt"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] Task #{task_id} completed in {duration:.1f}s\n")
                    f.write(f"Tools used: {', '.join(tools_used) if tools_used else 'none'}\n")
                    f.write(f"Summary: {summary[:1000]}\n\n")
            except Exception as log_err:
                log.warning(f"Failed to write task log: {log_err}")

            memory.log_conversation(
                role="assistant",
                content=f"Task #{task_id} '{task_title}': {duration:.1f}s, {len(tools_used)} tools. {summary[:500]}",
                session_id=session_id,
            )

            log.info(f"<<< Task #{task_id} done: {duration:.1f}s, {len(tools_used)} tools")
            _broadcast_event("task_end", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "duration_s": round(duration, 1),
                "tools_used": tools_used,
                "summary": summary[:1000],
            })

            # Send notifications — use the clean DB result, not the raw agent summary
            task_final = memory.get_task(task_id)
            clean_result = (task_final or {}).get("result") or summary
            send_task_notification(
                task_id=task_id,
                task_title=task_title,
                status="completed",
                result=clean_result,
                duration=duration
            )
            send_telegram_notification(
                task_id=task_id,
                task_title=task_title,
                status="completed",
                result=clean_result,
                duration=duration
            )

        except asyncio.CancelledError:
            duration = (datetime.now() - task_start).total_seconds()
            log.info(f"[Task #{task_id}] Cancelled by user after {duration:.1f}s")
            memory.update_task(task_id, status="cancelled", result="Cancelled by user")
            _broadcast_event("task_cancelled", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "duration_s": round(duration, 1),
            })
            send_telegram_notification(task_id, task_title, "cancelled", "Ακυρώθηκε από τον χρήστη", duration)
            raise  # Re-raise so gather() sees it

        except TimeoutError as e:
            duration = (datetime.now() - task_start).total_seconds()
            last_tool = tools_used[-1] if tools_used else "none"
            last_text_preview = full_response[-1][:100] if full_response else "none"
            diagnostic = f"Last tool: {last_tool} | Turns: {turn_count} | Last output: {last_text_preview}"
            log.error(f"[Task #{task_id}] TIMEOUT after {duration:.1f}s: {e}\n  {diagnostic}")
            memory.update_task(task_id, status="failed", error=f"{e} | {diagnostic}")
            memory.log_conversation(role="system", content=f"Task #{task_id} TIMEOUT: {e}\n{diagnostic}", session_id=session_id)
            _broadcast_event("task_error", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "error": str(e),
                "diagnostic": diagnostic,
                "duration_s": round(duration, 1),
            })
            send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"TIMEOUT: {e}", duration=duration)
            tg_msg = f"Timeout μετά από {duration:.0f}s\nΤελευταίο tool: {last_tool}\nTurns: {turn_count}"
            send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=tg_msg, duration=duration)

        except Exception as e:
            duration = (datetime.now() - task_start).total_seconds()
            log.error(f"[Task #{task_id}] Error: {e}", exc_info=True)
            memory.log_conversation(role="system", content=f"Task #{task_id} ERROR: {e}", session_id=session_id)
            _broadcast_event("task_error", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "error": str(e),
                "duration_s": round(duration, 1),
            })

            # Send failure notifications (email + telegram)
            send_task_notification(
                task_id=task_id,
                task_title=task_title,
                status="failed",
                result=f"ERROR: {str(e)}",
                duration=duration
            )
            send_telegram_notification(
                task_id=task_id,
                task_title=task_title,
                status="failed",
                result=f"ERROR: {str(e)}",
                duration=duration
            )

        finally:
            # Clean up running state
            running_task_ids.discard(task_id)
            running_asyncio_tasks.pop(task_id, None)
            agent_status["running_tasks"].pop(task_id, None)
            if not agent_status["running_tasks"]:
                agent_status["state"] = "idle"


async def execute_subagent_task(task: dict, cycle_session: str):
    """Execute a task assigned to a subagent using SDK-native patterns.

    Claude path: uses AgentDefinition for isolated subagent execution.
    OpenAI path: uses Agent class with subagent's system prompt.
    """
    task_id = task["id"]
    task_title = task.get("title", f"Task #{task_id}")
    subagent_name = task.get("assigned_to")
    task_start = datetime.now()
    session_id = f"subagent_{subagent_name}_{task_id}_{task_start.strftime('%Y%m%d_%H%M%S')}"

    # Parse subagent definition BEFORE acquiring semaphore (needed for timeout tracking)
    sa = _parse_subagent_md(subagent_name)
    sa_has_def = bool(sa.get("body"))
    sa_tools_info = sa.get("tools") or "all (default)"

    # Resolve per-subagent timeouts (SUBAGENT.md overrides > global config)
    sa_timeout = sa.get("timeout") or TASK_TIMEOUT
    sa_inactivity = sa.get("inactivity_timeout") or TASK_INACTIVITY_TIMEOUT
    sa_max_turns = sa.get("max_turns") or 30
    sa_max_retries = sa.get("max_retries") or 0

    async with task_semaphore:
        # Register as running — both in-memory AND in database
        running_task_ids.add(task_id)
        memory.start_task(task_id)  # DB: status='in_progress' BEFORE query starts
        agent_status["running_tasks"][task_id] = {
            "title": task_title,
            "subagent": subagent_name,
            "started_at": task_start.isoformat(),
            "session_id": session_id,
            "timeout": sa_timeout,
        }
        agent_status["state"] = "running"

        log.info(f">>> Subagent '{subagent_name}' Task #{task_id} started: {task_title}")
        log.info(f"[Subagent '{subagent_name}' Task #{task_id}] SUBAGENT.md: {'found' if sa_has_def else 'NOT FOUND'}, "
                 f"provider={sa.get('provider', 'auto')}, task_type={sa.get('task_type', 'general')}, tools={sa_tools_info}")
        log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Timeouts: total={sa_timeout}s, inactivity={sa_inactivity}s, max_turns={sa_max_turns}, max_retries={sa_max_retries}")
        if not sa_has_def:
            log.warning(f"[Subagent '{subagent_name}' Task #{task_id}] No SUBAGENT.md found — will use default daemon prompt")
        _broadcast_event("task_start", {
            "session_id": session_id,
            "task_id": task_id,
            "task_title": task_title,
            "subagent": subagent_name,
            "cycle_session": cycle_session,
        })
        send_telegram_notification(task_id, task_title, "started", f"Started executing (subagent: {subagent_name})...")

        # Build focused task prompt
        context = memory.build_context_summary()
        task_desc = task.get("description", "")
        task_priority = task.get("priority", 5)
        task_category = task.get("category", "general")
        task_folder = memory.get_task_folder(task_id)

        task_prompt = (
            f"SUBAGENT TASK EXECUTION: {session_id}\n"
            f"TIME: {task_start.isoformat()}\n"
            f"SUBAGENT: {subagent_name}\n\n"
            f"## YOUR SINGLE TASK\n"
            f"Task ID: {task_id}\n"
            f"Title: {task_title}\n"
            f"Description: {task_desc}\n"
            f"Priority: {task_priority}\n"
            f"Category: {task_category}\n"
            f"Task Folder: {task_folder}\n\n"
            f"{context}\n\n"
            f"---\n"
            f"WORKING DIR: {proactive_dir}\n\n"
            f"## SKILL-FIRST EXECUTION (MANDATORY — follow this before ANY work)\n"
            f"Before executing the task:\n"
            f"1. Run: `agelclaw-mem find_skill \"<task description>\"`\n"
            f"2. If skill found -> run: `agelclaw-mem skill_content <name>` -> follow its instructions\n"
            f"3. If NO skill found:\n"
            f"   a. Read the skill-creator guide: `cat .Claude/Skills/skill-creator/SKILL.md`\n"
            f"   b. Research the topic using available tools (Bash, Read, WebSearch)\n"
            f"   c. Create skill: `agelclaw-mem create_skill <name> \"<desc>\" \"<body>\"`\n"
            f"   d. Add scripts: `agelclaw-mem add_script <name> <file> \"<code>\"`\n"
            f"   e. Add references if needed: `agelclaw-mem add_ref <name> <file> \"<content>\"`\n"
            f"   f. Execute the task using the newly created skill\n"
            f"4. After execution: `agelclaw-mem update_skill <name> \"<updated body>\"` if improvements found\n\n"
            f"## SKILL CREATION RULES\n"
            f"- Create skills proactively — every new domain should get a skill\n"
            f"- Follow the skill-creator guide at `.Claude/Skills/skill-creator/SKILL.md`\n"
            f"- Scripts must be self-contained, handle errors, and work on Windows\n"
            f"- Test scripts after creating them (run with python)\n"
            f"- Include real working examples in skill body, not placeholders\n"
            f"- For long code: use Write tool to create files, then add_script with a short wrapper\n\n"
            f"## STRICT RULES\n"
            f"- Execute ONLY what the task description says. Nothing more.\n"
            f"- Do NOT fix, improve, or change anything outside the task scope.\n"
            f"- NEVER create new scripts if the subagent/skill already has one. Use the EXISTING script with its flags/parameters. If it lacks a feature, MODIFY the existing script — do NOT write a throwaway replacement.\n"
            f"- Once you call complete_task, you are DONE. STOP immediately.\n\n"
            f"## RESULT FORMAT (CRITICAL)\n"
            f"The result in complete_task is sent directly to the user as a Telegram notification.\n"
            f"- Write in GREEK, in natural human language\n"
            f"- Write ONLY the outcome\n"
            f"- NO technical steps, NO English\n\n"
            f"## STEPS (follow exactly)\n"
            f"1. `agelclaw-mem start_task {task_id}`\n"
            f"2. SKILL-FIRST: find or create the right skill (see above)\n"
            f"3. Execute the task using the skill's scripts and instructions\n"
            f"4. Save outputs to {task_folder}\n"
            f"5. `agelclaw-mem complete_task {task_id} \"<result in Greek>\"`\n"
            f"6. STOP. Do not continue after complete_task.\n\n"
            f"Use `agelclaw-mem <command> [args]` via Bash for memory/skill operations."
        )

        # Route to provider
        task_context = task.get("context") or {}
        if isinstance(task_context, str):
            try:
                task_context = json.loads(task_context)
            except (json.JSONDecodeError, TypeError):
                task_context = {}
        task_provider = task_context.get("provider") or sa.get("provider", "auto")
        if task_provider == "auto":
            task_provider = None
        route = _router.route(task_type=sa.get("task_type", task_category), prefer=task_provider)

        # Resolve subagent tools
        sa_tools = sa.get("tools") or AGENT_TOOLS

        full_response = []
        tools_used = []
        turn_count = 0

        try:
            if route.provider == Provider.OPENAI:
                # OpenAI path — run with subagent's system prompt appended
                log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Using OpenAI ({route.model})")
                _broadcast_event("agent_text", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "text": f"Subagent '{subagent_name}' processing with OpenAI ({route.model})...",
                })
                agent = get_agent(provider="openai", model=route.model)
                subagent_system = _get_daemon_prompt() + f"\n\n## SUBAGENT ROLE: {subagent_name}\n{sa['body']}"
                result = await agent.run(
                    prompt=task_prompt,
                    system_prompt=subagent_system,
                    tools=sa_tools if isinstance(sa_tools, list) and all(isinstance(t, str) for t in sa_tools) else ALLOWED_TOOLS,
                    cwd=str(proactive_dir),
                    max_turns=30,
                )
                full_response.append(result)
                _broadcast_event("agent_text", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "text": result[:500],
                })
            else:
                # Claude path — use AgentDefinition for isolated subagent context
                log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Using Claude with AgentDefinition")

                # Load MCP servers: auto-loaded + subagent-specific
                mcp_configs, _ = _scan_mcp_servers()
                sa_mcp_names = sa.get("mcp_servers", [])
                for mcp_name in sa_mcp_names:
                    if mcp_name not in mcp_configs:
                        cfg = load_mcp_server_config(mcp_name)
                        if cfg:
                            mcp_configs[mcp_name] = cfg

                allowed = list(AGENT_TOOLS) + ["Task"]
                if mcp_configs:
                    allowed += _build_mcp_tool_wildcards(mcp_configs)

                options = ClaudeAgentOptions(
                    system_prompt=_get_daemon_prompt(),
                    allowed_tools=allowed,
                    agents={
                        subagent_name: AgentDefinition(
                            description=sa["description"],
                            prompt=sa["body"],
                            tools=sa_tools,
                            model="sonnet",
                        ),
                    },
                    permission_mode="bypassPermissions",
                    cwd=str(proactive_dir),
                    max_turns=sa_max_turns,
                )
                if mcp_configs:
                    options.mcp_servers = mcp_configs

                delegation_prompt = f"Use the {subagent_name} agent to execute this task:\n\n{task_prompt}"

                last_progress_log = task_start
                last_activity = datetime.now()
                turn_count = 0

                async def _stream_with_inactivity_check():
                    """Wrap query() iterator with inactivity timeout."""
                    nonlocal last_activity
                    agen = query(prompt=delegation_prompt, options=options).__aiter__()
                    while True:
                        try:
                            msg = await asyncio.wait_for(
                                agen.__anext__(),
                                timeout=sa_inactivity,
                            )
                            last_activity = datetime.now()
                            yield msg
                        except asyncio.TimeoutError:
                            idle = (datetime.now() - last_activity).total_seconds()
                            raise TimeoutError(
                                f"Subagent '{subagent_name}' idle for {idle:.0f}s "
                                f"(inactivity timeout: {sa_inactivity}s)"
                            )
                        except StopAsyncIteration:
                            break

                async for message in _stream_with_inactivity_check():
                    if isinstance(message, AssistantMessage):
                        turn_count += 1
                        elapsed = (datetime.now() - task_start).total_seconds()
                        # Check total task timeout
                        if elapsed > sa_timeout:
                            raise TimeoutError(
                                f"Subagent '{subagent_name}' exceeded task timeout "
                                f"({sa_timeout}s, ran for {elapsed:.0f}s)"
                            )
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_response.append(block.text)
                                log.info(f"[Subagent '{subagent_name}' #{task_id}] [{elapsed:.0f}s] Agent: {block.text[:150]}")
                                _broadcast_event("agent_text", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "subagent": subagent_name,
                                    "text": block.text[:500],
                                })
                            elif isinstance(block, ToolUseBlock):
                                tools_used.append(block.name)
                                log.info(f"[Subagent '{subagent_name}' #{task_id}] [{elapsed:.0f}s] Tool: {block.name}")
                                _broadcast_event("tool_use", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "subagent": subagent_name,
                                    "tool": block.name,
                                })
                        # Periodic progress log every 60s
                        now = datetime.now()
                        if (now - last_progress_log).total_seconds() >= 60:
                            log.info(f"[Subagent '{subagent_name}' #{task_id}] PROGRESS: {elapsed:.0f}s elapsed, {turn_count} turns, {len(tools_used)} tools, {len(full_response)} text blocks")
                            last_progress_log = now

            duration = (datetime.now() - task_start).total_seconds()
            summary = "\n".join(full_response)[:2000]

            # SAFETY NET: ensure task is marked completed in DB
            # The agent SHOULD call complete_task, but if it didn't, we do it here
            task_now = memory.get_task(task_id)
            if task_now and task_now.get("status") != "completed":
                log.warning(f"[Subagent '{subagent_name}' #{task_id}] Agent did NOT call complete_task — daemon marking completed")
                memory.complete_task(task_id, result=summary[:500] if summary else "Completed by daemon (agent did not call complete_task)")

            # Write execution log to task folder
            try:
                log_file = task_folder / "logs.txt"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] Subagent '{subagent_name}' Task #{task_id} completed in {duration:.1f}s\n")
                    f.write(f"Tools used: {', '.join(tools_used) if tools_used else 'none'}\n")
                    f.write(f"Summary: {summary[:1000]}\n\n")
            except Exception as log_err:
                log.warning(f"Failed to write task log: {log_err}")

            memory.log_conversation(
                role="assistant",
                content=f"Subagent '{subagent_name}' Task #{task_id} '{task_title}': {duration:.1f}s, {len(tools_used)} tools. {summary[:500]}",
                session_id=session_id,
            )

            log.info(f"<<< Subagent '{subagent_name}' Task #{task_id} done: {duration:.1f}s")
            _broadcast_event("task_end", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "subagent": subagent_name,
                "duration_s": round(duration, 1),
                "tools_used": tools_used,
                "summary": summary[:1000],
            })

            # Send notifications — use the clean DB result, not the raw agent summary
            task_final = memory.get_task(task_id)
            clean_result = (task_final or {}).get("result") or summary
            send_task_notification(task_id=task_id, task_title=task_title, status="completed", result=clean_result, duration=duration)
            send_telegram_notification(task_id=task_id, task_title=task_title, status="completed", result=clean_result, duration=duration)

        except asyncio.CancelledError:
            duration = (datetime.now() - task_start).total_seconds()
            log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Cancelled by user after {duration:.1f}s")
            memory.update_task(task_id, status="cancelled", result="Cancelled by user")
            _broadcast_event("task_cancelled", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "subagent": subagent_name,
                "duration_s": round(duration, 1),
            })
            send_telegram_notification(task_id, task_title, "cancelled", "Ακυρώθηκε από τον χρήστη", duration)
            raise  # Re-raise so gather() sees it

        except TimeoutError as e:
            duration = (datetime.now() - task_start).total_seconds()
            last_tool = tools_used[-1] if tools_used else "none"
            last_text_preview = full_response[-1][:100] if full_response else "none"
            diagnostic = f"Last tool: {last_tool} | Turns: {turn_count} | Last output: {last_text_preview}"
            log.error(f"[Subagent '{subagent_name}' Task #{task_id}] TIMEOUT after {duration:.1f}s: {e}\n  {diagnostic}")

            # Auto-retry if max_retries allows
            retry_count = task.get("retry_count", 0) or 0
            if retry_count < sa_max_retries:
                retry_count += 1
                memory.update_task(task_id, status="pending", error=f"Retry {retry_count}/{sa_max_retries}: {e}", retry_count=retry_count)
                log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Auto-retry {retry_count}/{sa_max_retries}")
                send_telegram_notification(task_id, task_title, "started",
                    f"Timeout μετά από {duration:.0f}s — αυτόματο retry ({retry_count}/{sa_max_retries})", duration)
                wake_event.set()  # Wake daemon to pick up retried task
            else:
                memory.update_task(task_id, status="failed", error=f"{e} | {diagnostic}")
                memory.log_conversation(role="system", content=f"Subagent '{subagent_name}' Task #{task_id} TIMEOUT: {e}\n{diagnostic}", session_id=session_id)
                _broadcast_event("task_error", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "error": str(e),
                    "diagnostic": diagnostic,
                    "duration_s": round(duration, 1),
                })
                send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"TIMEOUT: {e}", duration=duration)
                tg_msg = f"Timeout μετά από {duration:.0f}s\nΤελευταίο tool: {last_tool}\nTurns: {turn_count}"
                if sa_max_retries > 0:
                    tg_msg += f"\nRetries: {retry_count}/{sa_max_retries} (εξαντλήθηκαν)"
                send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=tg_msg, duration=duration)

        except Exception as e:
            duration = (datetime.now() - task_start).total_seconds()
            log.error(f"[Subagent '{subagent_name}' Task #{task_id}] Error: {e}", exc_info=True)

            # Auto-retry for transient failures if max_retries allows
            retry_count = task.get("retry_count", 0) or 0
            if retry_count < sa_max_retries:
                retry_count += 1
                memory.update_task(task_id, status="pending", error=f"Retry {retry_count}/{sa_max_retries}: {e}", retry_count=retry_count)
                log.info(f"[Subagent '{subagent_name}' Task #{task_id}] Auto-retry {retry_count}/{sa_max_retries} after error: {e}")
                send_telegram_notification(task_id, task_title, "started",
                    f"Error: {str(e)[:100]} — αυτόματο retry ({retry_count}/{sa_max_retries})", duration)
                wake_event.set()
            else:
                memory.log_conversation(role="system", content=f"Subagent '{subagent_name}' Task #{task_id} ERROR: {e}", session_id=session_id)
                _broadcast_event("task_error", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "error": str(e),
                    "duration_s": round(duration, 1),
                })
                send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"ERROR: {str(e)}", duration=duration)
                send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=f"ERROR: {str(e)}", duration=duration)

        finally:
            running_task_ids.discard(task_id)
            running_asyncio_tasks.pop(task_id, None)
            agent_status["running_tasks"].pop(task_id, None)
            if not agent_status["running_tasks"]:
                agent_status["state"] = "idle"


def _has_greek(s: str) -> bool:
    """Check if string contains Greek Unicode characters."""
    return any('\u0370' <= c <= '\u03ff' or '\u1f00' <= c <= '\u1fff' for c in s)


def _extract_cli_from_description(description: str) -> dict:
    """Extract CLI arguments (--flag value...) from task description text.

    Scans from the first --flag to the end of the description.
    Ignores tokens containing Greek characters (natural language).
    Strips trailing punctuation from flags and values (e.g. --skip-voice. → --skip-voice).
    Returns dict of {flag: [values...]}.
    """
    if not description:
        return {}

    # Find first -- in description
    idx = description.find('--')
    if idx == -1:
        return {}

    cli_section = description[idx:]
    tokens = cli_section.split()

    overrides = {}
    current_flag = None
    for token in tokens:
        # Strip trailing punctuation that comes from natural language sentences
        clean = token.rstrip('.,;:!?)')
        if clean.startswith('--') and len(clean) > 2:
            current_flag = clean
            if current_flag not in overrides:
                overrides[current_flag] = []
        elif current_flag and not _has_greek(token):
            overrides[current_flag].append(clean)
        else:
            # Greek text or non-CLI token after values → stop collecting
            current_flag = None

    return overrides


def _apply_cli_overrides(command: str, overrides: dict) -> str:
    """Replace or append CLI flag overrides in the base command.

    For each --flag in overrides:
    - If the flag exists in the command, replace it and its values.
    - If the flag does not exist, append it to the command.
    """
    for flag, values in overrides.items():
        override_str = flag + (' ' + ' '.join(values) if values else '')
        # Pattern: --flag followed by non-flag values (tokens not starting with --)
        pattern = re.compile(rf'{re.escape(flag)}(?:\s+(?!--)\S+)*')
        if pattern.search(command):
            command = pattern.sub(override_str, command, count=1)
        else:
            command = command.rstrip() + ' ' + override_str
    return command


async def execute_script_task(task: dict, cycle_session: str):
    """Execute a task by running a shell command directly — NO AI agent.

    Used for task_type=script subagents. The subagent's SUBAGENT.md must contain
    a 'command' field in the YAML frontmatter specifying the exact command to run.

    CLI arguments in the task description (e.g. --to email@example.com) will
    override the corresponding flags in the base command.

    Benefits:
    - No inactivity timeout (script manages its own pacing)
    - Much higher timeout (SCRIPT_TIMEOUT, default 2 hours)
    - No AI overhead — just subprocess exec + result capture
    """
    task_id = task["id"]
    task_title = task.get("title", f"Task #{task_id}")
    subagent_name = task.get("assigned_to", "script")
    task_start = datetime.now()
    session_id = f"script_{subagent_name}_{task_id}_{task_start.strftime('%Y%m%d_%H%M%S')}"

    # Parse subagent to get the command
    sa = _parse_subagent_md(subagent_name)
    command = sa.get("command", "").strip()
    if not command:
        log.error(f"[Script Task #{task_id}] No 'command' in SUBAGENT.md frontmatter for '{subagent_name}'")
        memory.update_task(task_id, status="failed", error=f"No 'command' defined in subagent '{subagent_name}'")
        send_telegram_notification(task_id, task_title, "failed", f"Δεν βρέθηκε command στο subagent '{subagent_name}'")
        return

    # ── CLI override: extract --flag values from task description and merge ──
    description = task.get("description", "")
    cli_overrides = _extract_cli_from_description(description)
    if cli_overrides:
        original_command = command
        command = _apply_cli_overrides(command, cli_overrides)
        log.info(f"[Script Task #{task_id}] CLI overrides from description: {cli_overrides}")
        log.info(f"[Script Task #{task_id}] Original command: {original_command}")
        log.info(f"[Script Task #{task_id}] Final command:    {command}")

    async with task_semaphore:
        # Register as running
        running_task_ids.add(task_id)
        memory.start_task(task_id)
        agent_status["running_tasks"][task_id] = {
            "title": task_title,
            "subagent": subagent_name,
            "type": "script",
            "started_at": task_start.isoformat(),
            "session_id": session_id,
            "timeout": SCRIPT_TIMEOUT,
        }
        agent_status["state"] = "running"

        log.info(f">>> Script Task #{task_id} started: {task_title}")
        log.info(f"    Command: {command}")
        _broadcast_event("task_start", {
            "session_id": session_id,
            "task_id": task_id,
            "task_title": task_title,
            "subagent": subagent_name,
            "type": "script",
            "cycle_session": cycle_session,
        })
        send_telegram_notification(task_id, task_title, "started", f"Script εκτέλεση: {command[:100]}...")

        task_folder = memory.get_task_folder(task_id)

        try:
            # Run the command as a subprocess with SCRIPT_TIMEOUT
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(proactive_dir),
                creationflags=creationflags,
            )

            # Stream stdout in real-time for logging
            stdout_lines = []
            stderr_lines = []

            async def _read_stream(stream, lines_list, label):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    lines_list.append(decoded)
                    elapsed = (datetime.now() - task_start).total_seconds()
                    log.info(f"[Script #{task_id}] [{elapsed:.0f}s] {label}: {decoded[:200]}")
                    # Broadcast progress
                    _broadcast_event("agent_text", {
                        "session_id": session_id,
                        "task_id": task_id,
                        "task_title": task_title,
                        "subagent": subagent_name,
                        "text": f"[{label}] {decoded[:300]}",
                    })

            # Read stdout and stderr concurrently, with overall timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        _read_stream(proc.stdout, stdout_lines, "stdout"),
                        _read_stream(proc.stderr, stderr_lines, "stderr"),
                    ),
                    timeout=SCRIPT_TIMEOUT,
                )
                await proc.wait()
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(
                    f"Script task '{subagent_name}' exceeded timeout "
                    f"({SCRIPT_TIMEOUT}s / {SCRIPT_TIMEOUT//3600}h)"
                )

            duration = (datetime.now() - task_start).total_seconds()
            exit_code = proc.returncode
            stdout_text = "\n".join(stdout_lines)
            stderr_text = "\n".join(stderr_lines)

            # Save full output to task folder
            try:
                (task_folder / "stdout.txt").write_text(stdout_text, encoding="utf-8")
                if stderr_text:
                    (task_folder / "stderr.txt").write_text(stderr_text, encoding="utf-8")
                (task_folder / "logs.txt").write_text(
                    f"Command: {command}\n"
                    f"Exit code: {exit_code}\n"
                    f"Duration: {duration:.1f}s\n"
                    f"Started: {task_start.isoformat()}\n"
                    f"Finished: {datetime.now().isoformat()}\n",
                    encoding="utf-8",
                )
            except Exception as log_err:
                log.warning(f"Failed to write script output: {log_err}")

            if exit_code == 0:
                # Success — use last 500 chars of stdout as result
                result_text = stdout_text[-500:].strip() if stdout_text else "Script completed successfully"
                log.info(f"<<< Script Task #{task_id} SUCCESS: {duration:.1f}s, exit=0")
                memory.complete_task(task_id, result=result_text)
                memory.log_conversation(
                    role="assistant",
                    content=f"Script task '{task_title}' (subagent: {subagent_name}) completed in {duration:.1f}s. Exit=0. Output: {result_text[:300]}",
                    session_id="shared_chat",
                )
                _broadcast_event("task_end", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "type": "script",
                    "duration_s": round(duration, 1),
                    "exit_code": 0,
                })
                send_task_notification(task_id=task_id, task_title=task_title, status="completed", result=result_text, duration=duration)
                send_telegram_notification(task_id=task_id, task_title=task_title, status="completed", result=result_text, duration=duration)
            else:
                # Failed — include stderr
                error_text = stderr_text[-500:].strip() if stderr_text else f"Exit code {exit_code}"
                log.error(f"<<< Script Task #{task_id} FAILED: {duration:.1f}s, exit={exit_code}")
                memory.update_task(task_id, status="failed", error=error_text)
                memory.log_conversation(
                    role="system",
                    content=f"Script task '{task_title}' FAILED (exit={exit_code}): {error_text[:300]}",
                    session_id="shared_chat",
                )
                _broadcast_event("task_error", {
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_title": task_title,
                    "subagent": subagent_name,
                    "type": "script",
                    "error": error_text[:500],
                    "exit_code": exit_code,
                    "duration_s": round(duration, 1),
                })
                send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"Exit code {exit_code}: {error_text}", duration=duration)
                send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=f"Script failed (exit {exit_code}): {error_text[:300]}", duration=duration)

        except asyncio.CancelledError:
            duration = (datetime.now() - task_start).total_seconds()
            log.info(f"[Script Task #{task_id}] Cancelled after {duration:.1f}s")
            memory.update_task(task_id, status="cancelled", result="Cancelled by user")
            _broadcast_event("task_cancelled", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "subagent": subagent_name,
                "duration_s": round(duration, 1),
            })
            send_telegram_notification(task_id, task_title, "cancelled", "Ακυρώθηκε από τον χρήστη", duration)
            try:
                proc.kill()
            except Exception:
                pass
            raise

        except TimeoutError as e:
            duration = (datetime.now() - task_start).total_seconds()
            log.error(f"[Script Task #{task_id}] TIMEOUT: {e}")
            memory.update_task(task_id, status="failed", error=str(e))
            _broadcast_event("task_error", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "subagent": subagent_name,
                "error": str(e),
                "duration_s": round(duration, 1),
            })
            send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"TIMEOUT: {e}", duration=duration)
            send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=f"Script timeout μετά από {duration:.0f}s", duration=duration)

        except Exception as e:
            duration = (datetime.now() - task_start).total_seconds()
            log.error(f"[Script Task #{task_id}] Error: {e}", exc_info=True)
            memory.update_task(task_id, status="failed", error=str(e))
            _broadcast_event("task_error", {
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "subagent": subagent_name,
                "error": str(e),
                "duration_s": round(duration, 1),
            })
            send_task_notification(task_id=task_id, task_title=task_title, status="failed", result=f"ERROR: {str(e)}", duration=duration)
            send_telegram_notification(task_id=task_id, task_title=task_title, status="failed", result=f"Script error: {str(e)[:300]}", duration=duration)

        finally:
            running_task_ids.discard(task_id)
            running_asyncio_tasks.pop(task_id, None)
            agent_status["running_tasks"].pop(task_id, None)
            if not agent_status["running_tasks"]:
                agent_status["state"] = "idle"


async def run_agent_cycle(reason: str = "scheduled"):
    """Orchestrate a cycle: gather tasks and launch parallel execution."""
    cycle_start = datetime.now()
    cycle_session = f"cycle_{cycle_start.strftime('%Y%m%d_%H%M%S')}"
    agent_status["last_cycle"] = cycle_start.isoformat()

    # Increment cycle counter
    prev_count = memory.kv_get("daemon_cycle_count", 0)
    try:
        prev_count = int(prev_count)
    except (TypeError, ValueError):
        prev_count = 0
    memory.kv_set("daemon_cycle_count", prev_count + 1)

    log.info(f"=== Cycle [{reason}]: {cycle_session} ===")
    _broadcast_event("cycle_start", {"session_id": cycle_session, "reason": reason})

    # Gather due + pending tasks
    due_tasks = memory.get_due_tasks()
    pending_tasks = memory.get_pending_tasks(limit=MAX_TASKS_PER_CYCLE)
    stats = memory.get_task_stats()

    # Merge and deduplicate (due tasks first, then pending)
    seen_ids = set()
    all_tasks = []
    for t in due_tasks + pending_tasks:
        tid = t["id"]
        if tid not in seen_ids and tid not in running_task_ids:
            seen_ids.add(tid)
            all_tasks.append(t)

    log.info(f"Due: {len(due_tasks)}, Pending: {len(pending_tasks)}, "
             f"Already running: {len(running_task_ids)}, To launch: {len(all_tasks)}")

    if not all_tasks:
        log.info("Nothing to do")
        _broadcast_event("cycle_end", {
            "session_id": cycle_session,
            "reason": reason,
            "result": "no_tasks",
            "tasks_launched": 0,
            "duration_s": 0,
        })
        return "No tasks to process"

    # Cap at MAX_TASKS_PER_CYCLE
    tasks_to_run = all_tasks[:MAX_TASKS_PER_CYCLE]

    # Log detailed task routing info
    subagent_tasks = [t for t in tasks_to_run if t.get("assigned_to")]
    global_tasks = [t for t in tasks_to_run if not t.get("assigned_to")]
    log.info(f"Launching {len(tasks_to_run)} task(s): {len(global_tasks)} global, {len(subagent_tasks)} subagent (max concurrent: {MAX_CONCURRENT_TASKS})")
    for t in tasks_to_run:
        sa = t.get("assigned_to")
        route_label = f"-> subagent '{sa}'" if sa else "-> global daemon"
        log.info(f"  Task #{t['id']} '{t.get('title', '')[:60]}' [pri:{t.get('priority', 5)}] {route_label}")

    # Launch all tasks as fire-and-forget background tasks.
    # Previously used asyncio.gather() which BLOCKED the scheduler until ALL tasks
    # finished — a 2-hour script task would prevent new tasks from being picked up.
    # Now tasks run independently; the semaphore still limits concurrency.
    # Route: task_type=script → execute_script_task (direct subprocess, no AI)
    #        assigned_to → execute_subagent_task (AI agent with subagent prompt)
    #        else → execute_single_task (general daemon agent)
    agent_status["state"] = "running"
    for t in tasks_to_run:
        if t.get("assigned_to"):
            # Check if this subagent uses direct script execution
            sa_def = _parse_subagent_md(t["assigned_to"])
            if sa_def.get("task_type") == "script" and sa_def.get("command"):
                log.info(f"  Routing Task #{t['id']} to execute_script_task('{t['assigned_to']}') [DIRECT SCRIPT]")
                atask = asyncio.create_task(execute_script_task(t, cycle_session))
            else:
                log.info(f"  Routing Task #{t['id']} to execute_subagent_task('{t['assigned_to']}')")
                atask = asyncio.create_task(execute_subagent_task(t, cycle_session))
        else:
            log.info(f"  Routing Task #{t['id']} to execute_single_task()")
            atask = asyncio.create_task(execute_single_task(t, cycle_session))
        running_asyncio_tasks[t["id"]] = atask

    duration = (datetime.now() - cycle_start).total_seconds()
    log.info(f"=== Cycle launched: {duration:.1f}s, {len(tasks_to_run)} tasks fired ===")

    _broadcast_event("cycle_end", {
        "session_id": cycle_session,
        "reason": reason,
        "duration_s": round(duration, 1),
        "tasks_launched": len(tasks_to_run),
    })

    return f"Cycle launched: {len(tasks_to_run)} tasks in {duration:.1f}s"


# ─────────────────────────────────────────────────────────
# Heartbeat Proactivity
# ─────────────────────────────────────────────────────────

async def _maybe_run_heartbeat():
    """Check if it's time for a heartbeat and execute if so.

    Heartbeat reviews recent activity and proactively reaches out via Telegram
    if there's something worth telling the user. Controlled by config:
        heartbeat_enabled: true/false
        heartbeat_interval_hours: 4  (default)
        heartbeat_quiet_start: 23   (default, hour 0-23)
        heartbeat_quiet_end: 8      (default, hour 0-23)
    """
    cfg = load_config()
    if not cfg.get("heartbeat_enabled", False):
        return

    interval_hours = cfg.get("heartbeat_interval_hours", 4)
    quiet_start = cfg.get("heartbeat_quiet_start", 23)
    quiet_end = cfg.get("heartbeat_quiet_end", 8)

    # Check quiet hours
    current_hour = datetime.now().hour
    if quiet_start > quiet_end:
        # Wraps midnight: e.g. 23-8 means quiet from 23:00 to 08:00
        if current_hour >= quiet_start or current_hour < quiet_end:
            log.debug("Heartbeat skipped: quiet hours")
            return
    else:
        if quiet_start <= current_hour < quiet_end:
            log.debug("Heartbeat skipped: quiet hours")
            return

    # Check if enough time has passed since last heartbeat
    last_heartbeat = memory.kv_get("last_heartbeat_at")
    if last_heartbeat:
        try:
            last_dt = datetime.fromisoformat(last_heartbeat)
            elapsed_hours = (datetime.now() - last_dt).total_seconds() / 3600
            if elapsed_hours < interval_hours:
                return
        except (ValueError, TypeError):
            pass

    # Time for a heartbeat
    log.info("HEARTBEAT: Starting proactive check")

    # Load heartbeat checklist if available
    heartbeat_checklist = ""
    heartbeat_file = get_persona_dir() / "HEARTBEAT.md"
    if heartbeat_file.exists():
        try:
            heartbeat_checklist = heartbeat_file.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass

    # Build heartbeat prompt
    context = memory.build_context_summary()
    heartbeat_prompt = (
        f"HEARTBEAT CHECK — {datetime.now().isoformat()}\n\n"
        f"You are performing a periodic proactive check. Review the current state and decide "
        f"if there's anything worth telling the user via Telegram.\n\n"
        f"{context}\n\n"
    )
    if heartbeat_checklist:
        heartbeat_prompt += f"## Heartbeat Checklist\n{heartbeat_checklist}\n\n"
    heartbeat_prompt += (
        "## Instructions\n"
        "1. Review the context above\n"
        "2. Check pending/overdue tasks, recent completions, upcoming deadlines\n"
        "3. If there's something actionable or noteworthy for the user:\n"
        "   - Send a brief, helpful Telegram message using the notification system\n"
        "   - Write in Greek, keep it concise and natural\n"
        "4. If nothing notable: just log 'HEARTBEAT_OK' and stop\n"
        "5. `agelclaw-mem log \"HEARTBEAT: <summary>\"`\n"
    )

    try:
        route = _router.route(task_type="heartbeat")

        if route.provider == Provider.OPENAI:
            agent = get_agent(provider="openai", model=route.model)
            result = await agent.run(
                prompt=heartbeat_prompt,
                system_prompt=_get_daemon_prompt(),
                tools=ALLOWED_TOOLS,
                cwd=str(proactive_dir),
                max_turns=10,
            )
            log.info(f"HEARTBEAT completed (OpenAI): {(result or '')[:200]}")
        else:
            # Load auto-loaded MCP servers for heartbeat
            mcp_configs, _ = _scan_mcp_servers()
            hb_allowed = list(AGENT_TOOLS)
            if mcp_configs:
                hb_allowed += _build_mcp_tool_wildcards(mcp_configs)

            options = ClaudeAgentOptions(
                system_prompt=_get_daemon_prompt(),
                allowed_tools=hb_allowed,
                setting_sources=["user", "project"],
                permission_mode="bypassPermissions",
                cwd=str(proactive_dir),
                max_turns=10,
            )
            if mcp_configs:
                options.mcp_servers = mcp_configs

            response_parts = []
            async for message in query(prompt=heartbeat_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
            log.info(f"HEARTBEAT completed (Claude): {''.join(response_parts)[:200]}")

        # Only record timestamp AFTER successful execution
        memory.kv_set("last_heartbeat_at", datetime.now().isoformat())

    except Exception as e:
        log.error(f"HEARTBEAT failed: {e}", exc_info=True)
        # Set retry timestamp 15 minutes from now instead of full interval
        retry_at = datetime.now() - timedelta(hours=interval_hours) + timedelta(minutes=15)
        memory.kv_set("last_heartbeat_at", retry_at.isoformat())
        log.info(f"HEARTBEAT will retry after {retry_at.isoformat()}")


# ─────────────────────────────────────────────────────────
# Background scheduler
# ─────────────────────────────────────────────────────────

async def scheduler_loop():
    """Runs cycles on schedule OR when woken up by the API.

    Smart scheduling: instead of sleeping a fixed CHECK_INTERVAL,
    calculates the time until the next due task and sleeps only that long.
    This ensures scheduled tasks execute on time (not up to 5 minutes late).
    """
    log.info(f"Scheduler started (max interval: {CHECK_INTERVAL}s)")

    while True:
        # Calculate dynamic timeout: sleep until next due task or CHECK_INTERVAL
        next_due = memory.get_next_due_time()
        if next_due:
            seconds_until_due = (next_due - datetime.now()).total_seconds()
            if seconds_until_due <= 0:
                # Task already due, run immediately
                timeout = 0.1
            elif seconds_until_due <= CHECK_INTERVAL:
                # Due sooner than normal interval — wake up just after it's due
                timeout = seconds_until_due + 1  # +1s to ensure it's past due_at
            else:
                timeout = CHECK_INTERVAL
            log.info(f"Next due task at {next_due.isoformat()}, sleeping {timeout:.0f}s")
        else:
            timeout = CHECK_INTERVAL

        # Wait for either: calculated timeout OR wake_event
        try:
            await asyncio.wait_for(wake_event.wait(), timeout=timeout)
            wake_event.clear()
            reason = "api_trigger"
            log.info("Woken up by API trigger!")
        except asyncio.TimeoutError:
            reason = "scheduled"

        try:
            await run_agent_cycle(reason=reason)
        except Exception as e:
            log.error(f"Cycle crashed: {e}", exc_info=True)

        # Heartbeat: proactive check after each cycle
        try:
            await _maybe_run_heartbeat()
        except Exception as e:
            log.error(f"Heartbeat check failed: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────
# FastAPI HTTP Server
# ─────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn


class TaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: int = 5
    category: str = "general"
    due_at: Optional[str] = None
    recurring_cron: Optional[str] = None
    context: Optional[dict] = None
    assigned_to: Optional[str] = None
    wake_agent: bool = True  # Immediately wake the daemon


class TaskResponse(BaseModel):
    task_id: int
    status: str
    message: str


async def _watchdog_loop():
    """Safety net: kill tasks that exceed timeout even if asyncio.wait_for didn't fire.

    Runs every 30s, checks all running tasks against their effective timeout + 20% grace.
    """
    log.info("Watchdog started (30s interval)")
    while True:
        await asyncio.sleep(30)
        now = datetime.now()
        for task_id, info in list(agent_status["running_tasks"].items()):
            try:
                started = datetime.fromisoformat(info["started_at"])
                elapsed = (now - started).total_seconds()
                effective_timeout = info.get("timeout", TASK_TIMEOUT)
                hard_limit = effective_timeout * 1.2  # 20% grace period
                if elapsed > hard_limit:
                    log.error(f"WATCHDOG: Task #{task_id} force-killed ({elapsed:.0f}s > {hard_limit:.0f}s hard limit)")
                    atask = running_asyncio_tasks.get(task_id)
                    if atask and not atask.done():
                        atask.cancel()
                    # Mark failed if still in_progress
                    t = memory.get_task(task_id)
                    if t and t["status"] == "in_progress":
                        memory.update_task(task_id, status="failed",
                            error=f"Watchdog: exceeded {hard_limit:.0f}s hard limit ({elapsed:.0f}s elapsed)")
                        send_telegram_notification(task_id, info.get("title", "?"), "failed",
                            f"Watchdog — ξεπέρασε {hard_limit:.0f}s, τερματίστηκε αυτόματα", elapsed)
            except Exception as e:
                log.warning(f"WATCHDOG: Error checking task #{task_id}: {e}")


def _cleanup_stale_tasks():
    """Reset any tasks stuck in in_progress from a previous daemon crash."""
    try:
        with memory._conn() as conn:
            stale_tasks = conn.execute(
                "SELECT id, title FROM tasks WHERE status='in_progress'"
            ).fetchall()
        for t in stale_tasks:
            log.warning(f"Startup cleanup: Task #{t['id']} '{t['title']}' was in_progress — resetting to pending")
            memory.update_task(t["id"], status="pending")
        if stale_tasks:
            log.info(f"Startup cleanup: reset {len(stale_tasks)} stale task(s) to pending")
    except Exception as e:
        log.error(f"Startup cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clean up stale tasks from previous crash
    _cleanup_stale_tasks()

    # Start the scheduler and watchdog as background tasks
    scheduler_task = asyncio.create_task(scheduler_loop())
    watchdog_task = asyncio.create_task(_watchdog_loop())
    log.info(f"API server starting on port {API_PORT}")
    yield
    watchdog_task.cancel()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Self-Evolving Agent API",
    description="Submit tasks, check status, manage the autonomous agent",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/task", response_model=TaskResponse)
async def add_task(req: TaskRequest):
    """
    Add a new task. If wake_agent=true, the daemon picks it up immediately.
    
    Examples:
      POST /task {"title": "Scrape prices from Eurolife", "priority": 2}
      POST /task {"title": "Daily report", "recurring_cron": "daily_09:00"}
    """
    task_id = memory.add_task(
        title=req.title,
        description=req.description,
        priority=req.priority,
        category=req.category,
        due_at=req.due_at,
        recurring_cron=req.recurring_cron,
        context=req.context or {},
        assigned_to=req.assigned_to,
    )

    message = f"Task #{task_id} created"
    if req.assigned_to:
        message += f" (assigned to: {req.assigned_to})"

    if req.wake_agent:
        wake_event.set()  # Wakes daemon to recalculate next sleep timeout
        if req.due_at:
            message += f" — scheduled for {req.due_at}, daemon will wake on time"
        else:
            message += " — agent waking up now!"

    return TaskResponse(task_id=task_id, status="pending", message=message)


@app.get("/status")
async def get_status():
    """Current daemon state + task statistics + per-task health info."""
    stats = memory.get_task_stats()
    now = datetime.now()

    # Enrich running_tasks with elapsed/remaining time
    running_detail = {}
    for tid, info in agent_status["running_tasks"].items():
        try:
            started = datetime.fromisoformat(info["started_at"])
            elapsed = (now - started).total_seconds()
            timeout = info.get("timeout", TASK_TIMEOUT)
            running_detail[str(tid)] = {
                **info,
                "elapsed_s": round(elapsed, 1),
                "timeout_s": timeout,
                "remaining_s": round(max(0, timeout - elapsed), 1),
            }
        except Exception:
            running_detail[str(tid)] = info

    return {
        "agent": {
            "state": agent_status["state"],
            "running_tasks": running_detail,
            "last_cycle": agent_status["last_cycle"],
        },
        "tasks": stats,
        "daemon": {
            "check_interval": CHECK_INTERVAL,
            "max_tasks_per_cycle": MAX_TASKS_PER_CYCLE,
            "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
            "task_timeout": TASK_TIMEOUT,
            "task_inactivity_timeout": TASK_INACTIVITY_TIMEOUT,
            "script_timeout": SCRIPT_TIMEOUT,
            "uptime_since": memory.kv_get("daemon_last_start"),
            "total_cycles": memory.kv_get("daemon_cycle_count", 0),
            "watchdog": "active",
            "mcp_servers": list(_scan_mcp_servers()[0].keys()),
        },
    }


@app.get("/tasks")
async def get_tasks(status: str = "pending", limit: int = 20):
    """Get tasks by status."""
    with memory._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY priority ASC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/scheduled")
async def get_scheduled():
    """Get future scheduled tasks (not yet due)."""
    return memory.get_scheduled_tasks()


@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """Get a specific task with its conversation history."""
    task = memory.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    convos = memory.get_task_conversations(task_id)
    return {"task": task, "conversations": convos}


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: int):
    """Cancel a pending task."""
    task = memory.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ("pending", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {task['status']}")
    memory.update_task(task_id, status="cancelled")
    return {"message": f"Task #{task_id} cancelled"}


@app.post("/execute_task/{task_id}")
async def execute_task(task_id: int):
    """
    Execute a specific pending task immediately (without waiting for next cycle).

    Usage:
      POST /execute_task/34

    Returns:
      {"success": true/false, "message": "...", "task_id": 34}
    """
    # Get task from database
    task = memory.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{task_id} not found")

    if task["status"] != "pending":
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"Task #{task_id} is not pending (status: {task['status']})",
                "task_id": task_id,
            }
        )

    # Check if already running
    if task_id in running_task_ids:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": f"Task #{task_id} is already running",
                "task_id": task_id,
            }
        )

    # Execute the task immediately (in background) — route to subagent if assigned
    cycle_session = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if task.get("assigned_to"):
        atask = asyncio.create_task(execute_subagent_task(task, cycle_session))
    else:
        atask = asyncio.create_task(execute_single_task(task, cycle_session))
    running_asyncio_tasks[task_id] = atask

    return {
        "success": True,
        "message": f"Task #{task_id} '{task['title']}' started",
        "task_id": task_id,
    }


@app.post("/wake")
async def wake_agent():
    """Manually trigger an agent cycle right now."""
    wake_event.set()
    return {"message": "Agent waking up!"}


@app.get("/running")
async def get_running_tasks():
    """Get currently running tasks."""
    return agent_status["running_tasks"]


@app.post("/tasks/{task_id}/cancel")
async def cancel_running_task(task_id: int):
    """Cancel a currently running task."""
    if task_id not in running_task_ids:
        raise HTTPException(status_code=404, detail=f"Task #{task_id} is not running")

    atask = running_asyncio_tasks.get(task_id)
    if atask and not atask.done():
        atask.cancel()
        # Wait briefly for cleanup
        try:
            await asyncio.wait_for(asyncio.shield(atask), timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    return {"message": f"Task #{task_id} cancelled"}


class TaskUpdateMessage(BaseModel):
    message: str


@app.post("/tasks/{task_id}/update")
async def update_running_task(task_id: int, req: TaskUpdateMessage):
    """Send an update to a running task. Cancels current execution and restarts with updated instructions."""
    task = memory.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{task_id} not found")

    was_running = task_id in running_task_ids

    # Cancel if running
    if was_running:
        atask = running_asyncio_tasks.get(task_id)
        if atask and not atask.done():
            atask.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(atask), timeout=5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass

    # Append update to task description
    now = datetime.now().isoformat()
    updated_desc = task["description"] + f"\n\n--- USER UPDATE ({now}) ---\n{req.message}"
    memory.update_task(task_id, description=updated_desc, status="pending")

    # Log the update
    memory.log_conversation(
        role="user",
        content=f"Update for Task #{task_id}: {req.message}",
        session_id=f"task_update_{task_id}",
    )

    # Re-execute immediately
    wake_event.set()

    action = "restarted with update" if was_running else "updated (will execute on next cycle)"
    return {"message": f"Task #{task_id} {action}", "update": req.message}


@app.get("/history")
async def get_history(limit: int = 30):
    """Recent conversation history."""
    return memory.get_conversation_history(limit=limit)


@app.get("/learnings")
async def get_learnings(category: str = None):
    """Agent learnings and patterns."""
    return memory.get_learnings(category=category)


@app.get("/skills")
async def get_skills():
    """Installed skills registry."""
    return memory.get_all_skills()


@app.get("/events")
async def events():
    """
    SSE (Server-Sent Events) endpoint for real-time daemon activity.

    Usage:
      curl -N http://localhost:8420/events

    Events: cycle_start, cycle_end, task_start, task_end, task_error, agent_text, tool_use
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_subscribers.append(q)

    async def event_stream():
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'connected', 'time': datetime.now().isoformat(), 'status': agent_status})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in sse_subscribers:
                sse_subscribers.remove(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────

async def run_daemon():
    """Entry point for `agelclaw daemon` CLI command."""
    import uvicorn as _uv
    os.environ.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "0")
    memory.kv_set("daemon_last_start", datetime.now().isoformat())
    memory.kv_set("daemon_status", "running")
    log.info("Agent Daemon starting (parallel execution + watchdog)")
    log.info(f"   API: http://localhost:{API_PORT}")
    log.info(f"   Interval: {CHECK_INTERVAL}s")
    log.info(f"   Max concurrent: {MAX_CONCURRENT_TASKS}")
    log.info(f"   Max tasks/cycle: {MAX_TASKS_PER_CYCLE}")
    log.info(f"   Task timeout: {TASK_TIMEOUT}s, inactivity: {TASK_INACTIVITY_TIMEOUT}s, script: {SCRIPT_TIMEOUT}s")
    log.info(f"   Database: {memory.db_path}")
    config = _uv.Config(app, host="0.0.0.0", port=API_PORT, log_level="info")
    server = _uv.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio as _asyncio
    _asyncio.run(run_daemon())
    # Remove output token limit — let Claude produce as much as needed
    os.environ.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "0")

    memory.kv_set("daemon_last_start", datetime.now().isoformat())
    memory.kv_set("daemon_status", "running")

    log.info("Agent Daemon v2 starting (parallel execution)")
    log.info(f"   API: http://localhost:{API_PORT}")
    log.info(f"   Interval: {CHECK_INTERVAL}s")
    log.info(f"   Max concurrent: {MAX_CONCURRENT_TASKS}")
    log.info(f"   Max tasks/cycle: {MAX_TASKS_PER_CYCLE}")
    log.info(f"   Database: {memory.db_path}")
    log.info(f"   Output token limit: {os.environ.get('CLAUDE_CODE_MAX_OUTPUT_TOKENS', 'default')}")

    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
