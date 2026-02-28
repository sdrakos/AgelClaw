"""
Claude Agent Wrapper
====================
Wraps the Claude Agent SDK query() for use through the agent router.
"""

from typing import AsyncGenerator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from agelclaw.agent_wrappers.base_agent import BaseAgent


class ClaudeAgent(BaseAgent):
    """Claude Agent SDK wrapper implementing BaseAgent interface."""

    @property
    def provider_name(self) -> str:
        return "claude"

    async def run(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> str:
        options = self._build_options(system_prompt, tools, cwd, max_turns)
        full_response = []

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_response.append(block.text)

        return "".join(full_response)

    async def run_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        max_turns: int = 30,
    ) -> AsyncGenerator[tuple[str, str], None]:
        options = self._build_options(system_prompt, tools, cwd, max_turns)

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            yield ("text", block.text)
                        elif isinstance(block, ToolUseBlock):
                            yield ("tool", block.name)
                elif isinstance(message, ResultMessage):
                    pass
        except Exception as e:
            yield ("error", str(e))

        yield ("done", "")

    def _build_options(
        self,
        system_prompt: str,
        tools: list[str] | None,
        cwd: str,
        max_turns: int,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=tools or ["Skill", "Bash", "Read", "Write", "Edit", "Glob", "Grep"],
            setting_sources=["user", "project"],
            permission_mode="bypassPermissions",
            cwd=cwd,
            max_turns=max_turns,
        )
