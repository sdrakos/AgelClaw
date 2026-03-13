"""Chat endpoint — SSE streaming with OpenAI Agents SDK."""
import json
import os
import traceback
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents import Runner
from agent import create_agent, TimologiaContext
from auth import get_current_user, get_member_role, require_role
from config import FERNET, OPENAI_API_KEY
from db import get_db

os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)

router = APIRouter(prefix="/api/chat")


# ── Pydantic models ──

class ChatRequest(BaseModel):
    company_id: int
    message: str
    session_id: str | int | None = None


class ConfirmRequest(BaseModel):
    company_id: int


# ── Helpers ──

def _build_context(user: dict, company_id: int) -> TimologiaContext:
    """Build TimologiaContext from user + company, decrypting AADE creds."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    with get_db() as conn:
        company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if not company:
        raise HTTPException(404, "Company not found")

    aade_uid = ""
    aade_key = ""
    if company["aade_user_id"]:
        try:
            aade_uid = FERNET.decrypt(company["aade_user_id"].encode()).decode()
        except Exception:
            pass
    if company["aade_subscription_key"]:
        try:
            aade_key = FERNET.decrypt(company["aade_subscription_key"].encode()).decode()
        except Exception:
            pass

    return TimologiaContext(
        user_id=user["id"],
        user_role=role,
        company_id=company_id,
        afm=company["afm"],
        company_name=company["name"],
        aade_user_id=aade_uid,
        aade_subscription_key=aade_key,
        aade_env=company["aade_env"],
    )


def _get_or_create_session(user_id: int, company_id: int, session_id: str | int | None) -> tuple[int, list]:
    """Return (session_id, messages_list). Creates new session if needed."""
    with get_db() as conn:
        if session_id:
            row = conn.execute(
                "SELECT id, messages FROM chat_sessions WHERE id=? AND user_id=? AND company_id=?",
                (session_id, user_id, company_id),
            ).fetchone()
            if row:
                messages = json.loads(row["messages"])
                return row["id"], messages

        # Create new session
        cur = conn.execute(
            "INSERT INTO chat_sessions (user_id, company_id, messages) VALUES (?, ?, '[]')",
            (user_id, company_id),
        )
        return cur.lastrowid, []


def _save_session(session_id: int, messages: list):
    """Persist messages to the chat_sessions table."""
    with get_db() as conn:
        conn.execute(
            "UPDATE chat_sessions SET messages=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(messages, ensure_ascii=False), session_id),
        )


def _check_for_confirmation(result) -> dict | None:
    """Check Runner result new_items for dry_run tool outputs containing action_type.

    Returns the parsed action dict if found, else None.
    """
    for item in getattr(result, "new_items", []):
        # Tool output items have output attribute
        output = getattr(item, "output", None)
        if not output or not isinstance(output, str):
            continue
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("dry_run") is True and data.get("action_type"):
            return data
    return None


def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Endpoints ──

@router.post("")
async def chat(req: ChatRequest, user=Depends(get_current_user)):
    """SSE streaming chat endpoint. Runs the OpenAI agent and streams events."""
    context = _build_context(user, req.company_id)
    session_id, messages = _get_or_create_session(user["id"], req.company_id, req.session_id)

    # Append user message
    messages.append({"role": "user", "content": req.message, "ts": datetime.now().isoformat()})

    async def event_stream():
        try:
            # Build agent
            agent = create_agent(context)

            # Build input for the agent: convert stored messages to agent format
            agent_input = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant"):
                    agent_input.append({"role": role, "content": content})

            # Run agent
            result = await Runner.run(agent, input=agent_input, context=context)

            # Extract response text
            response_text = result.final_output or ""

            # Check for confirmation actions in tool outputs
            confirmation = _check_for_confirmation(result)

            # Stream tool call events + detect file outputs (for UI display)
            file_attachments = []
            for item in getattr(result, "new_items", []):
                item_type = getattr(item, "type", "")
                if item_type == "tool_call_item":
                    tool_name = getattr(item, "name", "") or getattr(item, "tool_name", "unknown")
                    tool_args = getattr(item, "arguments", "") or ""
                    yield _sse_event("tool_call", {
                        "tool": tool_name,
                        "arguments": tool_args[:500],
                    })
                # Check tool output for file references (report generation)
                output = getattr(item, "output", None)
                if output and isinstance(output, str):
                    try:
                        out_data = json.loads(output)
                        if isinstance(out_data, dict) and out_data.get("filename") and out_data.get("id"):
                            file_attachments.append({
                                "report_id": out_data["id"],
                                "filename": out_data["filename"],
                                "download_url": f"/api/reports/download/{out_data['id']}",
                            })
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Send file attachment events
            for fa in file_attachments:
                yield _sse_event("file", fa)

            # If there's a confirmation action, store it and send event
            if confirmation:
                action_id = _store_pending_action(
                    session_id=session_id,
                    company_id=req.company_id,
                    action_type=confirmation["action_type"],
                    payload=confirmation,
                    preview=confirmation.get("message", ""),
                )
                yield _sse_event("confirmation", {
                    "action_id": action_id,
                    "action_type": confirmation["action_type"],
                    "preview": confirmation.get("preview", {}),
                    "message": confirmation.get("message", ""),
                })

            # Send text response
            yield _sse_event("text", {"content": response_text, "session_id": session_id})

            # Save assistant message
            messages.append({
                "role": "assistant",
                "content": response_text,
                "ts": datetime.now().isoformat(),
            })
            _save_session(session_id, messages)

            yield _sse_event("done", {"session_id": session_id})

        except Exception as e:
            yield _sse_event("error", {"message": str(e), "detail": traceback.format_exc()[-500:]})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _store_pending_action(session_id: int, company_id: int, action_type: str,
                          payload: dict, preview: str) -> int:
    """Store a pending confirmation action. Returns the action ID."""
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO pending_actions
               (chat_session_id, company_id, action_type, payload, preview, status, expires_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (session_id, company_id, action_type, json.dumps(payload, ensure_ascii=False),
             preview, expires_at),
        )
        return cur.lastrowid


@router.post("/confirm/{action_id}")
async def confirm_action(action_id: int, req: ConfirmRequest, user=Depends(get_current_user)):
    """Execute a pending dry-run action after user confirmation."""
    role = get_member_role(user["id"], req.company_id)
    if not role or role == "viewer":
        raise HTTPException(403, "Requires accountant or owner role")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM pending_actions WHERE id=? AND company_id=?",
            (action_id, req.company_id),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Action not found")
    if row["status"] != "pending":
        raise HTTPException(400, f"Action already {row['status']}")

    # Check expiry
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires_at:
        with get_db() as conn:
            conn.execute("UPDATE pending_actions SET status='expired' WHERE id=?", (action_id,))
        raise HTTPException(400, "Action expired. Please try again.")

    payload = json.loads(row["payload"])
    action_type = row["action_type"]
    original_args = payload.get("original_args", {})

    # Build context for execution
    context = _build_context(user, req.company_id)

    try:
        if action_type == "send_invoice":
            from invoice_xml import build_invoice_xml
            from aade_client import MyDataClient

            xml_bytes = build_invoice_xml(
                issuer_vat=context.afm,
                issuer_country="GR",
                issuer_branch=0,
                counterpart_vat=original_args["counterpart_vat"],
                invoice_type=original_args["invoice_type"],
                series=original_args["series"],
                number=original_args["number"],
                items=original_args["items"],
                env=context.aade_env,
            )
            client = MyDataClient(
                context.aade_user_id, context.aade_subscription_key,
                context.afm, env=context.aade_env,
            )
            try:
                raw_result = await client.send_invoice_xml(xml_bytes)
                result = client._parse_response(raw_result)
            finally:
                await client.close()

        elif action_type == "cancel_invoice":
            from aade_client import MyDataClient

            client = MyDataClient(
                context.aade_user_id, context.aade_subscription_key,
                context.afm, env=context.aade_env,
            )
            try:
                result = await client.cancel_invoice(original_args["mark"])
            finally:
                await client.close()

        elif action_type == "update_company_settings":
            changes = {}
            if original_args.get("name"):
                changes["name"] = original_args["name"]
            if original_args.get("aade_env") and original_args["aade_env"] in ("dev", "prod"):
                changes["aade_env"] = original_args["aade_env"]

            with get_db() as conn:
                for key, val in changes.items():
                    conn.execute(f"UPDATE companies SET {key}=? WHERE id=?", (val, req.company_id))
            result = {"updated": changes}

        else:
            raise HTTPException(400, f"Unknown action type: {action_type}")

        # Mark action as confirmed
        with get_db() as conn:
            conn.execute("UPDATE pending_actions SET status='confirmed' WHERE id=?", (action_id,))

        return {"ok": True, "action_type": action_type, "result": result}

    except HTTPException:
        raise
    except Exception as e:
        # Mark action as failed
        with get_db() as conn:
            conn.execute("UPDATE pending_actions SET status='failed' WHERE id=?", (action_id,))
        raise HTTPException(500, f"Action failed: {str(e)}")


@router.post("/reject/{action_id}")
async def reject_action(action_id: int, req: ConfirmRequest, user=Depends(get_current_user)):
    """Reject a pending action."""
    role = get_member_role(user["id"], req.company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM pending_actions WHERE id=? AND company_id=?",
            (action_id, req.company_id),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Action not found")
    if row["status"] != "pending":
        raise HTTPException(400, f"Action already {row['status']}")

    with get_db() as conn:
        conn.execute("UPDATE pending_actions SET status='rejected' WHERE id=?", (action_id,))

    return {"ok": True, "status": "rejected"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: int, user=Depends(get_current_user)):
    """Load messages for a specific chat session."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT messages FROM chat_sessions WHERE id=? AND user_id=?",
            (session_id, user["id"]),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    messages = json.loads(row["messages"])
    return {"session_id": session_id, "messages": messages}


@router.get("/sessions")
async def list_sessions(
    company_id: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    """List chat sessions for user + company, paginated."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    offset = (page - 1) * per_page
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM chat_sessions WHERE user_id=? AND company_id=?",
            (user["id"], company_id),
        ).fetchone()["cnt"]

        rows = conn.execute(
            "SELECT id, user_id, company_id, created_at, updated_at FROM chat_sessions "
            "WHERE user_id=? AND company_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (user["id"], company_id, per_page, offset),
        ).fetchall()

    sessions = [dict(r) for r in rows]

    # Enrich with message count + first user message as title
    with get_db() as conn:
        for s in sessions:
            row = conn.execute("SELECT messages FROM chat_sessions WHERE id=?", (s["id"],)).fetchone()
            if row:
                msgs = json.loads(row["messages"])
                s["message_count"] = len(msgs)
                # Use first user message as title
                first_user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
                s["last_message"] = first_user[:80] if first_user else ""
            else:
                s["message_count"] = 0
                s["last_message"] = ""

    return {
        "items": sessions,
        "total": total,
        "page": page,
        "per_page": per_page,
    }
