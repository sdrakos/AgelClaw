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
import re
import sys
import io
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
from agelclaw.agent_config import (
    get_system_prompt, build_agent_options, build_prompt_with_history,
    PROACTIVE_DIR, SHARED_SESSION_ID, get_agent, get_router,
    AGENT_TOOLS, ALLOWED_TOOLS,
)
from agelclaw.core.config import load_config, save_config, save_env_file
from agelclaw.core.agent_router import Provider
from agelclaw.memory import Memory

# ── Config ───────────────────────────────────────────────────────────
from agelclaw.project import get_react_dist_dir, get_project_dir
REACT_BUILD_DIR = get_react_dist_dir()
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


# ── Chat-based task control (natural language stop/update) ───────────

_STOP_PATTERNS = [
    re.compile(r"(?:σταμ[αά]τ[αη]|σταμάτησε|ακύρωσε|ακυρωσε|cancel|stop|kill|abort)\s+(?:(?:το\s+)?(?:task|#)\s*(\d+)|(\d+))", re.IGNORECASE),
    re.compile(r"(?:task|#)\s*(\d+)\s+(?:σταμ[αά]τ[αη]|cancel|stop|kill|abort)", re.IGNORECASE),
]

_UPDATE_PATTERNS = [
    re.compile(r"(?:άλλαξε|αλλαξε|update|change)\s+(?:(?:το\s+)?(?:task|#)\s*(\d+)|(\d+))\s+(.+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:task|#)\s*(\d+)\s+(?:άλλαξε|αλλαξε|update|change)\s+(.+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:στο\s+)?(?:task|#)\s*(\d+)\s*[,:]\s+(.+)", re.IGNORECASE | re.DOTALL),
]


def _detect_stop_intent(text: str) -> int | None:
    for pat in _STOP_PATTERNS:
        m = pat.search(text)
        if m:
            for g in m.groups():
                if g and g.isdigit():
                    return int(g)
    return None


def _detect_update_intent(text: str) -> tuple[int, str] | None:
    for pat in _UPDATE_PATTERNS:
        m = pat.search(text)
        if m:
            groups = m.groups()
            task_id = None
            msg = None
            for g in groups:
                if g is None:
                    continue
                if g.strip().isdigit() and task_id is None:
                    task_id = int(g.strip())
                elif task_id is not None:
                    msg = g.strip()
                    break
            if task_id and msg:
                return (task_id, msg)
    return None


async def _daemon_request(method: str, path: str, json_data: dict = None) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"http://localhost:{DAEMON_PORT}{path}"
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=json_data)
            return {"status_code": resp.status_code, "data": resp.json()}
    except Exception:
        return None


def _get_uploads_dir() -> Path:
    d = get_project_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── API Endpoints ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/stats")
async def stats():
    return memory.get_task_stats()


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """Delete a task by ID."""
    if memory.delete_task(task_id):
        return {"message": f"Task #{task_id} deleted successfully"}
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Task not found")


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


# ── Settings API ─────────────────────────────────────────────────────
def _mask_key(key: str) -> str:
    """Mask a secret key for display (show first 4 and last 4 chars)."""
    if not key or len(key) < 8:
        return ""
    return key[:4] + "***" + key[-4:]


@app.get("/api/settings")
async def get_settings():
    """Return config with masked secrets."""
    cfg = load_config(force_reload=True)
    return {
        "anthropic_api_key": _mask_key(cfg.get("anthropic_api_key", "")),
        "openai_api_key": _mask_key(cfg.get("openai_api_key", "")),
        "default_provider": cfg.get("default_provider", "claude"),
        "telegram_bot_token": _mask_key(cfg.get("telegram_bot_token", "")),
        "telegram_allowed_users": cfg.get("telegram_allowed_users", ""),
        "outlook_client_id": _mask_key(cfg.get("outlook_client_id", "")),
        "outlook_client_secret": _mask_key(cfg.get("outlook_client_secret", "")),
        "outlook_tenant_id": cfg.get("outlook_tenant_id", ""),
        "outlook_user_email": cfg.get("outlook_user_email", ""),
        "api_port": cfg.get("api_port", 8000),
        "daemon_port": cfg.get("daemon_port", 8420),
        "cost_limit_daily": cfg.get("cost_limit_daily", 10.0),
        "max_concurrent_tasks": cfg.get("max_concurrent_tasks", 3),
        "check_interval": cfg.get("check_interval", 300),
        # Meta flags
        "is_configured": bool(cfg.get("anthropic_api_key") or cfg.get("openai_api_key")),
        "has_telegram": bool(cfg.get("telegram_bot_token")),
        "has_outlook": bool(cfg.get("outlook_client_id")),
    }


