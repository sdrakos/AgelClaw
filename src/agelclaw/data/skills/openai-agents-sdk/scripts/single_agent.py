"""
Single Agent Template
=====================
A single agent with tools and structured output.

Usage:
    pip install openai-agents
    export OPENAI_API_KEY=sk-...
    python single_agent.py
"""

import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, function_tool


# ── Tools ────────────────────────────────────────────
@function_tool
def search_knowledge(query: str) -> str:
    """Search the knowledge base for relevant information.

    Args:
        query: The search query.
    """
    # Replace with your actual search logic
    return f"Found results for: {query}"


@function_tool
def save_note(title: str, content: str) -> str:
    """Save a note for later reference.

    Args:
        title: Note title.
        content: Note content.
    """
    print(f"[Saved] {title}: {content}")
    return f"Note '{title}' saved successfully."


# ── Structured Output (optional) ─────────────────────
class TaskResult(BaseModel):
    summary: str
    next_steps: list[str]
    confidence: float


# ── Agent ─────────────────────────────────────────────
agent = Agent(
    name="Assistant",
    instructions="""You are a helpful assistant.
Use the available tools to help the user.
Be concise and actionable.""",
    model="gpt-4.1",
    tools=[search_knowledge, save_note],
    # output_type=TaskResult,  # Uncomment for structured output
)


# ── Run ───────────────────────────────────────────────
async def main():
    result = await Runner.run(agent, "Search for Python best practices and save a note with the key points.")
    print(result.final_output)
    print(f"\nTokens used: {result.context_wrapper.usage.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
