"""
Telegram Bot for Proactive Agent
=================================
Receives Telegram messages, runs them through the same Claude Agent SDK
query() flow as api_server.py, and sends responses back.

Usage:
    python telegram_bot.py
    pm2 start ecosystem.config.js   (includes telegram-bot)

Requires:
    pip install python-telegram-bot python-dotenv
    Set TELEGRAM_BOT_TOKEN in .env
"""

import asyncio
import logging
import os
import re
import sys
import io
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode, ChatAction

from claude_agent_sdk import (
    query,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from agelclaw.agent_config import (
    get_system_prompt, get_system_prompt_for_channel, build_agent_options,
    build_prompt_with_history,
    SHARED_SESSION_ID, get_agent, get_router, AGENT_TOOLS, PROACTIVE_DIR,
)
from agelclaw.core.config import load_config
from agelclaw.core.agent_router import Provider
from agelclaw.memory import Memory

# ── Setup ────────────────────────────────────────────────────────────
from agelclaw.project import get_env_path, get_project_dir
load_dotenv(get_env_path())

logging.basicConfig(
    format="%(asctime)s [telegram-bot] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_cfg = load_config()
TELEGRAM_BOT_TOKEN = _cfg.get("telegram_bot_token", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS = _cfg.get("telegram_allowed_users", "") or os.getenv("TELEGRAM_ALLOWED_USERS", "")

memory = Memory()

# ── Helpers ──────────────────────────────────────────────────────────

def get_allowed_user_ids() -> set[int]:
    """Parse allowed user IDs from env. Empty set = allow all."""
    if not TELEGRAM_ALLOWED_USERS.strip():
        return set()
    try:
        return {int(uid.strip()) for uid in TELEGRAM_ALLOWED_USERS.split(",") if uid.strip()}
    except ValueError:
        logger.warning("Invalid TELEGRAM_ALLOWED_USERS format, allowing all users")
        return set()


ALLOWED_IDS = get_allowed_user_ids()


def is_authorized(user_id: int) -> bool:
    """Check if user is allowed. If no whitelist configured, allow all."""
    if not ALLOWED_IDS:
        return True
    return user_id in ALLOWED_IDS


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", text)


def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Try to split at a newline
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            # Try splitting at a space
            split_pos = text.rfind(" ", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            # Hard split
            split_pos = max_length

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks


TOOL_PROGRESS_LABELS = {
    "Bash": "Εκτελώ εντολή...",
    "Read": "Διαβάζω αρχείο...",
    "Write": "Γράφω αρχείο...",
    "Edit": "Επεξεργάζομαι αρχείο...",
    "Grep": "Αναζητώ στον κώδικα...",
    "Glob": "Ψάχνω αρχεία...",
    "WebSearch": "Αναζητώ στο web...",
    "WebFetch": "Φορτώνω σελίδα...",
    "Skill": "Χρησιμοποιώ skill...",
    "Task": "Εκτελώ υπο-εργασία...",
}


# ── Chat-based task control (natural language stop/update) ────────────

# Patterns for detecting stop intent in Greek & English
_STOP_PATTERNS = [
    re.compile(r"(?:σταμ[αά]τ[αη]|σταμάτησε|ακύρωσε|ακυρωσε|cancel|stop|kill|abort)\s+(?:(?:το\s+)?(?:task|#)\s*(\d+)|(\d+))", re.IGNORECASE),
    re.compile(r"(?:task|#)\s*(\d+)\s+(?:σταμ[αά]τ[αη]|cancel|stop|kill|abort)", re.IGNORECASE),
]

# Patterns for detecting update intent
_UPDATE_PATTERNS = [
    re.compile(r"(?:άλλαξε|αλλαξε|update|change)\s+(?:(?:το\s+)?(?:task|#)\s*(\d+)|(\d+))\s+(.+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:task|#)\s*(\d+)\s+(?:άλλαξε|αλλαξε|update|change)\s+(.+)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:στο\s+)?(?:task|#)\s*(\d+)\s*[,:]\s+(.+)", re.IGNORECASE | re.DOTALL),
]


def _detect_stop_intent(text: str) -> int | None:
    """Detect if user wants to stop a task. Returns task_id or None."""
    for pat in _STOP_PATTERNS:
        m = pat.search(text)
        if m:
            # Get the first non-None group (different patterns capture ID in different groups)
            for g in m.groups():
                if g and g.isdigit():
                    return int(g)
    return None


def _detect_update_intent(text: str) -> tuple[int, str] | None:
    """Detect if user wants to update a task. Returns (task_id, message) or None."""
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
    """Make an HTTP request to the daemon. Returns response dict or None on error."""
    try:
        import httpx
        cfg = load_config()
        port = cfg.get("daemon_port", 8420)
        async with httpx.AsyncClient(timeout=10) as client:
            if method == "GET":
                resp = await client.get(f"http://localhost:{port}{path}")
            else:
                resp = await client.post(f"http://localhost:{port}{path}", json=json_data)
            return {"status_code": resp.status_code, "data": resp.json()}
    except Exception as e:
        logger.error(f"Daemon request failed: {method} {path}: {e}")
        return None


# ── File upload directory ────────────────────────────────────────────

def _get_uploads_dir() -> Path:
    """Get (and create) the uploads directory for Telegram file uploads."""
    d = get_project_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def run_agent_query_with_progress(prompt: str, chat, channel_type: str = "private") -> str:
    """Run the agent query with live progress updates to Telegram.
    Routes to Claude or OpenAI based on config."""
    router = get_router()
    route = router.route(task_type="chat")

    if route.provider == Provider.OPENAI:
        return await _run_openai_query(prompt, chat, route.model, channel_type)
    else:
        return await _run_claude_query(prompt, chat, channel_type)


async def _run_openai_query(prompt: str, chat, model: str, channel_type: str = "private") -> str:
    """Run query via OpenAI Agents SDK (no streaming progress)."""
    progress_msg = None
    try:
        await chat.send_action(ChatAction.TYPING)
        progress_msg = await chat.send_message(f"Processing with OpenAI ({model})...")

        agent = get_agent(provider="openai", model=model)
        result = await agent.run(
            prompt=prompt,
            system_prompt=get_system_prompt_for_channel(channel_type),
            tools=AGENT_TOOLS,
            cwd=str(PROACTIVE_DIR),
            max_turns=30,
        )

        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception:
                pass

        return result if result else "No response from agent."

    except Exception as e:
        logger.error(f"OpenAI agent query error: {e}")
        if progress_msg:
            try:
                await progress_msg.edit_text("Error processing request")
            except Exception:
                pass
        return f"Error: {e}"


async def _run_claude_query(prompt: str, chat, channel_type: str = "private") -> str:
    """Run query via Claude Agent SDK with streaming progress."""
    options = build_agent_options(max_turns=30, channel_type=channel_type)
    full_response = []
    progress_msg = None
    last_status = ""
    tool_count = 0

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_response.append(block.text)
                        # Log agent text to terminal (truncated)
                        preview = block.text.strip().replace("\n", " ")[:120]
                        if preview:
                            logger.info(f"[Agent] {preview}")
                    elif isinstance(block, ToolUseBlock):
                        tool_count += 1
                        tool_name = block.name
                        label = TOOL_PROGRESS_LABELS.get(tool_name, f"Working ({tool_name})...")

                        detail = ""
                        if tool_name == "Bash" and isinstance(block.input, dict):
                            cmd = block.input.get("command", "")
                            if cmd:
                                if "send" in cmd.lower() or "email" in cmd.lower() or "mail" in cmd.lower():
                                    label = "Sending email..."
                                elif "search" in cmd.lower() or "curl" in cmd.lower():
                                    label = "Searching..."
                                elif "pip" in cmd.lower() or "npm" in cmd.lower():
                                    label = "Installing dependencies..."
                                elif "python" in cmd.lower() and "mem_cli" in cmd.lower():
                                    label = "Checking memory..."
                            # Log the actual command
                            logger.info(f"[Tool #{tool_count}] Bash: {cmd[:150]}")
                        elif tool_name == "WebSearch" and isinstance(block.input, dict):
                            q = block.input.get("query", "")
                            if q:
                                detail = f' "{q[:40]}"'
                            logger.info(f"[Tool #{tool_count}] WebSearch: {q[:100]}")
                        elif tool_name == "Read" and isinstance(block.input, dict):
                            logger.info(f"[Tool #{tool_count}] Read: {block.input.get('file_path', '')[:100]}")
                        elif tool_name == "Write" and isinstance(block.input, dict):
                            logger.info(f"[Tool #{tool_count}] Write: {block.input.get('file_path', '')[:100]}")
                        elif tool_name == "WebFetch" and isinstance(block.input, dict):
                            logger.info(f"[Tool #{tool_count}] WebFetch: {block.input.get('url', '')[:100]}")
                        elif tool_name == "Grep" and isinstance(block.input, dict):
                            logger.info(f"[Tool #{tool_count}] Grep: {block.input.get('pattern', '')[:60]} in {block.input.get('path', '')[:60]}")
                        elif tool_name == "Glob" and isinstance(block.input, dict):
                            logger.info(f"[Tool #{tool_count}] Glob: {block.input.get('pattern', '')[:80]}")
                        else:
                            logger.info(f"[Tool #{tool_count}] {tool_name}")

                        status_text = f"{label}{detail}"

                        if status_text == last_status:
                            continue
                        last_status = status_text

                        try:
                            await chat.send_action(ChatAction.TYPING)

                            if progress_msg is None:
                                progress_msg = await chat.send_message(
                                    f"Working: {status_text}"
                                )
                            else:
                                await progress_msg.edit_text(
                                    f"Working: {status_text} (step {tool_count})"
                                )
                        except Exception as e:
                            logger.debug(f"Progress update failed: {e}")

            elif isinstance(message, ResultMessage):
                pass

    except Exception as e:
        logger.error(f"Agent query error: {e}")
        if progress_msg:
            try:
                await progress_msg.edit_text("Error processing request")
            except Exception:
                pass
        return f"Error: {e}"

    if progress_msg:
        try:
            await progress_msg.delete()
        except Exception:
            try:
                await progress_msg.edit_text("Done")
            except Exception:
                pass

    return "".join(full_response) if full_response else "No response from agent."


# ── Command Handlers ─────────────────────────────────────────────────

async def cmd_start(update: Update, context) -> None:
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(
        "Hello! I'm your proactive AI assistant.\n\n"
        "Send me any message and I'll process it through the agent.\n\n"
        "Commands:\n"
        "/status - View task statistics\n"
        "/skills - List installed skills\n"
        "/tasks - View pending tasks\n"
        "/running - Running tasks now\n"
        "/stop <id> - Stop a running task\n"
        "/update <id> <msg> - Update a running task"
    )


async def cmd_status(update: Update, context) -> None:
    """Handle /status command."""
    if not is_authorized(update.effective_user.id):
        return

    stats = memory.get_task_stats()
    text = (
        "Task Statistics:\n"
        f"  Pending: {stats.get('pending', 0)}\n"
        f"  In Progress: {stats.get('in_progress', 0)}\n"
        f"  Completed: {stats.get('completed', 0)}\n"
        f"  Failed: {stats.get('failed', 0)}\n"
        f"  Total: {stats.get('total', 0)}"
    )
    await update.message.reply_text(text)


async def cmd_skills(update: Update, context) -> None:
    """Handle /skills command."""
    if not is_authorized(update.effective_user.id):
        return

    skills = memory.get_all_skills()
    if not skills:
        await update.message.reply_text("No skills installed yet.")
        return

    lines = ["Installed Skills:"]
    for s in skills:
        lines.append(f"  - {s['name']} (used {s['use_count']}x)")
    await update.message.reply_text("\n".join(lines))


async def cmd_tasks(update: Update, context) -> None:
    """Handle /tasks command."""
    if not is_authorized(update.effective_user.id):
        return

    pending = memory.get_pending_tasks(limit=10)
    if not pending:
        await update.message.reply_text("No pending tasks.")
        return

    lines = ["Pending Tasks:"]
    for t in pending:
        lines.append(f"  #{t['id']} [{t['priority']}] {t['title']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_running(update: Update, context) -> None:
    """Handle /running command — show tasks currently executing."""
    if not is_authorized(update.effective_user.id):
        return

    try:
        import httpx
        cfg = load_config()
        port = cfg.get("daemon_port", 8420)
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"http://localhost:{port}/running")
            running = resp.json()
    except Exception as e:
        await update.message.reply_text(f"Cannot reach daemon: {e}")
        return

    if not running:
        await update.message.reply_text("No tasks running right now.")
        return

    lines = ["Running tasks:"]
    for tid, info in running.items():
        sa = info.get("subagent", "")
        sa_label = f" [{sa}]" if sa else ""
        lines.append(f"  #{tid}{sa_label} — {info.get('title', '?')}")

    lines.append("\nUse /stop <id> to cancel")
    lines.append("Use /update <id> <message> to send update")
    await update.message.reply_text("\n".join(lines))


async def cmd_stop(update: Update, context) -> None:
    """Handle /stop <task_id> — cancel a running task."""
    if not is_authorized(update.effective_user.id):
        return

    args = context.args
    if not args:
        # Show running tasks list instead
        await cmd_running(update, context)
        return

    try:
        task_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Usage: /stop <task_id>")
        return

    try:
        import httpx
        cfg = load_config()
        port = cfg.get("daemon_port", 8420)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"http://localhost:{port}/tasks/{task_id}/cancel")
            if resp.status_code == 200:
                await update.message.reply_text(f"Task #{task_id} cancelled.")
            else:
                data = resp.json()
                await update.message.reply_text(f"Error: {data.get('detail', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Failed to cancel: {e}")


async def cmd_update_task(update: Update, context) -> None:
    """Handle /update <task_id> <message> — update a running task."""
    if not is_authorized(update.effective_user.id):
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Usage: /update <task_id> <message>")
        return

    try:
        task_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Usage: /update <task_id> <message>")
        return

    message_text = " ".join(args[1:])

    try:
        import httpx
        cfg = load_config()
        port = cfg.get("daemon_port", 8420)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"http://localhost:{port}/tasks/{task_id}/update",
                json={"message": message_text},
            )
            data = resp.json()
            if resp.status_code == 200:
                await update.message.reply_text(f"Task #{task_id}: {data.get('message', 'updated')}")
            else:
                await update.message.reply_text(f"Error: {data.get('detail', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")


# ── Message Handler ──────────────────────────────────────────────────

async def handle_message(update: Update, context) -> None:
    """Process any text message through the agent.

    Intercepts stop/update intents for running tasks before delegating to the agent.
    """
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    if not user_text:
        return

    user_name = update.effective_user.first_name or "User"
    logger.info(f"Message from {user_name} ({update.effective_user.id}): {user_text[:100]}")

    # Determine channel type for context isolation
    chat_type = update.message.chat.type  # "private", "group", "supergroup", "channel"
    channel_type = "group" if chat_type in ("group", "supergroup") else "private"
    chat_id = str(update.message.chat.id)

    # ── Check for stop intent (e.g. "σταμάτα το task 5", "cancel 12")
    stop_id = _detect_stop_intent(user_text)
    if stop_id is not None:
        result = await _daemon_request("POST", f"/tasks/{stop_id}/cancel")
        if result is None:
            await update.message.reply_text(f"Cannot reach daemon to cancel task #{stop_id}.")
        elif result["status_code"] == 200:
            await update.message.reply_text(f"Task #{stop_id} cancelled.")
        else:
            detail = result["data"].get("detail", "Unknown error")
            await update.message.reply_text(f"Error: {detail}")
        return

    # ── Check for update intent (e.g. "άλλαξε το task 5 να γράψει σε markdown")
    update_intent = _detect_update_intent(user_text)
    if update_intent is not None:
        task_id, msg = update_intent
        result = await _daemon_request("POST", f"/tasks/{task_id}/update", {"message": msg})
        if result is None:
            await update.message.reply_text(f"Cannot reach daemon to update task #{task_id}.")
        elif result["status_code"] == 200:
            action = result["data"].get("message", "updated")
            await update.message.reply_text(f"Task #{task_id}: {action}")
        else:
            detail = result["data"].get("detail", "Unknown error")
            await update.message.reply_text(f"Error: {detail}")
        return

    # ── Normal agent query
    await update.message.chat.send_action(ChatAction.TYPING)
    import time as _time
    _query_start = _time.time()
    logger.info(f"[Query start] {channel_type} | {user_text[:80]}")

    # Build prompt with conversation history from SQLite (shared across all channels)
    # In group mode: restricted context (no profile, no private conversations)
    prompt_with_context = build_prompt_with_history(user_text, memory, channel_type=channel_type)

    # Run the agent query with live progress updates
    response = await run_agent_query_with_progress(prompt_with_context, update.message.chat, channel_type=channel_type)

    _elapsed = _time.time() - _query_start
    resp_preview = response.strip().replace("\n", " ")[:150] if response else "(empty)"
    logger.info(f"[Query done] {_elapsed:.1f}s | Response: {resp_preview}")

    # Log to memory (log original user text, not the context-enriched prompt)
    # Group messages go to "group_chat" session, private to "shared_chat"
    session_id = "group_chat" if channel_type == "group" else SHARED_SESSION_ID
    memory.log_conversation(role="user", content=user_text[:2000], session_id=session_id,
                            channel_type=channel_type, chat_id=chat_id)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=session_id,
                            channel_type=channel_type, chat_id=chat_id)

    # Send response (split if too long)
    chunks = split_message(response)
    logger.info(f"[Sending] {len(chunks)} chunk(s), {len(response)} chars total")
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Fallback: send without any formatting
            await update.message.reply_text(chunk[:4096])


# ── File Upload Handlers ──────────────────────────────────────────────

async def _download_telegram_file(file_obj, filename: str) -> Path:
    """Download a Telegram file to the uploads directory. Returns the saved path."""
    uploads = _get_uploads_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize filename
    safe_name = re.sub(r'[^\w\-.]', '_', filename)
    dest = uploads / f"{timestamp}_{safe_name}"
    tg_file = await file_obj.get_file()
    await tg_file.download_to_drive(str(dest))
    return dest


async def handle_document(update: Update, context) -> None:
    """Handle document uploads (PDF, DOCX, TXT, CSV, etc.)."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    doc = update.message.document
    if not doc:
        return

    user_name = update.effective_user.first_name or "User"
    filename = doc.file_name or "unknown_file"
    logger.info(f"Document from {user_name}: {filename} ({doc.file_size} bytes)")

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        saved_path = await _download_telegram_file(doc, filename)
        logger.info(f"Document saved to: {saved_path}")
    except Exception as e:
        logger.error(f"Failed to download document: {e}")
        await update.message.reply_text(f"Failed to download file: {e}")
        return

    # Build prompt: include caption (if any) + file info
    caption = update.message.caption or ""
    user_text = (
        f"User uploaded a file: {filename} ({doc.file_size} bytes)\n"
        f"Saved at: {saved_path}\n"
    )
    if caption:
        user_text += f"User message: {caption}\n"
    user_text += "Read the file and respond to the user about its contents."

    prompt_with_context = build_prompt_with_history(user_text, memory)
    response = await run_agent_query_with_progress(prompt_with_context, update.message.chat)

    memory.log_conversation(role="user", content=f"[File: {filename}] {caption}"[:2000], session_id=SHARED_SESSION_ID)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)

    chunks = split_message(response)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            await update.message.reply_text(chunk[:4096])


async def handle_photo(update: Update, context) -> None:
    """Handle photo uploads."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    if not update.message.photo:
        return

    user_name = update.effective_user.first_name or "User"
    # Get the highest resolution photo
    photo = update.message.photo[-1]
    logger.info(f"Photo from {user_name}: {photo.width}x{photo.height} ({photo.file_size} bytes)")

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        filename = f"photo_{photo.file_unique_id}.jpg"
        saved_path = await _download_telegram_file(photo, filename)
        logger.info(f"Photo saved to: {saved_path}")
    except Exception as e:
        logger.error(f"Failed to download photo: {e}")
        await update.message.reply_text(f"Failed to download photo: {e}")
        return

    caption = update.message.caption or ""
    user_text = (
        f"User sent a photo ({photo.width}x{photo.height})\n"
        f"Saved at: {saved_path}\n"
    )
    if caption:
        user_text += f"User message: {caption}\n"
    user_text += "Analyze the image and respond to the user."

    prompt_with_context = build_prompt_with_history(user_text, memory)
    response = await run_agent_query_with_progress(prompt_with_context, update.message.chat)

    memory.log_conversation(role="user", content=f"[Photo] {caption}"[:2000], session_id=SHARED_SESSION_ID)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)

    chunks = split_message(response)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            await update.message.reply_text(chunk[:4096])


