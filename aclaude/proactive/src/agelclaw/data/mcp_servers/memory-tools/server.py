"""
Memory Tools MCP Server
========================
Native MCP interface to AgelClaw's persistent memory, tasks, skills, and subagents.
Replaces agelclaw-mem CLI bridge with direct MCP tool calls.

Started by claude.exe as a stdio MCP server.
Requires AGELCLAW_HOME env var or discoverable project directory.
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Bootstrap: find the AgelClaw package ──
# The server runs as a subprocess of claude.exe, so we need to find the package.
# Try import directly first (pip installed), then try adding src to path.
try:
    from agelclaw.memory import Memory
    from agelclaw.project import get_project_dir, get_skills_dir, get_subagents_dir, get_mcp_servers_dir
except ImportError:
    # Dev mode: add src/ to path (server.py is 5 levels deep: data/mcp_servers/name/server.py → src/)
    _src = Path(__file__).resolve().parent.parent.parent.parent.parent
    if (_src / "agelclaw").is_dir():
        sys.path.insert(0, str(_src))
    from agelclaw.memory import Memory
    from agelclaw.project import get_project_dir, get_skills_dir, get_subagents_dir, get_mcp_servers_dir

memory = Memory()
server = Server("memory-tools")


# ── Tool definitions ──

TOOLS = [
    Tool(
        name="context",
        description="Get full context summary: pending tasks, recent activity, key learnings, user profile",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="pending",
        description="Get pending tasks (status=pending, ready to execute now)",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max tasks to return (default 10)"}},
            "required": [],
        },
    ),
    Tool(
        name="due",
        description="Get due scheduled tasks (next_run_at <= now)",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="scheduled",
        description="Get future scheduled tasks (next_run_at > now)",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="completed",
        description="Get recently completed tasks",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max tasks (default 10)"}},
            "required": [],
        },
    ),
    Tool(
        name="stats",
        description="Get task statistics: counts by status, recent completions",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="get_task",
        description="Get full details for a specific task by ID",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Task ID"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="add_task",
        description="Create a new task",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Task description"},
                "priority": {"type": "integer", "description": "Priority 1-5 (default 3)"},
                "due_at": {"type": "string", "description": "ISO datetime for when to execute"},
                "recurring": {"type": "string", "description": "Recurrence pattern: daily_HH:MM, weekly_D_HH:MM, every_Xm, every_Xh"},
                "assigned_to": {"type": "string", "description": "Subagent name to assign to"},
            },
            "required": ["title"],
        },
    ),
    Tool(
        name="start_task",
        description="Mark a task as in_progress",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Task ID"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="complete_task",
        description="Mark a task as completed with a result message",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Task ID"},
                "result": {"type": "string", "description": "Completion result/summary"},
            },
            "required": ["id", "result"],
        },
    ),
    Tool(
        name="fail_task",
        description="Mark a task as failed with an error message",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Task ID"},
                "error": {"type": "string", "description": "Error description"},
            },
            "required": ["id", "error"],
        },
    ),
    Tool(
        name="log",
        description="Log a message to the activity log",
        inputSchema={
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Message to log"}},
            "required": ["message"],
        },
    ),
    Tool(
        name="add_learning",
        description="Record a learning/insight for future reference",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category (e.g. 'python', 'user_preference', 'debugging')"},
                "content": {"type": "string", "description": "The learning content"},
            },
            "required": ["category", "content"],
        },
    ),
    Tool(
        name="rules",
        description="List active hard rules (promoted learnings injected into every prompt)",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="profile",
        description="View user profile facts (all or filtered by category)",
        inputSchema={
            "type": "object",
            "properties": {"category": {"type": "string", "description": "Optional category filter"}},
            "required": [],
        },
    ),
    Tool(
        name="set_profile",
        description="Set a user profile fact",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category (e.g. 'preferences', 'work', 'personal')"},
                "key": {"type": "string", "description": "Fact key"},
                "value": {"type": "string", "description": "Fact value"},
                "confidence": {"type": "number", "description": "Confidence 0.0-1.0 (default 0.8)"},
                "source": {"type": "string", "description": "How this was learned (default 'conversation')"},
            },
            "required": ["category", "key", "value"],
        },
    ),
    Tool(
        name="skills",
        description="List installed skills with descriptions",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="find_skill",
        description="Find the best matching skill for a task description",
        inputSchema={
            "type": "object",
            "properties": {"description": {"type": "string", "description": "What you want to do"}},
            "required": ["description"],
        },
    ),
    Tool(
        name="subagents",
        description="List installed subagent definitions",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="add_subagent_task",
        description="Create a task assigned to a specific subagent for background execution",
        inputSchema={
            "type": "object",
            "properties": {
                "subagent": {"type": "string", "description": "Subagent name"},
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Task description with all details"},
                "priority": {"type": "integer", "description": "Priority 1-5 (default 3)"},
                "due_at": {"type": "string", "description": "ISO datetime (only for scheduled tasks)"},
                "recurring": {"type": "string", "description": "Recurrence pattern"},
            },
            "required": ["subagent", "title"],
        },
    ),
    Tool(
        name="mcp_servers",
        description="List installed MCP servers",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = _handle_tool(name, arguments)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


def _handle_tool(name: str, args: dict) -> str:
    """Dispatch tool calls to memory operations."""

    if name == "context":
        return memory.build_context_summary()

    elif name == "pending":
        limit = args.get("limit", 10)
        tasks = memory.get_pending_tasks(limit=limit)
        return json.dumps(tasks, indent=2, default=str)

    elif name == "due":
        tasks = memory.get_due_tasks()
        return json.dumps(tasks, indent=2, default=str)

    elif name == "scheduled":
        tasks = memory.get_scheduled_tasks()
        if not tasks:
            return "No scheduled tasks."
        lines = []
        for t in tasks:
            lines.append(f"  #{t['id']} [{t.get('next_run_at', '?')}] {t['title']}"
                         + (f" (assigned: {t['assigned_to']})" if t.get('assigned_to') else "")
                         + (f" [recurring: {t['recurring_cron']}]" if t.get('recurring_cron') else ""))
        return "\n".join(lines)

    elif name == "completed":
        limit = args.get("limit", 10)
        tasks = memory.get_recent_completed(limit=limit)
        return json.dumps(tasks, indent=2, default=str)

    elif name == "stats":
        return json.dumps(memory.get_task_stats(), indent=2, default=str)

    elif name == "get_task":
        task = memory.get_task(args["id"])
        if not task:
            return f"Task #{args['id']} not found."
        return json.dumps(task, indent=2, default=str)

    elif name == "add_task":
        task_id = memory.add_task(
            title=args["title"],
            description=args.get("description", ""),
            priority=args.get("priority", 3),
            due_at=args.get("due_at"),
            recurring_cron=args.get("recurring"),
            assigned_to=args.get("assigned_to"),
        )
        # Notify daemon
        _wake_daemon(task_id, args["title"])
        return f"Task #{task_id} created: {args['title']}"

    elif name == "start_task":
        memory.start_task(args["id"])
        return f"Task #{args['id']} marked as in_progress."

    elif name == "complete_task":
        memory.complete_task(args["id"], result=args["result"])
        return f"Task #{args['id']} completed."

    elif name == "fail_task":
        memory.update_task(args["id"], status="failed", error=args["error"])
        return f"Task #{args['id']} marked as failed."

    elif name == "log":
        memory.log_conversation(role="system", content=args["message"])
        return "Logged."

    elif name == "add_learning":
        lid = memory.add_learning(args["category"], args["content"])
        return f"Learning #{lid} added in category '{args['category']}'."

    elif name == "rules":
        rules = memory.get_rules()
        if not rules:
            return "No active hard rules."
        lines = []
        for r in rules:
            lines.append(f"  #{r['id']} [{r['category']}] {r['insight'][:100]}")
        return "\n".join(lines)

    elif name == "profile":
        category = args.get("category")
        facts = memory.get_profile(category=category)
        if not facts:
            return f"No profile facts" + (f" in category '{category}'" if category else "") + "."
        lines = []
        for f in facts:
            lines.append(f"  [{f['category']}] {f['key']}: {f['value']}"
                         + (f" (confidence: {f['confidence']})" if f.get('confidence') else ""))
        return "\n".join(lines)

    elif name == "set_profile":
        memory.set_profile(
            category=args["category"],
            key=args["key"],
            value=args["value"],
            confidence=args.get("confidence", 0.8),
            source=args.get("source", "conversation"),
        )
        return f"Profile set: [{args['category']}] {args['key']} = {args['value']}"

    elif name == "skills":
        return _list_skills()

    elif name == "find_skill":
        return _find_skill(args["description"])

    elif name == "subagents":
        return _list_subagents()

    elif name == "add_subagent_task":
        task_id = memory.add_task(
            title=args["title"],
            description=args.get("description", ""),
            priority=args.get("priority", 3),
            due_at=args.get("due_at"),
            recurring_cron=args.get("recurring"),
            assigned_to=args["subagent"],
        )
        _wake_daemon(task_id, args["title"])
        return f"Task #{task_id} created and assigned to subagent '{args['subagent']}': {args['title']}"

    elif name == "mcp_servers":
        return _list_mcp_servers()

    else:
        return f"Unknown tool: {name}"


# ── Helper functions ──

def _wake_daemon(task_id: int, title: str):
    """Wake the daemon so it picks up the newly created task.
    The task already exists in the database — we only need to trigger a cycle.
    Previously this called POST /task which CREATED A DUPLICATE unassigned task."""
    try:
        from agelclaw.core.config import load_config
        cfg = load_config()
        port = cfg.get("daemon_port", 8420)
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/wake",
            data=b"",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass  # Daemon might not be running


def _list_skills() -> str:
    """List installed skills from .Claude/Skills/ directories."""
    import re
    skill_dirs = [
        get_skills_dir(),
        Path.home() / ".claude" / "skills",
    ]
    lines = []
    for root in skill_dirs:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            md = d / "SKILL.md"
            if not md.exists():
                continue
            try:
                content = md.read_text(encoding="utf-8", errors="replace")
                desc = ""
                fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                if fm:
                    dm = re.search(r'description:\s*(.+)', fm.group(1))
                    if dm:
                        desc = dm.group(1).strip().strip('"\'')[:100]
                lines.append(f"  {d.name}: {desc}" if desc else f"  {d.name}")
            except Exception:
                lines.append(f"  {d.name}")
    return "\n".join(lines) if lines else "No skills installed."


def _find_skill(description: str) -> str:
    """Find best matching skill by keyword search."""
    import re
    description_lower = description.lower()
    matches = []

    for root in [get_skills_dir(), Path.home() / ".claude" / "skills"]:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            md = d / "SKILL.md"
            if not md.exists():
                continue
            try:
                content = md.read_text(encoding="utf-8", errors="replace")
                content_lower = content.lower()
                # Score by keyword matches
                words = [w for w in description_lower.split() if len(w) > 2]
                score = sum(1 for w in words if w in content_lower)
                if score > 0 or d.name.lower() in description_lower:
                    fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                    desc = ""
                    if fm:
                        dm = re.search(r'description:\s*(.+)', fm.group(1))
                        if dm:
                            desc = dm.group(1).strip().strip('"\'')[:150]
                    matches.append((score + (5 if d.name.lower() in description_lower else 0), d.name, desc))
            except Exception:
                continue

    if not matches:
        return f"No skill found matching '{description}'. Consider creating one."

    matches.sort(key=lambda x: -x[0])
    lines = [f"Best matches for '{description}':"]
    for score, name, desc in matches[:5]:
        lines.append(f"  {name} (score: {score}): {desc}")
    return "\n".join(lines)


def _list_subagents() -> str:
    """List installed subagent definitions."""
    import re
    sa_dir = get_subagents_dir()
    if not sa_dir.exists():
        return "No subagents installed."

    lines = []
    for d in sorted(sa_dir.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SUBAGENT.md"
        if not md.exists():
            continue
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
            desc = ""
            fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if fm:
                dm = re.search(r'description:\s*(.+)', fm.group(1))
                if dm:
                    desc = dm.group(1).strip().strip('"\'')[:100]
            lines.append(f"  {d.name}: {desc}" if desc else f"  {d.name}")
        except Exception:
            lines.append(f"  {d.name}")
    return "\n".join(lines) if lines else "No subagents installed."


def _list_mcp_servers() -> str:
    """List installed MCP servers."""
    import re
    mcp_dir = get_mcp_servers_dir()
    if not mcp_dir.exists():
        return "No MCP servers installed."

    lines = []
    for d in sorted(mcp_dir.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SERVER.md"
        if not md.exists():
            continue
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
            desc = ""
            auto = False
            fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if fm:
                dm = re.search(r'description:\s*(.+)', fm.group(1))
                if dm:
                    desc = dm.group(1).strip().strip('"\'')[:100]
                al = re.search(r'auto_load:\s*(true|false)', fm.group(1), re.IGNORECASE)
                if al:
                    auto = al.group(1).lower() == "true"
            entry = f"  {d.name}"
            if desc:
                entry += f": {desc}"
            if auto:
                entry += " [auto-loaded]"
            lines.append(entry)
        except Exception:
            lines.append(f"  {d.name}")
    return "\n".join(lines) if lines else "No MCP servers installed."


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