@app.post("/api/settings")
async def post_settings(data: dict):
    """Save config. Skips masked values (containing '***')."""
    cfg = load_config(force_reload=True)

    for key, value in data.items():
        # Skip meta flags and masked values
        if key.startswith("is_") or key.startswith("has_"):
            continue
        if isinstance(value, str) and "***" in value:
            continue
        cfg[key] = value

    save_config(cfg)
    save_env_file(cfg)
    return {"status": "saved"}


@app.get("/api/services/status")
async def services_status():
    """Check which services are currently running via port check."""
    import socket

    cfg = load_config()

    def _port_open(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    return {
        "api_server": True,  # We're responding, so it's running
        "daemon": _port_open(cfg.get("daemon_port", 8420)),
        "telegram": False,  # TODO: check telegram bot process
    }


@app.post("/api/services/{service}/{action}")
async def control_service(service: str, action: str):
    """Start/stop/restart a service. service: daemon|telegram|all. action: start|stop|restart."""
    import subprocess

    cfg = load_config()
    results = {}

    services_to_act = [service] if service != "all" else ["daemon", "telegram"]

    for svc in services_to_act:
        try:
            if action in ("stop", "restart"):
                # Try to kill existing process by finding the port
                if svc == "daemon":
                    port = cfg.get("daemon_port", 8420)
                    if sys.platform == "win32":
                        subprocess.run(
                            f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /F /PID %a',
                            shell=True, capture_output=True,
                        )
                    else:
                        subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
                results[svc] = "stopped"

            if action in ("start", "restart"):
                script = {
                    "daemon": "daemon_v2.py",
                    "telegram": "telegram_bot.py",
                }.get(svc)
                if script:
                    script_path = PROACTIVE_DIR / script
                    if script_path.exists():
                        python = sys.executable
                        subprocess.Popen(
                            [python, str(script_path)],
                            cwd=str(PROACTIVE_DIR),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                        )
                        results[svc] = "started"
                    else:
                        results[svc] = f"script not found: {script}"
                else:
                    results[svc] = f"unknown service: {svc}"
        except Exception as e:
            results[svc] = f"error: {e}"

    return {"results": results}


@app.get("/api/skills")
async def skills():
    """Dynamically scan .Claude/Skills/ and return installed skills."""
    skills_dir = get_skills_dir()
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
    """Stream agent response via SSE. Supports provider selection.

    Also intercepts stop/update intents for running daemon tasks.
    """
    # ── Check for stop intent
    stop_id = _detect_stop_intent(req.message)
    if stop_id is not None:
        result = await _daemon_request("POST", f"/tasks/{stop_id}/cancel")
        async def stop_stream():
            if result is None:
                msg = f"Cannot reach daemon to cancel task #{stop_id}."
            elif result["status_code"] == 200:
                msg = f"Task #{stop_id} cancelled."
            else:
                msg = f"Error: {result['data'].get('detail', 'Unknown error')}"
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stop_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── Check for update intent
    update_intent = _detect_update_intent(req.message)
    if update_intent is not None:
        task_id, update_msg = update_intent
        result = await _daemon_request("POST", f"/tasks/{task_id}/update", {"message": update_msg})
        async def update_stream():
            if result is None:
                msg = f"Cannot reach daemon to update task #{task_id}."
            elif result["status_code"] == 200:
                msg = f"Task #{task_id}: {result['data'].get('message', 'updated')}"
            else:
                msg = f"Error: {result['data'].get('detail', 'Unknown error')}"
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(update_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── Normal agent query
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
                    tools=AGENT_TOOLS,
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


# ── File Upload Endpoint ─────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    message: str = Form(""),
    provider: str | None = Form(None),
):
    """Upload a file and process it through the agent.

    The file is saved to uploads/ and a prompt is built telling the agent
    to read/analyze the file. Response is streamed via SSE.
    """
    # Save the file
    uploads = _get_uploads_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-.]', '_', file.filename or "unknown")
    dest = uploads / f"{timestamp}_{safe_name}"

    content = await file.read()
    dest.write_bytes(content)
    file_size = len(content)

    # Build prompt with file info
    user_text = (
        f"User uploaded a file: {file.filename} ({file_size} bytes, type: {file.content_type})\n"
        f"Saved at: {dest}\n"
    )
    if message:
        user_text += f"User message: {message}\n"
    user_text += "Read the file and respond to the user about its contents."

    prompt_text = build_prompt_with_history(user_text, memory)

    # Route to provider
    router = get_router()
    route = router.route(task_type="chat", prefer=provider)

    async def generate():
        full_response = []

        try:
            if route.provider == Provider.OPENAI:
                yield f"data: {json.dumps({'type': 'provider', 'provider': 'openai', 'model': route.model})}\n\n"
                agent = get_agent(provider="openai", model=route.model)
                result = await agent.run(
                    prompt=prompt_text,
                    system_prompt=get_system_prompt(),
                    tools=AGENT_TOOLS,
                    cwd=str(PROACTIVE_DIR),
                    max_turns=30,
                )
                full_response.append(result)
                yield f"data: {json.dumps({'type': 'text', 'content': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'provider', 'provider': 'claude', 'model': route.model})}\n\n"
                options = build_agent_options(max_turns=30)

                async for msg in query(prompt=prompt_text, options=options):
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                full_response.append(block.text)
                                yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"
                            elif isinstance(block, ToolUseBlock):
                                yield f"data: {json.dumps({'type': 'tool', 'name': block.name})}\n\n"

            memory.log_conversation(
                role="user",
                content=f"[File: {file.filename}] {message}"[:2000],
                session_id="shared_chat",
            )
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Subagent Endpoints ───────────────────────────────────────────────
from agelclaw.core.subagent_manager import SubagentManager

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


