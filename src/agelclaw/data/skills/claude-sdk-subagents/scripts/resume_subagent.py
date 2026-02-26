"""
Resume Subagent — Session Persistence
=======================================
Demonstrates capturing session/agent IDs and resuming a subagent
with follow-up questions that require previous context.

Usage:
    pip install claude-agent-sdk
    python resume_subagent.py
"""

import asyncio
import json
import re
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


def extract_agent_id(text: str) -> str | None:
    """Extract agentId from Task tool result text."""
    match = re.search(r"agentId:\s*([a-f0-9-]+)", text)
    return match.group(1) if match else None


# Define agents once — reuse for both calls
AGENTS = {
    "analyzer": AgentDefinition(
        description="Codebase architecture analyzer. Use for structural analysis.",
        prompt="""You are an architecture analyst. Analyze:
- Module structure and dependencies
- Design patterns used
- Coupling and cohesion
- Potential architectural improvements""",
        tools=["Read", "Grep", "Glob"],
    ),
}

OPTIONS_BASE = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob", "Task"],
    agents=AGENTS,
)


async def main():
    agent_id = None
    session_id = None

    # ── Step 1: First invocation ──────────────────────
    print("Step 1: Initial analysis...")
    async for message in query(
        prompt="Use the analyzer agent to review the codebase architecture",
        options=OPTIONS_BASE,
    ):
        # Capture session_id from ResultMessage
        if hasattr(message, "session_id"):
            session_id = message.session_id

        # Extract agentId from content
        if hasattr(message, "content"):
            content_str = json.dumps(message.content, default=str)
            extracted = extract_agent_id(content_str)
            if extracted:
                agent_id = extracted

        if hasattr(message, "result"):
            print(f"Result: {message.result[:200]}...")

    print(f"\nCaptured: session_id={session_id}, agent_id={agent_id}")

    # ── Step 2: Resume with follow-up ─────────────────
    if agent_id and session_id:
        print("\nStep 2: Resuming with follow-up question...")
        async for message in query(
            prompt=f"Resume agent {agent_id} and list the top 3 most complex modules with refactoring suggestions",
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob", "Task"],
                resume=session_id,  # Same session!
                agents=AGENTS,      # Same agent definitions!
            ),
        ):
            if hasattr(message, "result"):
                print(f"Result: {message.result}")
    else:
        print("Could not capture session/agent IDs for resume.")


if __name__ == "__main__":
    asyncio.run(main())
