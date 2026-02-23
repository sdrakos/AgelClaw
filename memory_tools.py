"""
Memory MCP Tools
================
Exposes the persistent memory system as MCP tools
that the Claude agent can use autonomously.
"""

import json
from claude_agent_sdk import tool
from memory import Memory

memory = Memory()


# ─────────────────────────────────────────────────────────
# Task Management Tools
# ─────────────────────────────────────────────────────────

@tool(
    "memory_add_task",
    (
        "Add a new task to persistent memory. Use this to track work that needs "
        "to be done, including recurring tasks. Tasks persist across sessions."
    ),
    {
        "title": str,
        "description": str,
        "priority": int,        # 1=urgent, 10=low
        "category": str,        # e.g. "scraping", "email", "maintenance"
        "due_at": str,          # ISO datetime or empty
        "recurring_cron": str,  # e.g. "every_30m", "daily_09:00", "every_2h"
        "context": str,         # JSON string with extra data
    }
)
async def memory_add_task(args):
    context = {}
    if args.get("context"):
        try:
            context = json.loads(args["context"])
        except json.JSONDecodeError:
            context = {"raw": args["context"]}

    task_id = memory.add_task(
        title=args["title"],
        description=args.get("description", ""),
        priority=args.get("priority", 5),
        category=args.get("category", "general"),
        due_at=args.get("due_at") or None,
        recurring_cron=args.get("recurring_cron") or None,
        context=context,
    )
    return {"content": [{"type": "text", "text": f"✅ Task #{task_id} created: {args['title']}"}]}


@tool(
    "memory_get_pending_tasks",
    "Get all pending and in-progress tasks from memory, ordered by priority.",
    {}
)
async def memory_get_pending_tasks(args):
    tasks = memory.get_pending_tasks()
    if not tasks:
        return {"content": [{"type": "text", "text": "No pending tasks. All clear! 🎉"}]}

    lines = ["## Pending Tasks\n"]
    for t in tasks:
        status_icon = "🔄" if t["status"] == "in_progress" else "⏳"
        lines.append(
            f"{status_icon} **#{t['id']}** [{t['category']}] {t['title']} "
            f"(priority: {t['priority']}, retries: {t['retry_count']}/{t['max_retries']})"
        )
        if t.get("description"):
            lines.append(f"   {t['description'][:150]}")
        if t.get("recurring_cron"):
            lines.append(f"   🔁 Recurring: {t['recurring_cron']}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "memory_get_due_tasks",
    (
        "Get tasks that are due RIGHT NOW and need immediate execution. "
        "These are scheduled or recurring tasks whose time has come."
    ),
    {}
)
async def memory_get_due_tasks(args):
    tasks = memory.get_due_tasks()
    if not tasks:
        return {"content": [{"type": "text", "text": "No tasks due right now."}]}

    lines = ["## ⚠️ Tasks Due NOW\n"]
    for t in tasks:
        lines.append(
            f"🔴 **#{t['id']}** {t['title']} (priority: {t['priority']})"
        )
        if t.get("description"):
            lines.append(f"   {t['description'][:150]}")
        ctx = json.loads(t.get("context", "{}"))
        if ctx:
            lines.append(f"   Context: {json.dumps(ctx)[:200]}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "memory_start_task",
    "Mark a task as in_progress. Call this before starting work on a task.",
    {"task_id": int}
)
async def memory_start_task(args):
    memory.start_task(args["task_id"])
    return {"content": [{"type": "text", "text": f"🔄 Task #{args['task_id']} started."}]}


@tool(
    "memory_complete_task",
    (
        "Mark a task as completed with results. If the task is recurring, "
        "it will automatically be rescheduled for the next run."
    ),
    {"task_id": int, "result": str}
)
async def memory_complete_task(args):
    memory.complete_task(args["task_id"], args.get("result", ""))
    task = memory.get_task(args["task_id"])
    if task and task.get("recurring_cron"):
        return {"content": [{"type": "text", "text": (
            f"✅ Task #{args['task_id']} completed. "
            f"🔁 Next run scheduled: {task.get('next_run_at')}"
        )}]}
    return {"content": [{"type": "text", "text": f"✅ Task #{args['task_id']} completed."}]}


@tool(
    "memory_fail_task",
    "Mark a task as failed. It will auto-retry if under max_retries.",
    {"task_id": int, "error": str}
)
async def memory_fail_task(args):
    memory.fail_task(args["task_id"], args.get("error", ""))
    task = memory.get_task(args["task_id"])
    status = task["status"] if task else "unknown"
    return {"content": [{"type": "text", "text": (
        f"❌ Task #{args['task_id']} failed: {args.get('error', '')}. "
        f"Status: {status} (retry {task.get('retry_count', 0)}/{task.get('max_retries', 3)})"
    )}]}


