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
import os
import sys
import io

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
)

from agelclaw.memory import Memory
from agelclaw.agent_config import (
    get_system_prompt, build_prompt_with_history,
    PROACTIVE_DIR, SHARED_SESSION_ID, AGENT_TOOLS,
)

memory = Memory()


async def run_query(user_input: str) -> str:
    """Send a single query and collect the response."""
    prompt_with_history = build_prompt_with_history(user_input, memory)

    options = ClaudeAgentOptions(
        system_prompt=get_system_prompt(),
        allowed_tools=AGENT_TOOLS,
        setting_sources=["user", "project"],
        permission_mode="acceptEdits",
        cwd=str(PROACTIVE_DIR),
        max_turns=30,
    )

    full_response = []
    in_tools = False

    async for message in query(prompt=prompt_with_history, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    if in_tools:
                        # Clear "Working..." and move to new line
                        print("\r" + " " * 20 + "\r", end="", flush=True)
                        in_tools = False
                    print(block.text, end="", flush=True)
                    full_response.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    if not in_tools:
                        in_tools = True
                        print("\n   Working...", end="", flush=True)

    if in_tools:
        print("\r" + " " * 20 + "\r", end="", flush=True)

    return "\n".join(full_response)


async def single_query(prompt: str):
    """Non-interactive mode: answer a single prompt and exit (agelclaw -p)."""
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    memory.log_conversation(role="user", content=prompt, session_id=SHARED_SESSION_ID)
    response = await run_query(prompt)
    print(response)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)


def _print_banner():
    """Print Claude Code-style startup banner."""
    from agelclaw import __version__

    # Colors (ANSI)
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"

    project = str(PROACTIVE_DIR)

    # Task stats
    stats = memory.get_task_stats()
    due = memory.get_due_tasks()
    pending = stats.get("pending", 0)
    completed = stats.get("completed", 0)

    print()
    print(f"  {MAGENTA}{BOLD}AgelClaw{RESET} {DIM}v{__version__}{RESET}")
    print(f"  {DIM}Claude Agent SDK · Persistent Memory{RESET}")
    print(f"  {DIM}{project}{RESET}")
    print()

    # Status line
    parts = []
    if pending:
        parts.append(f"{YELLOW}{pending} pending{RESET}")
    if completed:
        parts.append(f"{GREEN}{completed} completed{RESET}")
    if due:
        parts.append(f"{CYAN}{len(due)} due now{RESET}")

    if parts:
        print(f"  {' · '.join(parts)}")
        print()


async def main(initial_prompt: str = None):
    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        # Enable ANSI colors on Windows
        os.system("")

    _print_banner()

    # Process initial prompt if provided (agelclaw "do something")
    if initial_prompt:
        print(f"\033[1m> \033[0m{initial_prompt}")
        memory.log_conversation(role="user", content=initial_prompt, session_id=SHARED_SESSION_ID)
        print()
        response = await run_query(initial_prompt)
        print("\n")
        memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)

    while True:
        try:
            user_input = input("\033[1m> \033[0m").strip()
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
        memory.log_conversation(role="user", content=user_input, session_id=SHARED_SESSION_ID)

        # Send to agent
        print()
        response = await run_query(user_input)
        print("\n")

        # Log agent response
        memory.log_conversation(
            role="assistant",
            content=response[:2000],
            session_id=SHARED_SESSION_ID,
        )


if __name__ == "__main__":
    asyncio.run(main())
