"""
Subagent Manager
================
Dynamic lifecycle management for subagents.
Creates, runs, tracks, and cancels subagents across providers.
Emits SSE events for UI monitoring.
"""

import asyncio
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

from agelclaw.core.agent_router import AgentRouter, Provider


@dataclass
class SubagentInfo:
    """Tracks a running or completed subagent."""
    id: str
    name: str
    provider: str
    model: str
    status: str  # "running" | "completed" | "failed" | "cancelled"
    created_at: str
    completed_at: str | None = None
    prompt: str = ""
    result: str = ""
    error: str = ""
    tokens_used: int = 0
    cost_estimate: float = 0.0
    task: asyncio.Task | None = field(default=None, repr=False)


class SubagentManager:
    """Manages dynamic subagent creation and lifecycle."""

    def __init__(self, router: AgentRouter | None = None):
        self._router = router or AgentRouter()
        self._subagents: dict[str, SubagentInfo] = {}
        self._sse_subscribers: list[asyncio.Queue] = []

    def _broadcast(self, event_type: str, data: dict) -> None:
        """Send event to all SSE subscribers."""
        payload = json.dumps({
            "type": event_type,
            "time": datetime.now().isoformat(),
            **data,
        })
        dead = []
        for i, q in enumerate(self._sse_subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(i)
        for i in reversed(dead):
            self._sse_subscribers.pop(i)

    async def create_subagent(
        self,
        name: str,
        prompt: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
        cwd: str = ".",
        provider: str | None = None,
        task_type: str = "general",
        max_turns: int = 30,
    ) -> SubagentInfo:
        """Create and start a new subagent.

        Returns SubagentInfo with the subagent's ID for tracking.
        """
        from agelclaw.agent_config import get_agent

        route = self._router.route(task_type=task_type, prefer=provider)
        agent_id = str(uuid.uuid4())[:8]

        info = SubagentInfo(
            id=agent_id,
            name=name,
            provider=route.provider.value,
            model=route.model,
            status="running",
            created_at=datetime.now().isoformat(),
            prompt=prompt[:500],
        )
        self._subagents[agent_id] = info

        self._broadcast("subagent_start", {
            "subagent_id": agent_id,
            "name": name,
            "provider": route.provider.value,
            "model": route.model,
        })

        agent = get_agent(provider=route.provider.value, model=route.model)

        async def _run():
            try:
                result = await agent.run(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    cwd=cwd,
                    max_turns=max_turns,
                )
                info.result = result
                info.status = "completed"
                info.completed_at = datetime.now().isoformat()
                self._broadcast("subagent_end", {
                    "subagent_id": agent_id,
                    "name": name,
                    "status": "completed",
                    "result_preview": result[:500],
                })
            except asyncio.CancelledError:
                info.status = "cancelled"
                info.completed_at = datetime.now().isoformat()
                self._broadcast("subagent_end", {
                    "subagent_id": agent_id,
                    "name": name,
                    "status": "cancelled",
                })
            except Exception as e:
                info.status = "failed"
                info.error = str(e)
                info.completed_at = datetime.now().isoformat()
                self._broadcast("subagent_error", {
                    "subagent_id": agent_id,
                    "name": name,
                    "error": str(e),
                })

        info.task = asyncio.create_task(_run())
        return info

    def cancel(self, agent_id: str) -> bool:
        """Cancel a running subagent."""
        info = self._subagents.get(agent_id)
        if not info or info.status != "running":
            return False
        if info.task and not info.task.done():
            info.task.cancel()
        return True

    def list_subagents(self, status: str | None = None) -> list[dict[str, Any]]:
        """List subagents, optionally filtered by status."""
        results = []
        for info in self._subagents.values():
            if status and info.status != status:
                continue
            results.append({
                "id": info.id,
                "name": info.name,
                "provider": info.provider,
                "model": info.model,
                "status": info.status,
                "created_at": info.created_at,
                "completed_at": info.completed_at,
                "result_preview": info.result[:200] if info.result else "",
                "error": info.error,
            })
        return results

    def get_subagent(self, agent_id: str) -> dict[str, Any] | None:
        """Get full details of a subagent."""
        info = self._subagents.get(agent_id)
        if not info:
            return None
        return {
            "id": info.id,
            "name": info.name,
            "provider": info.provider,
            "model": info.model,
            "status": info.status,
            "created_at": info.created_at,
            "completed_at": info.completed_at,
            "prompt": info.prompt,
            "result": info.result,
            "error": info.error,
            "tokens_used": info.tokens_used,
            "cost_estimate": info.cost_estimate,
        }

    def subscribe_sse(self) -> asyncio.Queue:
        """Get an SSE queue for subagent events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._sse_subscribers.append(q)
        return q

    def unsubscribe_sse(self, q: asyncio.Queue) -> None:
        """Remove an SSE subscriber."""
        if q in self._sse_subscribers:
            self._sse_subscribers.remove(q)
