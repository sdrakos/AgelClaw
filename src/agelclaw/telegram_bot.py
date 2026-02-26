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
    get_system_prompt, build_agent_options, build_prompt_with_history,
    SHARED_SESSION_ID, get_agent, get_router, AGENT_TOOLS, PROACTIVE_DIR,
)
from agelclaw.core.config import load_config
from agelclaw.core.agent_router import Provider
from agelclaw.memory import Memory

# ── Setup ────────────────────────────────────────────────────────────
from agelclaw.project import get_env_path
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


async def run_agent_query_with_progress(prompt: str, chat) -> str:
    """Run the agent query with live progress updates to Telegram.
    Routes to Claude or OpenAI based on config."""
    router = get_router()
    route = router.route(task_type="chat")

    if route.provider == Provider.OPENAI:
        return await _run_openai_query(prompt, chat, route.model)
    else:
        return await _run_claude_query(prompt, chat)


async def _run_openai_query(prompt: str, chat, model: str) -> str:
    """Run query via OpenAI Agents SDK (no streaming progress)."""
    progress_msg = None
    try:
        await chat.send_action(ChatAction.TYPING)
        progress_msg = await chat.send_message(f"Processing with OpenAI ({model})...")

        agent = get_agent(provider="openai", model=model)
        result = await agent.run(
            prompt=prompt,
            system_prompt=get_system_prompt(),
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


async def _run_claude_query(prompt: str, chat) -> str:
    """Run query via Claude Agent SDK with streaming progress."""
    options = build_agent_options(max_turns=30)
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
                        elif tool_name == "WebSearch" and isinstance(block.input, dict):
                            q = block.input.get("query", "")
                            if q:
                                detail = f' "{q[:40]}"'

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
        "/tasks - View pending tasks"
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


# ── Message Handler ──────────────────────────────────────────────────

async def handle_message(update: Update, context) -> None:
    """Process any text message through the agent."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    if not user_text:
        return

    user_name = update.effective_user.first_name or "User"
    logger.info(f"Message from {user_name} ({update.effective_user.id}): {user_text[:100]}")

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Build prompt with conversation history from SQLite (shared across all channels)
    prompt_with_context = build_prompt_with_history(user_text, memory)

    # Run the agent query with live progress updates
    response = await run_agent_query_with_progress(prompt_with_context, update.message.chat)

    # Log to memory (log original user text, not the context-enriched prompt)
    memory.log_conversation(role="user", content=user_text[:2000], session_id=SHARED_SESSION_ID)
    memory.log_conversation(role="assistant", content=response[:2000], session_id=SHARED_SESSION_ID)

    # Send response (split if too long)
    chunks = split_message(response)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Fallback: send without any formatting
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
