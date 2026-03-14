"""Telegram bot for Timologia — authenticated per-company access."""
import os
import json
import asyncio
import logging
import httpx
from datetime import datetime
from pathlib import Path
from db import get_db

MAX_HISTORY = 20  # Keep last N messages per session

log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "timologia-tg-secret")


async def set_webhook(base_url: str):
    """Set Telegram webhook URL and register bot commands."""
    url = f"{base_url}/api/telegram/webhook/{WEBHOOK_SECRET}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_URL}/setWebhook", json={"url": url})
        log.info(f"Telegram webhook set: {resp.json()}")
        # Register bot commands (visible when user types /)
        await client.post(f"{API_URL}/setMyCommands", json={"commands": [
            {"command": "company", "description": "Αλλαγή εταιρείας"},
            {"command": "unlink", "description": "Αποσύνδεση λογαριασμού"},
            {"command": "start", "description": "Σύνδεση με Timologia"},
        ]})


async def send_message(chat_id: str | int, text: str):
    """Send a Telegram message."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        })


async def send_document(chat_id: str | int, file_path: str, caption: str = ""):
    """Send a file as a Telegram document."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(file_path, "rb") as f:
            await client.post(
                f"{API_URL}/sendDocument",
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (Path(file_path).name, f)},
            )


def get_user_by_chat_id(chat_id: str) -> dict | None:
    """Find user linked to a Telegram chat_id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, name, role, telegram_company_id FROM users WHERE telegram_chat_id = ?",
            (str(chat_id),)
        ).fetchone()
    return dict(row) if row else None


def _is_admin(user_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    return row and row["role"] == "admin"


def get_user_company(user_id: int, company_id: int | None = None) -> dict | None:
    """Get a specific company or the user's active telegram company. Admin sees all."""
    admin = _is_admin(user_id)
    with get_db() as conn:
        if company_id:
            if admin:
                row = conn.execute(
                    "SELECT id, name, afm, aade_env, aade_user_id, aade_subscription_key "
                    "FROM companies WHERE id = ?", (company_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT c.id, c.name, c.afm, c.aade_env, c.aade_user_id, c.aade_subscription_key "
                    "FROM companies c JOIN company_members cm ON cm.company_id = c.id "
                    "WHERE cm.user_id = ? AND c.id = ?",
                    (user_id, company_id)
                ).fetchone()
        else:
            if admin:
                row = conn.execute(
                    "SELECT id, name, afm, aade_env, aade_user_id, aade_subscription_key "
                    "FROM companies ORDER BY id LIMIT 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT c.id, c.name, c.afm, c.aade_env, c.aade_user_id, c.aade_subscription_key "
                    "FROM companies c JOIN company_members cm ON cm.company_id = c.id "
                    "WHERE cm.user_id = ? ORDER BY c.id LIMIT 1",
                    (user_id,)
                ).fetchone()
    return dict(row) if row else None


def get_user_companies(user_id: int) -> list:
    """Get all companies the user is a member of. Admin sees all."""
    admin = _is_admin(user_id)
    with get_db() as conn:
        if admin:
            rows = conn.execute(
                "SELECT id, name, afm FROM companies ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT c.id, c.name, c.afm "
                "FROM companies c JOIN company_members cm ON cm.company_id = c.id "
                "WHERE cm.user_id = ? ORDER BY c.name",
                (user_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def set_active_company(user_id: int, company_id: int):
    """Set the active telegram company for a user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET telegram_company_id = ? WHERE id = ?",
            (company_id, user_id)
        )


def link_telegram(token: str, chat_id: str) -> dict | None:
    """Validate link token and bind chat_id to user. Returns user info or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT tlt.id, tlt.user_id, tlt.company_id, u.name, c.name as company_name "
            "FROM telegram_link_tokens tlt "
            "JOIN users u ON u.id = tlt.user_id "
            "JOIN companies c ON c.id = tlt.company_id "
            "WHERE tlt.token = ? AND tlt.used = 0 AND tlt.expires_at > datetime('now')",
            (token,)
        ).fetchone()
        if not row:
            return None
        # Mark token as used
        conn.execute("UPDATE telegram_link_tokens SET used = 1 WHERE id = ?", (row["id"],))
        # Set chat_id and active company on user
        conn.execute(
            "UPDATE users SET telegram_chat_id = ?, telegram_company_id = ? WHERE id = ?",
            (str(chat_id), row["company_id"], row["user_id"])
        )
    return {"name": row["name"], "company_name": row["company_name"], "company_id": row["company_id"]}


def _get_tg_session(user_id: int, company_id: int) -> tuple[int, list]:
    """Get or create a Telegram chat session. Returns (session_id, messages)."""
    with get_db() as conn:
        # Find existing Telegram session for this user+company (most recent)
        row = conn.execute(
            "SELECT id, messages FROM chat_sessions "
            "WHERE user_id=? AND company_id=? ORDER BY updated_at DESC LIMIT 1",
            (user_id, company_id),
        ).fetchone()
        if row:
            messages = json.loads(row["messages"])
            # Trim old messages
            if len(messages) > MAX_HISTORY:
                messages = messages[-MAX_HISTORY:]
            return row["id"], messages
        # Create new
        cur = conn.execute(
            "INSERT INTO chat_sessions (user_id, company_id, messages, created_at, updated_at) "
            "VALUES (?, ?, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (user_id, company_id),
        )
        return cur.lastrowid, []


def _save_tg_session(session_id: int, messages: list):
    """Save Telegram chat session messages."""
    with get_db() as conn:
        conn.execute(
            "UPDATE chat_sessions SET messages=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(messages, ensure_ascii=False), session_id),
        )


def unlink_telegram(user_id: int):
    """Remove Telegram link for a user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET telegram_chat_id = NULL, telegram_company_id = NULL WHERE id = ?",
            (user_id,)
        )


async def handle_update(update: dict):
    """Process a Telegram webhook update."""
    message = update.get("message")
    if not message:
        return

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()

    # Handle /start with token
    if text.startswith("/start "):
        token = text.split(" ", 1)[1].strip()
        result = link_telegram(token, chat_id)
        if result:
            await send_message(chat_id,
                f"Καλώς ήρθες <b>{result['name']}</b>!\n"
                f"Συνδέθηκες με την εταιρεία <b>{result['company_name']}</b>.\n\n"
                f"Μπορείς να μου κάνεις ερωτήσεις για τα τιμολόγιά σου, "
                f"να ζητήσεις αναφορές ή να στείλεις παραστατικά.\n\n"
                f"Εντολές:\n"
                f"/company — αλλαγή εταιρείας\n"
                f"/unlink — αποσύνδεση"
            )
        else:
            await send_message(chat_id,
                "Το link σύνδεσης δεν είναι έγκυρο ή έχει λήξει.\n"
                "Δημιουργήστε νέο από: timologia.me → Ρυθμίσεις → Σύνδεση Telegram"
            )
        return

    # Handle /start without token
    if text == "/start":
        await send_message(chat_id,
            "Για να χρησιμοποιήσετε το Timologia Bot, "
            "συνδεθείτε μέσω:\ntimologia.me → Ρυθμίσεις → Σύνδεση Telegram"
        )
        return

    # Handle /unlink
    if text == "/unlink":
        user = get_user_by_chat_id(chat_id)
        if user:
            unlink_telegram(user["id"])
            await send_message(chat_id, "Αποσυνδέθηκες επιτυχώς. Μπορείς να συνδεθείς ξανά από τα Settings.")
        else:
            await send_message(chat_id, "Δεν είσαι συνδεδεμένος.")
        return

    # Handle /company — switch active company
    if text == "/company":
        user = get_user_by_chat_id(chat_id)
        if not user:
            await send_message(chat_id, "Δεν είστε συνδεδεμένος.")
            return
        companies = get_user_companies(user["id"])
        if len(companies) <= 1:
            await send_message(chat_id, "Έχετε μόνο μία εταιρεία.")
            return
        lines = ["Επιλέξτε εταιρεία (στείλτε τον αριθμό):\n"]
        for i, c in enumerate(companies, 1):
            active = " ✓" if c["id"] == user.get("telegram_company_id") else ""
            lines.append(f"{i}. {c['name']} (ΑΦΜ: {c['afm']}){active}")
        await send_message(chat_id, "\n".join(lines))
        return

    # Check if user is selecting a company (digit response after /company)
    user = get_user_by_chat_id(chat_id)
    if user and text.isdigit():
        companies = get_user_companies(user["id"])
        idx = int(text) - 1
        if 0 <= idx < len(companies):
            set_active_company(user["id"], companies[idx]["id"])
            await send_message(chat_id, f"Ενεργή εταιρεία: <b>{companies[idx]['name']}</b>")
            return

    # Regular message — forward to AI agent
    if not user:
        await send_message(chat_id,
            "Δεν είστε συνδεδεμένος.\n"
            "Συνδεθείτε μέσω: timologia.me → Ρυθμίσεις → Σύνδεση Telegram"
        )
        return

    company = get_user_company(user["id"], user.get("telegram_company_id"))
    if not company:
        company = get_user_company(user["id"])
    if not company:
        await send_message(chat_id, "Δεν βρέθηκε εταιρεία. Προσθέστε μία στο timologia.me")
        return

    # Run agent query with conversation history
    await send_message(chat_id, "Επεξεργασία...")
    try:
        from agent import create_agent, TimologiaContext
        from config import FERNET, REPORTS_DIR
        from agents import Runner

        ctx = TimologiaContext(
            user_id=user["id"],
            user_role=user["role"],
            company_id=company["id"],
            afm=company["afm"],
            company_name=company["name"],
            aade_user_id=FERNET.decrypt(company["aade_user_id"].encode()).decode() if company["aade_user_id"] else "",
            aade_subscription_key=FERNET.decrypt(company["aade_subscription_key"].encode()).decode() if company["aade_subscription_key"] else "",
            aade_env=company["aade_env"],
        )

        # Load or create chat session for this user+company on Telegram
        session_id, messages = _get_tg_session(user["id"], company["id"])
        messages.append({"role": "user", "content": text, "ts": datetime.now().isoformat()})

        # Build agent input with history
        agent_input = [{"role": m["role"], "content": m["content"]}
                       for m in messages if m.get("role") in ("user", "assistant")]

        agent = create_agent(ctx)
        result = await Runner.run(agent, input=agent_input, context=ctx)
        reply = result.final_output or "Δεν μπόρεσα να απαντήσω."

        # Save assistant reply to session
        messages.append({"role": "assistant", "content": reply, "ts": datetime.now().isoformat()})
        # Trim to last N messages
        if len(messages) > MAX_HISTORY:
            messages = messages[-MAX_HISTORY:]
        _save_tg_session(session_id, messages)

        # Check if agent generated a report file
        report_sent = False
        for item in getattr(result, "new_items", []):
            output = getattr(item, "output", None)
            if output and isinstance(output, str):
                try:
                    data = json.loads(output)
                    if isinstance(data, dict) and data.get("filename"):
                        fpath = REPORTS_DIR / data["filename"]
                        if fpath.exists():
                            await send_document(chat_id, str(fpath), f"Αναφορά: {data['filename']}")
                            report_sent = True
                except (json.JSONDecodeError, TypeError):
                    pass

        # Send text reply
        for i in range(0, len(reply), 4000):
            await send_message(chat_id, reply[i:i + 4000])

    except Exception as e:
        log.exception(f"Telegram agent error: {e}")
        await send_message(chat_id, "Προέκυψε σφάλμα. Δοκιμάστε ξανά αργότερα.")
