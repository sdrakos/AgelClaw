"""
OpenAI Agent Wrapper
====================
Wraps the OpenAI Agents SDK for use through the agent router.
"""

from typing import AsyncGenerator

from agents import Agent, Runner  # openai-agents SDK
from agent_wrappers.openai_tools import ALL_OPENAI_TOOLS, set_cwd
from agent_wrappers.base_agent import BaseAgent


class OpenAIAgent(BaseAgent):
    """OpenAI Agents SDK wrapper implementing BaseAgent interface."""

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def run(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> str:
        set_cwd(cwd)
        agent_tools = self._select_tools(tools)

        agent = Agent(
            name="ProactiveAgent",
            instructions=system_prompt or "You are a helpful assistant.",
            model=self.model,
            tools=agent_tools,
        )

        result = await Runner.run(agent, prompt, max_turns=max_turns)
        return str(result.final_output)

    async def run_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """OpenAI Agents SDK doesn't have the same streaming model as Claude.
        We run the full query and yield the result as a single text event.
        """
        try:
            result = await self.run(prompt, system_prompt, tools, cwd, max_turns)
            yield ("text", result)
        except Exception as e:
            yield ("error", str(e))
        yield ("done", "")

    def _select_tools(self, tool_names: list[str] | None) -> list:
        """Map our tool names to OpenAI function_tool implementations."""
        if not tool_names:
            return ALL_OPENAI_TOOLS

        from agent_wrappers.openai_tools import bash, read_file, write_file, grep_search, glob_search

        name_map = {
            "Bash": bash,
            "Read": read_file,
            "Write": write_file,
            "Edit": write_file,  # Edit maps to write for OpenAI
            "Grep": grep_search,
            "Glob": glob_search,
        }

        selected = []
        for name in tool_names:
            if name in name_map:
                tool = name_map[name]
                if tool not in selected:
                    selected.append(tool)

        return selected if selected else ALL_OPENAI_TOOLS