# ── Per-Subagent Task Endpoints ───────────────────────────────────────


class SubagentTaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: int = 5
    category: str = "general"
    due_at: str | None = None
    recurring_cron: str | None = None
    context: dict | None = None


@app.get("/api/subagents/{name}/tasks")
async def get_subagent_tasks(name: str, status: str | None = None, limit: int = 20):
    """List tasks assigned to a specific subagent."""
    tasks = memory.get_subagent_tasks(name, status=status, limit=limit)
    stats = memory.get_subagent_stats(name)
    return {"subagent": name, "tasks": tasks, "stats": stats}


@app.post("/api/subagents/{name}/tasks")
async def create_subagent_task(name: str, req: SubagentTaskRequest):
    """Create a new task assigned to a specific subagent."""
    task_id = memory.add_task(
        title=req.title,
        description=req.description,
        priority=req.priority,
        category=req.category,
        due_at=req.due_at,
        recurring_cron=req.recurring_cron,
        context=req.context or {},
        assigned_to=name,
    )
    return {"task_id": task_id, "assigned_to": name, "status": "pending", "message": f"Task #{task_id} created for subagent '{name}'"}


@app.post("/api/tasks/{task_id}/assign/{subagent_name}")
async def assign_task_to_subagent(task_id: int, subagent_name: str):
    """Assign an existing task to a subagent."""
    if memory.assign_task(task_id, subagent_name):
        return {"task_id": task_id, "assigned_to": subagent_name, "message": f"Task #{task_id} assigned to '{subagent_name}'"}
    raise HTTPException(status_code=404, detail=f"Task #{task_id} not found")


# ── Proxy daemon SSE for production (no Vite proxy available) ────────
import httpx

@app.get("/daemon/{path:path}")
async def proxy_daemon(path: str):
    """Proxy requests to daemon API (for production, replaces Vite proxy)."""
    daemon_base = f"http://localhost:{DAEMON_PORT}"

    if path == "events":
        # SSE proxy - stream through
        async def stream_sse():
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream("GET", f"{daemon_base}/events", timeout=None) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Daemon not running — send an offline notice and close
                yield f"data: {json.dumps({'type': 'daemon_offline', 'message': 'Daemon is not running on port ' + str(DAEMON_PORT)})}\n\n"
        return StreamingResponse(
            stream_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        # Regular JSON proxy
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{daemon_base}/{path}", timeout=10)
                return resp.json()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise HTTPException(status_code=503, detail=f"Daemon not running on port {DAEMON_PORT}")


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
