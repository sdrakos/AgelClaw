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
import json
import os
import sys
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)

from memory import Memory
from memory_tools import ALL_MEMORY_TOOLS
from skill_tools import ALL_SKILL_TOOLS

# ─────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────

from core.config import load_config
from core.agent_router import AgentRouter, Provider
from agent_config import get_agent, get_system_prompt, ALLOWED_TOOLS, _scan_installed_skills, _scan_installed_subagents

_cfg = load_config()
CHECK_INTERVAL = _cfg.get("check_interval", 300)
MAX_TASKS_PER_CYCLE = int(os.getenv("AGENT_MAX_TASKS", "5"))
MAX_CONCURRENT_TASKS = _cfg.get("max_concurrent_tasks", 3)
API_PORT = _cfg.get("daemon_port", 8420)
WEBHOOK_URL = os.getenv("AGENT_WEBHOOK_URL", "")  # POST cycle summaries here

_router = AgentRouter()
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "daemon.log"),
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

def send_task_notification(task_id: int, task_title: str, status: str, result: str, duration: float = None):
    """Send email notification when a task completes"""
    try:
        # Get path to notification script
        script_path = Path.home() / ".claude" / "skills" / "task-completion-notifier" / "scripts" / "task_notifier.py"
        if not script_path.exists():
            # Try project skills
            script_path = Path(__file__).parent.parent / ".Claude" / "Skills" / "task-completion-notifier" / "scripts" / "task_notifier.py"

        if not script_path.exists():
            log.warning(f"Notification script not found at {script_path}")
            return

        # Build command
        cmd = [
            sys.executable,
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
        log.info(f"✉️ Notification queued for task #{task_id}")

    except Exception as e:
        log.error(f"Failed to send notification for task #{task_id}: {e}")


# ─────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────

DAEMON_SYSTEM_PROMPT = """You are an autonomous self-evolving assistant running as a background daemon.
You execute tasks from your persistent memory WITHOUT any human input.

## MEMORY & SKILL CLI
Use `python mem_cli.py <command>` via Bash for ALL memory and skill operations:

### Memory commands:
  python mem_cli.py context                          # Full context summary
  python mem_cli.py pending [limit]                  # Pending tasks (ready now)
  python mem_cli.py due                              # Due scheduled tasks
  python mem_cli.py scheduled                        # Future scheduled tasks
  python mem_cli.py stats                            # Task statistics
  python mem_cli.py start_task <id>                  # Mark task in_progress
  python mem_cli.py complete_task <id> "<result>"    # Mark task completed
  python mem_cli.py fail_task <id> "<error>"         # Mark task failed
  python mem_cli.py add_task "<title>" "<desc>" [pri] [due_at] [recurring]
  python mem_cli.py log "<message>"                  # Log a message
  python mem_cli.py add_learning "<cat>" "<content>" # Add a learning
  python mem_cli.py get_learnings [category]         # Get learnings
  python mem_cli.py rules                            # List active hard rules
  python mem_cli.py promote_rule <id>                # Promote learning → hard rule
  python mem_cli.py demote_rule <id>                 # Demote rule → regular learning

### Scheduling:
  due_at format: ISO datetime, e.g. "2026-02-16T09:00:00"
  recurring formats:
    "daily_HH:MM"        → every day at HH:MM (e.g. "daily_09:00")
    "weekly_D_HH:MM"     → every week on day D at HH:MM (0=Mon, 6=Sun)
    "every_Xm"           → every X minutes (e.g. "every_30m")
    "every_Xh"           → every X hours (e.g. "every_2h")
  Example: python mem_cli.py add_task "Email report" "Run email digest" 3 "2026-02-16T09:00:00" "daily_09:00"

### Skill commands:
  python mem_cli.py skills                           # List installed skills
  python mem_cli.py find_skill "<description>"       # Find matching skill
  python mem_cli.py skill_content <name>             # Get skill content
  python mem_cli.py create_skill <name> "<desc>" "<body>" [location]
  python mem_cli.py add_script <skill> <file> "<code>"
  python mem_cli.py add_ref <skill> <file> "<content>"
  python mem_cli.py update_skill <name> "<body>"

### Subagent definition commands:
  python mem_cli.py subagents                        # List installed subagent definitions
  python mem_cli.py subagent_content <name>          # Get full SUBAGENT.md content
  python mem_cli.py create_subagent <name> "<desc>" "<body>"  # Create persistent subagent definition

### Task folder commands:
  python mem_cli.py task_folder <id>                 # Get/create task folder path

### Semantic search (AI-powered):
  python mem_cli.py search "<query>" [limit]                    # Search across all tables
  python mem_cli.py search "<query>" --table conversations      # Search specific table
  python mem_cli.py search "<query>" --table tasks              # Search tasks only
  python mem_cli.py embed_backfill                              # Backfill embeddings for existing data
  python mem_cli.py embed_stats                                 # Show embedding coverage

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
- This applies to: create_skill, create_subagent, any SKILL.md/SUBAGENT.md
VIOLATION: Creating a skill/subagent with just `import X` or a bare template is FORBIDDEN.

## STARTUP PROCEDURE (every cycle)
1. Run: python mem_cli.py context
2. Run: python mem_cli.py due
3. Run: python mem_cli.py pending
4. Execute tasks in priority order

## SKILL-FIRST EXECUTION (follow this for EVERY task)
Before executing ANY task:
1. Run: python mem_cli.py find_skill "<task description>"
2. If skill found → run: python mem_cli.py skill_content <name> → follow instructions
3. If NO skill found:
   a. Research the topic using available tools (Bash, Read, Grep)
   b. Create skill: python mem_cli.py create_skill <name> "<desc>" "<body>"
   c. Add scripts: python mem_cli.py add_script <name> <file> "<code>"
   d. Add references if needed: python mem_cli.py add_ref <name> <file> "<content>"
   e. Execute the task using the newly created skill
4. After execution: python mem_cli.py update_skill <name> "<updated body>" if improvements found

## TASK EXECUTION
For each task:
1. python mem_cli.py start_task <id>
2. Follow SKILL-FIRST EXECUTION above
3. Execute the task using skill scripts and instructions
4. python mem_cli.py complete_task <id> "<result summary>"
5. If failed: python mem_cli.py fail_task <id> "<error>"
6. python mem_cli.py log "<what you did>"
7. python mem_cli.py add_learning "<category>" "<content>" when you learn something

## SKILL CREATION RULES
- Create skills proactively — every new domain should get a skill
- Scripts must be self-contained, handle errors, and work on Windows
- Test scripts after creating them (run with python)
- Include real working examples in skill body, not placeholders
- Add API docs or schemas as references when dealing with external services
- For long code: use Write tool to create files, then add_script with a short wrapper

## TASK REPORTING
After completing a task, ALWAYS:
1. Write a detailed result via: python mem_cli.py complete_task <id> "<full result summary>"
2. If the task requested a "report" or "summary", also save it as a file:
   - Write the report to: proactive/reports/report_<task_id>_<YYYYMMDD_HHMMSS>.md
   - Include: task title, what was done, results, any data/findings
3. Log what you did: python mem_cli.py log "<summary>"
4. Add learnings if applicable

## PERSONALIZATION — YOU ARE A PERSONAL ASSISTANT
The context (python mem_cli.py context) includes the user's profile at the top.
Use it to personalize every interaction.

LEARNING ABOUT THE USER:
After EVERY conversation, extract and save new facts you learned:
  python mem_cli.py set_profile <category> <key> "<value>" [confidence] [source]

Categories:
  identity     — name, email, phone, company, role, title
  work         — projects, clients, domains, tech_stack, tools
  preferences  — language, communication_style, schedule, notifications
  relationships — colleagues, clients, contacts (key=person_name, value=context)
  habits       — working_hours, common_requests, patterns
  interests    — topics, hobbies, focus_areas

Rules:
- Stated facts (user told you directly) → confidence 0.9, source "stated"
- Inferred facts (you deduced from context) → confidence 0.6, source "inferred"
- Observed patterns (repeated behavior) → confidence 0.5, source "observed"
- ALWAYS save facts immediately — don't wait
- Update facts when new info contradicts old (confidence increases over time)

USING THE PROFILE:
- Address the user by name
- Respond in their preferred language
- Reference their work context when helping
- Remember their contacts when relevant
- Adapt to their communication style
- Suggest tasks/solutions based on their domain and tools

### Profile CLI:
  python mem_cli.py profile [category]                         # View profile
  python mem_cli.py set_profile <cat> <key> "<value>" [conf] [source]  # Set fact
  python mem_cli.py del_profile <cat> <key>                    # Delete fact

## RULES
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
- WRONG: "Run: python outlook_digest.py --schedule"
- CORRECT: Actually run it, or create a recurring task:
    python mem_cli.py add_task "Daily email digest" "Run outlook_digest.py" 3 "<next_run_iso>" "daily_09:00"
- The daemon handles recurring tasks automatically — no need for --schedule flags.
"""


def _get_daemon_prompt() -> str:
    """Build daemon system prompt with dynamically scanned skills, subagents, and hard rules."""
    return DAEMON_SYSTEM_PROMPT + _scan_installed_skills() + _scan_installed_subagents() + memory.build_rules_prompt()


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
        # Register as running
        running_task_ids.add(task_id)
        agent_status["running_tasks"][task_id] = {
            "title": task_title,
            "started_at": task_start.isoformat(),
            "session_id": session_id,
        }
        agent_status["state"] = "running"

        log.info(f">>> Task #{task_id} started: {task_title}")
        _broadcast_event("task_start", {
            "session_id": session_id,
            "task_id": task_id,
            "task_title": task_title,
            "cycle_session": cycle_session,
        })

        # Build a focused prompt for this single task
        context = memory.build_context_summary()
        proactive_dir = Path(__file__).resolve().parent
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
            f"WORKING DIR: {proactive_dir}\n"
            f"Execute ONLY this task. Save all outputs to: {task_folder}\n"
            f"Steps:\n"
            f"1. python mem_cli.py start_task {task_id}\n"
            f"2. Follow SKILL-FIRST EXECUTION from your instructions\n"
            f"3. Save all outputs (reports, data, scripts) to {task_folder}\n"
            f"4. python mem_cli.py complete_task {task_id} \"<result>\" (or fail_task on error)\n"
            f"5. python mem_cli.py log \"<summary>\"\n\n"
            f"Use `python mem_cli.py <command> [args]` via Bash for memory/skill operations."
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
                # Claude execution path (existing behavior)
                log.info(f"[Task #{task_id}] Using Claude ({route.model})")
                options = ClaudeAgentOptions(
                    system_prompt=_get_daemon_prompt(),
                    allowed_tools=["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                    setting_sources=["user", "project"],
                    permission_mode="bypassPermissions",
                    cwd=str(proactive_dir),
                    max_turns=30,
                )

                async for message in query(prompt=prompt_text, options=options):
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_response.append(block.text)
                                log.info(f"[Task #{task_id}] Agent: {block.text[:150]}")
                                _broadcast_event("agent_text", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "text": block.text[:500],
                                })
                            elif isinstance(block, ToolUseBlock):
                                tools_used.append(block.name)
                                log.info(f"[Task #{task_id}] Tool: {block.name}")
                                _broadcast_event("tool_use", {
                                    "session_id": session_id,
                                    "task_id": task_id,
                                    "task_title": task_title,
                                    "tool": block.name,
                                })

            duration = (datetime.now() - task_start).total_seconds()
            summary = "\n".join(full_response)[:2000]

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

            # Send email notification
            send_task_notification(
                task_id=task_id,
                task_title=task_title,
                status="completed",
                result=summary,
                duration=duration
            )

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

            # Send failure notification
            send_task_notification(
                task_id=task_id,
                task_title=task_title,
                status="failed",
                result=f"ERROR: {str(e)}",
                duration=duration
            )

        finally:
            # Clean up running state
            running_task_ids.discard(task_id)
            agent_status["running_tasks"].pop(task_id, None)
            if not agent_status["running_tasks"]:
                agent_status["state"] = "idle"


async def run_agent_cycle(reason: str = "scheduled"):
    """Orchestrate a cycle: gather tasks and launch parallel execution."""
    cycle_start = datetime.now()
    cycle_session = f"cycle_{cycle_start.strftime('%Y%m%d_%H%M%S')}"
    agent_status["last_cycle"] = cycle_start.isoformat()

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
    log.info(f"Launching {len(tasks_to_run)} task(s) in parallel (max concurrent: {MAX_CONCURRENT_TASKS})")

    # Launch all tasks concurrently — semaphore handles throttling
    agent_status["state"] = "running"
    coros = [execute_single_task(t, cycle_session) for t in tasks_to_run]
    await asyncio.gather(*coros, return_exceptions=True)

    duration = (datetime.now() - cycle_start).total_seconds()
    log.info(f"=== Cycle done: {duration:.1f}s, {len(tasks_to_run)} tasks launched ===")

    _broadcast_event("cycle_end", {
        "session_id": cycle_session,
        "reason": reason,
        "duration_s": round(duration, 1),
        "tasks_launched": len(tasks_to_run),
    })

    # Update state based on whether other tasks are still running
    if not agent_status["running_tasks"]:
        agent_status["state"] = "idle"

    return f"Cycle complete: {len(tasks_to_run)} tasks in {duration:.1f}s"


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
    wake_agent: bool = True  # Immediately wake the daemon


class TaskResponse(BaseModel):
    task_id: int
    status: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler as a background task
    scheduler_task = asyncio.create_task(scheduler_loop())
    log.info(f"API server starting on port {API_PORT}")
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
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
    )

    message = f"Task #{task_id} created"

    if req.wake_agent:
        wake_event.set()  # Wakes daemon to recalculate next sleep timeout
        if req.due_at:
            message += f" — scheduled for {req.due_at}, daemon will wake on time"
        else:
            message += " — agent waking up now!"

    return TaskResponse(task_id=task_id, status="pending", message=message)


@app.get("/status")
async def get_status():
    """Current daemon state + task statistics."""
    stats = memory.get_task_stats()
    return {
        "agent": agent_status,
        "tasks": stats,
        "daemon": {
            "check_interval": CHECK_INTERVAL,
            "max_tasks_per_cycle": MAX_TASKS_PER_CYCLE,
            "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
            "uptime_since": memory.kv_get("daemon_last_start"),
            "total_cycles": memory.kv_get("daemon_cycle_count", 0),
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


@app.post("/wake")
async def wake_agent():
    """Manually trigger an agent cycle right now."""
    wake_event.set()
    return {"message": "Agent waking up!"}


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

if __name__ == "__main__":
    memory.kv_set("daemon_last_start", datetime.now().isoformat())
    memory.kv_set("daemon_status", "running")

    log.info("🤖 Agent Daemon v2 starting (parallel execution)")
    log.info(f"   API: http://localhost:{API_PORT}")
    log.info(f"   Interval: {CHECK_INTERVAL}s")
    log.info(f"   Max concurrent: {MAX_CONCURRENT_TASKS}")
    log.info(f"   Max tasks/cycle: {MAX_TASKS_PER_CYCLE}")
    log.info(f"   Database: {memory.db_path}")

    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
