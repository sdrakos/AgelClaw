"""
Base Agent Interface
====================
Abstract base class for all AI provider agents.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseAgent(ABC):
    """Abstract agent interface that Claude and OpenAI agents implement."""

    @abstractmethod
    async def run(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> str:
        """Run the agent and return the full text response.

        Args:
            prompt: User prompt / task description.
            system_prompt: System instructions.
            tools: List of tool names to allow (e.g., ["Bash", "Read"]).
            cwd: Working directory for tool execution.
            max_turns: Maximum conversation turns.

        Returns:
            Complete text response from the agent.
        """
        ...

    @abstractmethod
    async def run_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Run the agent with streaming output.

        Yields tuples of (event_type, content):
            ("text", "some text...")
            ("tool", "Bash")
            ("error", "error message")
            ("done", "")

        Args:
            Same as run().
        """
        ...
        # Make this a generator
        yield  # type: ignore

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'claude', 'openai')."""
        ...
