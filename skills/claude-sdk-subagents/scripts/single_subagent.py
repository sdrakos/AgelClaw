"""
Single Subagent — Minimal Example
==================================
A main agent that delegates code review to a read-only subagent.

Usage:
    pip install claude-agent-sdk
    python single_subagent.py
"""

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


async def main():
    async for message in query(
        prompt="Use the code-reviewer agent to review the authentication module",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Task"],
            agents={
                "code-reviewer": AgentDefinition(
                    description="Expert code review specialist. Use for quality, security, and maintainability reviews.",
                    prompt="""You are a code review specialist.
When reviewing code:
- Identify security vulnerabilities
- Check for performance issues
- Suggest specific improvements
Be thorough but concise.""",
                    tools=["Read", "Grep", "Glob"],  # read-only
                    model="sonnet",
                ),
            },
        ),
    ):
        if hasattr(message, "result"):
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())