async def handle_voice(update: Update, context) -> None:
    """Handle voice messages — download and pass to agent for transcription/processing."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    voice = update.message.voice
    if not voice:
        return

    user_name = update.effective_user.first_name or "User"
    duration = voice.duration
    logger.info(f"Voice from {user_name}: {duration}s ({voice.file_size} bytes)")

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        filename = f"voice_{voice.file_unique_id}.ogg"
        saved_path = await _download_telegram_file(voice, filename)
        logger.info(f"Voice saved to: {saved_path}")
    except Exception as e:
        logger.error(f"Failed to download voice: {e}")
        await update.message.reply_text(f"Failed to download voice message: {e}")
        return

    user_text = (
        f"User sent a voice message ({duration}s)\n"
        f"Saved at: {saved_path}\n"
        f"Transcribe the voice message and respond to the user."
    )

    prompt_with_context = build_prompt_with_history(user_text, memory)
    response = await run_agent_query_with_progress(prompt_with_context, update.message.chat)

    memory.log_conversation(role="user", content=f"[Voice: {duration}s]"[:2000], session_id=SHARED_SESSION_ID)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)

    chunks = split_message(response)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            await update.message.reply_text(chunk[:4096])


# ── Main ─────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        print("1. Create a bot via @BotFather on Telegram")
        print("2. Add TELEGRAM_BOT_TOKEN=<your-token> to .env")
        sys.exit(1)

    logger.info("Starting Telegram bot...")
    if ALLOWED_IDS:
        logger.info(f"Authorized users: {ALLOWED_IDS}")
    else:
        logger.info("No user whitelist — accepting all users")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("running", cmd_running))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("update", cmd_update_task))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    main()
