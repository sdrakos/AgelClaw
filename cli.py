"""
Interactive CLI
===============
Chat with the agent AND manage tasks.

The daemon (daemon_v2.py) runs in background via PM2 and picks up tasks.
This CLI lets you:
- Chat with the agent directly
- Add tasks that the daemon will execute
- View task status, history, learnings
- Manage skills
"""

import asyncio
import json
import sys
import io
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from memory import Memory

memory = Memory()
PROACTIVE_DIR = Path(__file__).resolve().parent


SYSTEM_PROMPT = """You are a self-evolving virtual assistant with persistent memory and auto-research capabilities.

You have access to a persistent memory system (SQLite) where ALL tasks, conversations,
learnings, and state are stored. A background daemon processes tasks automatically.

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

### Scheduling (due_at and recurring params):
  due_at: ISO datetime, e.g. "2026-02-16T09:00:00"
  recurring:
    "daily_HH:MM"        → every day at HH:MM
    "weekly_D_HH:MM"     → every week (0=Mon, 6=Sun)
    "every_Xm" / "every_Xh" → interval
  Example: python mem_cli.py add_task "Daily report" "Run email digest" 3 "2026-02-16T09:00:00" "daily_09:00"

### Skill commands:
  python mem_cli.py skills                           # List installed skills
  python mem_cli.py find_skill "<description>"       # Find matching skill
  python mem_cli.py skill_content <name>             # Get skill content
  python mem_cli.py create_skill <name> "<desc>" "<body>" [location]
  python mem_cli.py add_script <skill> <file> "<code>"
  python mem_cli.py add_ref <skill> <file> "<content>"
  python mem_cli.py update_skill <name> "<body>"

## HOW IT WORKS
- User adds tasks via this chat → stored in memory
- Background daemon (PM2) picks up tasks and executes them
- You can also execute tasks directly in this chat

## COMMANDS
When the user says:
- "add task: ..." → python mem_cli.py add_task "..." "..."
- "status" / "tasks" → python mem_cli.py pending
- "history" → python mem_cli.py context
- "skills" → python mem_cli.py skills
- "stats" → python mem_cli.py stats
- "learnings" → python mem_cli.py get_learnings

## CONTEXT
Always start by running: python mem_cli.py context

## SKILL-FIRST EXECUTION (follow this for EVERY task)
Before executing ANY task:
1. Run: python mem_cli.py find_skill "<task description>"
2. If skill found → run: python mem_cli.py skill_content <name> → follow instructions
3. If NO skill found:
   a. Research the topic using available tools (Bash, Read, Grep, web lookups)
   b. Create skill: python mem_cli.py create_skill <name> "<desc>" "<body>"
   c. Add scripts: python mem_cli.py add_script <name> <file> "<code>"
   d. Add references if needed
   e. Execute the task using the newly created skill
4. After execution: update skill body if improvements found

## PROACTIVE
- Suggest related tasks when the user adds one
- Note if similar tasks have been done before
- Always create skills for new domains so they can be reused
- Save learnings after discovering something useful

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

## CRITICAL: NEVER ASK THE USER TO RUN COMMANDS
- You are an AUTONOMOUS agent. NEVER output "run this command" or "you can do X".
- If something needs to run → RUN IT YOURSELF via Bash.
- If something needs scheduling → CREATE a recurring task yourself:
    python mem_cli.py add_task "<title>" "<desc>" <pri> "<due_at_iso>" "<recurring>"
  The daemon picks it up automatically.
- If dependencies are missing → INSTALL THEM YOURSELF.
- WRONG: "To schedule this, run: python script.py --schedule"
- CORRECT: *actually create the task* → "Done. Recurring task created, daemon handles it."
"""


async def run_query(user_input: str) -> str:
    """Send a single query and collect the response."""
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        setting_sources=["user", "project"],
        permission_mode="acceptEdits",
        cwd=str(PROACTIVE_DIR),
        max_turns=30,
    )

    full_response = []

    async for message in query(prompt=user_input, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
                    full_response.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"\n   > {block.name}", flush=True)

    return "\n".join(full_response)


async def main():
    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    print("Self-Evolving Assistant (Interactive)")
    print("   Memory: persistent (SQLite)")
    print("   Daemon: runs via PM2 in background")
    print()
    print("   Commands: 'status', 'history', 'skills', 'stats', 'quit'")
    print("   Or just chat naturally!")
    print()

    # Show quick status
    stats = memory.get_task_stats()
    due = memory.get_due_tasks()
    print(f"   Tasks: {stats.get('pending', 0)} pending, "
          f"{stats.get('completed', 0)} completed, "
          f"{stats.get('failed', 0)} failed")
    if due:
        print(f"   {len(due)} tasks are due now!")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        if not user_input:
            continue

        # Quick local commands (no agent call needed)
        if user_input.lower() == "stats":
            s = memory.get_task_stats()
            print(f"\n{json.dumps(s, indent=2)}\n")
            continue

        # Log user message
        memory.log_conversation(role="user", content=user_input)

        # Send to agent
        print("\nAgent: ", end="", flush=True)
        response = await run_query(user_input)
        print("\n")

        # Log agent response
        memory.log_conversation(
            role="assistant",
            content=response[:2000],
        )


if __name__ == "__main__":
    asyncio.run(main())