# ─────────────────────────────────────────────────────────
# Conversation / History Tools
# ─────────────────────────────────────────────────────────

@tool(
    "memory_log",
    (
        "Log a conversation entry or important event to persistent memory. "
        "Use this to record what you did, decisions made, and outcomes."
    ),
    {"role": str, "content": str, "task_id": int, "session_id": str}
)
async def memory_log(args):
    memory.log_conversation(
        role=args.get("role", "assistant"),
        content=args["content"],
        task_id=args.get("task_id"),
        session_id=args.get("session_id"),
    )
    return {"content": [{"type": "text", "text": "📝 Logged to memory."}]}


@tool(
    "memory_get_history",
    "Get recent conversation history from persistent memory.",
    {"limit": int, "session_id": str}
)
async def memory_get_history(args):
    history = memory.get_conversation_history(
        session_id=args.get("session_id"),
        limit=args.get("limit", 20),
    )
    if not history:
        return {"content": [{"type": "text", "text": "No conversation history found."}]}

    lines = ["## Recent History\n"]
    for h in history:
        role_icon = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(h["role"], "?")
        lines.append(f"{role_icon} [{h['created_at']}] {h['content'][:200]}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ─────────────────────────────────────────────────────────
# Learning Tools
# ─────────────────────────────────────────────────────────

@tool(
    "memory_add_learning",
    (
        "Record an insight or learning for future reference. "
        "Use this when you discover something useful: a pattern that works, "
        "a common error, a user preference, or an optimization."
    ),
    {"category": str, "insight": str, "confidence": float}
)
async def memory_add_learning(args):
    learning_id = memory.add_learning(
        category=args["category"],
        insight=args["insight"],
        confidence=args.get("confidence", 0.5),
    )
    return {"content": [{"type": "text", "text": f"🧠 Learning #{learning_id} saved."}]}


@tool(
    "memory_get_learnings",
    "Retrieve learnings from memory, optionally filtered by category.",
    {"category": str, "limit": int}
)
async def memory_get_learnings(args):
    learnings = memory.get_learnings(
        category=args.get("category"),
        limit=args.get("limit", 10),
    )
    if not learnings:
        return {"content": [{"type": "text", "text": "No learnings recorded yet."}]}

    lines = ["## Learnings\n"]
    for l in learnings:
        conf = "🟢" if l["confidence"] > 0.7 else "🟡" if l["confidence"] > 0.4 else "🔴"
        lines.append(f"{conf} [{l['category']}] {l['insight']}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ─────────────────────────────────────────────────────────
# KV Store Tools
# ─────────────────────────────────────────────────────────

@tool(
    "memory_kv_set",
    "Store a key-value pair in persistent memory. Use for settings, state, counters.",
    {"key": str, "value": str}
)
async def memory_kv_set(args):
    memory.kv_set(args["key"], args["value"])
    return {"content": [{"type": "text", "text": f"💾 Saved: {args['key']}"}]}


@tool(
    "memory_kv_get",
    "Retrieve a value from persistent memory by key.",
    {"key": str}
)
async def memory_kv_get(args):
    value = memory.kv_get(args["key"])
    if value is None:
        return {"content": [{"type": "text", "text": f"Key '{args['key']}' not found."}]}
    return {"content": [{"type": "text", "text": f"{args['key']} = {json.dumps(value)}"}]}


# ─────────────────────────────────────────────────────────
# Full Context Tool (injected into every prompt)
# ─────────────────────────────────────────────────────────

@tool(
    "memory_get_full_context",
    (
        "Get a complete summary of the agent's current state: "
        "pending tasks, due tasks, recent completions, skills, and learnings. "
        "USE THIS AT THE START OF EVERY SESSION to understand what's going on."
    ),
    {}
)
async def memory_get_full_context(args):
    context = memory.build_context_summary()
    return {"content": [{"type": "text", "text": context}]}


# ─────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────

@tool(
    "memory_get_stats",
    "Get task statistics: counts by status, total tasks, etc.",
    {}
)
async def memory_get_stats(args):
    stats = memory.get_task_stats()
    return {"content": [{"type": "text", "text": json.dumps(stats, indent=2)}]}


# ─────────────────────────────────────────────────────────
# Export all tools
# ─────────────────────────────────────────────────────────

ALL_MEMORY_TOOLS = [
    memory_add_task,
    memory_get_pending_tasks,
    memory_get_due_tasks,
    memory_start_task,
    memory_complete_task,
    memory_fail_task,
    memory_log,
    memory_get_history,
    memory_add_learning,
    memory_get_learnings,
    memory_kv_set,
    memory_kv_get,
    memory_get_full_context,
    memory_get_stats,
]
