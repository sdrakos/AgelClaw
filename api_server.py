"""
API Server
==========
FastAPI backend that bridges the React chat UI with the Claude Agent SDK.
Streams agent responses via SSE.
In production, also serves the React build (static files).

Usage:
    python api_server.py                      # Dev mode (React served by Vite)
    python api_server.py --production         # Prod mode (serves React build too)
    pm2 start ecosystem.config.js             # Via PM2
"""

import asyncio
import json
import sys
import io
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from agent_config import (
    get_system_prompt, build_agent_options, build_prompt_with_history,
    PROACTIVE_DIR, SHARED_SESSION_ID, get_agent, get_router,
    ALLOWED_TOOLS,
)
from core.config import load_config
from core.agent_router import Provider
from memory import Memory

# ── Config ───────────────────────────────────────────────────────────
REACT_BUILD_DIR = PROACTIVE_DIR / "react-claude-chat" / "dist"
_cfg = load_config()
API_PORT = _cfg.get("api_port", 8000)
DAEMON_PORT = _cfg.get("daemon_port", 8420)

memory = Memory()

# ── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(title="Claude Agent Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    provider: str | None = None  # "claude" | "openai" | "auto" | None (uses default)


# ── API Endpoints ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/stats")
async def stats():
    return memory.get_task_stats()


@app.get("/api/daemon-url")
async def daemon_url():
    """Tell the frontend where the daemon SSE is."""
    return {"url": f"http://localhost:{DAEMON_PORT}"}


@app.get("/api/config")
async def get_config():
    """Public config info (no secrets)."""
    cfg = load_config()
    router = get_router()
    return {
        "default_provider": cfg.get("default_provider", "claude"),
        "available_providers": [p.value for p in router.available_providers],
        "api_port": cfg.get("api_port"),
        "daemon_port": cfg.get("daemon_port"),
        "cost_limit_daily": cfg.get("cost_limit_daily"),
        "has_claude_key": bool(cfg.get("anthropic_api_key")),
        "has_openai_key": bool(cfg.get("openai_api_key")),
    }


@app.get("/api/skills")
async def skills():
    """Dynamically scan .Claude/Skills/ and return installed skills."""
    skills_dir = PROACTIVE_DIR.parent / ".Claude" / "Skills"
    result = []
    if skills_dir.exists():
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            name = entry.name
            description = ""
            if skill_md.exists():
                try:
                    text = skill_md.read_text(encoding="utf-8", errors="replace")
                    # Parse YAML frontmatter
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            for line in parts[1].strip().splitlines():
                                if line.startswith("name:"):
                                    name = line.split(":", 1)[1].strip()
                                elif line.startswith("description:"):
                                    desc = line.split(":", 1)[1].strip()
                                    if desc and desc != ">-":
                                        description = desc
                            # Handle multi-line description (YAML >- style)
                            if not description:
                                in_desc = False
                                for line in parts[1].strip().splitlines():
                                    if line.startswith("description:"):
                                        in_desc = True
                                        continue
                                    if in_desc:
                                        if line and not line[0].isalpha() or line.startswith("  "):
                                            description = line.strip()
                                            break
                except Exception:
                    pass
            if not description:
                description = f"Agent skill: {name}"
            result.append({
                "status": "ready",
                "icon": "🧩",
                "name": name,
                "description": description,
                "source": "project",
            })
    return result


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Stream agent response via SSE. Supports provider selection."""

    # Build prompt with conversation context (shared across web + telegram)
    prompt_text = build_prompt_with_history(req.message, memory)

    # Route to the right provider
    router = get_router()
    route = router.route(task_type="chat", prefer=req.provider)

    async def generate():
        full_response = []

        try:
            if route.provider == Provider.OPENAI:
                # OpenAI: run full query, return as single SSE event
                yield f"data: {json.dumps({'type': 'provider', 'provider': 'openai', 'model': route.model})}\n\n"
                agent = get_agent(provider="openai", model=route.model)
                result = await agent.run(
                    prompt=prompt_text,
                    system_prompt=get_system_prompt(),
                    tools=ALLOWED_TOOLS,
                    cwd=str(PROACTIVE_DIR),
                    max_turns=30,
                )
                full_response.append(result)
                yield f"data: {json.dumps({'type': 'text', 'content': result})}\n\n"
            else:
                # Claude: stream response via SSE
                yield f"data: {json.dumps({'type': 'provider', 'provider': 'claude', 'model': route.model})}\n\n"
                options = build_agent_options(max_turns=30)

                async for message in query(prompt=prompt_text, options=options):
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_response.append(block.text)
                                yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"
                            elif isinstance(block, ToolUseBlock):
                                yield f"data: {json.dumps({'type': 'tool', 'name': block.name})}\n\n"
                    elif isinstance(message, ResultMessage):
                        pass

            memory.log_conversation(role="user", content=req.message[:2000], session_id="shared_chat")
            memory.log_conversation(
                role="assistant",
                content="".join(full_response)[:2000],
                session_id="shared_chat",
            )

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Subagent Endpoints ───────────────────────────────────────────────
from core.subagent_manager import SubagentManager

_subagent_mgr = SubagentManager()


class SubagentRequest(BaseModel):
    name: str
    prompt: str
    system_prompt: str = ""
    tools: list[str] | None = None
    provider: str | None = None
    task_type: str = "general"
    max_turns: int = 30


@app.get("/api/subagents")
async def list_subagents(status: str | None = None):
    """List active and completed subagents."""
    return _subagent_mgr.list_subagents(status=status)


@app.post("/api/subagents")
async def create_subagent(req: SubagentRequest):
    """Create and run a new subagent."""
    info = await _subagent_mgr.create_subagent(
        name=req.name,
        prompt=req.prompt,
        system_prompt=req.system_prompt,
        tools=req.tools,
        cwd=str(PROACTIVE_DIR),
        provider=req.provider,
        task_type=req.task_type,
        max_turns=req.max_turns,
    )
    return {"id": info.id, "status": info.status, "provider": info.provider, "model": info.model}


@app.get("/api/subagents/{agent_id}")
async def get_subagent(agent_id: str):
    """Get details of a specific subagent."""
    result = _subagent_mgr.get_subagent(agent_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Subagent not found")
    return result


@app.delete("/api/subagents/{agent_id}")
async def cancel_subagent(agent_id: str):
    """Cancel a running subagent."""
    if _subagent_mgr.cancel(agent_id):
        return {"message": f"Subagent {agent_id} cancelled"}
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="Cannot cancel (not running or not found)")


@app.get("/api/subagents/events")
async def subagent_events():
    """SSE stream for subagent lifecycle events."""
    q = _subagent_mgr.subscribe_sse()

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _subagent_mgr.unsubscribe_sse(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Proxy daemon SSE for production (no Vite proxy available) ────────
import httpx

@app.get("/daemon/{path:path}")
async def proxy_daemon(path: str):
    """Proxy requests to daemon API (for production, replaces Vite proxy)."""
    daemon_base = f"http://localhost:{DAEMON_PORT}"

    if path == "events":
        # SSE proxy - stream through
        async def stream_sse():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", f"{daemon_base}/events", timeout=None) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        return StreamingResponse(
            stream_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        # Regular JSON proxy
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{daemon_base}/{path}", timeout=10)
            return resp.json()


# ── Serve React build (production) ──────────────────────────────────
# MUST be last — catches all non-API routes and serves index.html
if REACT_BUILD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(REACT_BUILD_DIR), html=True), name="static")


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    import uvicorn

    mode = "PRODUCTION" if REACT_BUILD_DIR.exists() else "DEV"
    print(f"Starting API server on http://localhost:{API_PORT} [{mode}]")
    if REACT_BUILD_DIR.exists():
        print(f"  Serving React build from {REACT_BUILD_DIR}")
    else:
        print(f"  React build not found — run: cd react-claude-chat && npm run build")
        print(f"  For dev: cd react-claude-chat && npm run dev (Vite on :3000)")
    print(f"  Daemon proxy: /daemon/* -> localhost:{DAEMON_PORT}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
