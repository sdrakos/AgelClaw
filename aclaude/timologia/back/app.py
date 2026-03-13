"""FastAPI application — main entry point."""
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from db import run_migrations, get_db
from auth import get_current_user, register_user, login_user, get_member_role, require_role
from config import PORT, FERNET, REPORTS_DIR
from chat import router as chat_router
from analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app):
    run_migrations()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="Timologia API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(analytics_router)


# --- Pydantic models ---
class RegisterReq(BaseModel):
    email: str
    password: str
    name: str

class LoginReq(BaseModel):
    email: str
    password: str

class CompanyReq(BaseModel):
    name: str
    afm: str
    aade_user_id: str = ""
    aade_subscription_key: str = ""
    aade_env: str = "dev"

class MemberReq(BaseModel):
    email: str
    role: str = "viewer"

class ScheduleReq(BaseModel):
    company_id: int
    preset: str | None = None
    params: dict | None = None
    cron: str
    recipients: str
    enabled: bool = True


# --- Auth endpoints ---
@app.post("/api/auth/register")
def api_register(req: RegisterReq):
    return register_user(req.email, req.password, req.name)

@app.post("/api/auth/login")
def api_login(req: LoginReq):
    return login_user(req.email, req.password)

@app.get("/api/auth/me")
async def api_me(user=Depends(get_current_user)):
    return user


# --- Company endpoints ---
@app.get("/api/companies")
async def list_companies(user=Depends(get_current_user)):
    with get_db() as conn:
        if user["role"] == "admin":
            rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
        else:
            rows = conn.execute(
                "SELECT c.* FROM companies c "
                "JOIN company_members cm ON cm.company_id=c.id "
                "WHERE cm.user_id=? ORDER BY c.name",
                (user["id"],),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d.pop("aade_user_id", None)
        d.pop("aade_subscription_key", None)
        result.append(d)
    return result

@app.post("/api/companies")
async def create_company(req: CompanyReq, user=Depends(get_current_user)):
    encrypted_uid = FERNET.encrypt(req.aade_user_id.encode()).decode() if req.aade_user_id else ""
    encrypted_key = FERNET.encrypt(req.aade_subscription_key.encode()).decode() if req.aade_subscription_key else ""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, afm, aade_user_id, aade_subscription_key, aade_env) "
            "VALUES (?, ?, ?, ?, ?)",
            (req.name, req.afm, encrypted_uid, encrypted_key, req.aade_env),
        )
        company_id = cur.lastrowid
        conn.execute(
            "INSERT INTO company_members (user_id, company_id, role) VALUES (?, ?, 'owner')",
            (user["id"], company_id),
        )
    return {"id": company_id, "name": req.name, "afm": req.afm}

@app.put("/api/companies/{company_id}")
async def update_company(company_id: int, req: CompanyReq, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    encrypted_uid = FERNET.encrypt(req.aade_user_id.encode()).decode() if req.aade_user_id else ""
    encrypted_key = FERNET.encrypt(req.aade_subscription_key.encode()).decode() if req.aade_subscription_key else ""
    with get_db() as conn:
        conn.execute(
            "UPDATE companies SET name=?, afm=?, aade_user_id=?, aade_subscription_key=?, aade_env=? WHERE id=?",
            (req.name, req.afm, encrypted_uid, encrypted_key, req.aade_env, company_id),
        )
    return {"ok": True}

@app.get("/api/companies/{company_id}/members")
async def list_members(company_id: int, user=Depends(get_current_user)):
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT cm.user_id, cm.role, u.name, u.email "
            "FROM company_members cm JOIN users u ON u.id=cm.user_id "
            "WHERE cm.company_id=? ORDER BY u.name",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/companies/{company_id}/members")
async def add_member(company_id: int, req: MemberReq, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    with get_db() as conn:
        target = conn.execute("SELECT id FROM users WHERE email=?", (req.email,)).fetchone()
        if not target:
            raise HTTPException(404, "User not found")
        conn.execute(
            "INSERT OR REPLACE INTO company_members (user_id, company_id, role) VALUES (?, ?, ?)",
            (target["id"], company_id, req.role),
        )
    return {"ok": True}

@app.delete("/api/companies/{company_id}/members/{uid}")
async def remove_member(company_id: int, uid: int, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    with get_db() as conn:
        conn.execute(
            "DELETE FROM company_members WHERE user_id=? AND company_id=?", (uid, company_id)
        )
    return {"ok": True}


# --- Admin endpoints ---
@app.get("/api/admin/users")
async def admin_list_users(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    with get_db() as conn:
        rows = conn.execute("SELECT id, email, name, role, created_at FROM users").fetchall()
    return [dict(r) for r in rows]

@app.put("/api/admin/users/{uid}")
async def admin_update_user(uid: int, request: Request, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    body = await request.json()
    with get_db() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (body["role"], uid))
    return {"ok": True}


# --- Invoice sync helpers ---

async def _sync_invoices(company_id: int, force: bool = False):
    """Fetch invoices from AADE and upsert into local cache."""
    with get_db() as conn:
        company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
        if not company:
            return
        if not force:
            last = conn.execute(
                "SELECT MAX(synced_at) as last FROM invoices WHERE company_id=?",
                (company_id,),
            ).fetchone()
            if last and last["last"]:
                last_sync = datetime.fromisoformat(last["last"])
                if (datetime.now() - last_sync).total_seconds() < 900:
                    return

    aade_uid = FERNET.decrypt(company["aade_user_id"].encode()).decode() if company["aade_user_id"] else ""
    aade_key = FERNET.decrypt(company["aade_subscription_key"].encode()).decode() if company["aade_subscription_key"] else ""
    if not aade_uid or not aade_key:
        return

    from aade_client import MyDataClient
    client = MyDataClient(aade_uid, aade_key, company["afm"], env=company["aade_env"])

    date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")

    try:
        sent = await client.get_sent_invoices(date_from=date_from, date_to=date_to)
        received = await client.get_received_invoices(date_from=date_from, date_to=date_to)
    finally:
        await client.close()

    # Resolve counterpart names from AFM via GSIS cache
    all_invoices = [(inv, "sent") for inv in sent] + [(inv, "received") for inv in received]
    _resolve_counterpart_names(all_invoices)

    now_str = datetime.now().isoformat()
    with get_db() as conn:
        for inv in sent:
            _upsert_invoice(conn, company_id, inv, "sent", now_str)
        for inv in received:
            _upsert_invoice(conn, company_id, inv, "received", now_str)


def _resolve_counterpart_names(invoices_with_dir: list):
    """Resolve counterpart names from AFM via GSIS SOAP cache.

    For sent invoices: counterpart is in counterpart_vat / counterpart_name
    For received invoices: counterpart (supplier) is in issuer_vat / issuer_name
    """
    from agent import _validate_afm, _afm_cache_get, _afm_cache_put
    try:
        from agent import _soap_lookup_afm
    except Exception:
        return

    for inv, direction in invoices_with_dir:
        if direction == "sent":
            afm = inv.get("counterpart_vat", "")
            name = inv.get("counterpart_name", "")
        else:
            afm = inv.get("issuer_vat", "")
            name = inv.get("issuer_name", "")

        if name or not afm:
            continue

        afm_clean = afm.strip().replace("EL", "").replace("el", "")
        if not _validate_afm(afm_clean):
            continue

        # Check cache
        cached = _afm_cache_get(afm_clean)
        if cached:
            resolved_name = cached.get("name", "")
        else:
            # SOAP lookup (best-effort)
            try:
                info = _soap_lookup_afm(afm_clean)
                _afm_cache_put(afm_clean, info)
                resolved_name = info.get("name", "")
            except Exception:
                continue

        # Write back to the correct field
        if direction == "sent":
            inv["counterpart_name"] = resolved_name
        else:
            inv["issuer_name"] = resolved_name


def _upsert_invoice(conn, company_id: int, inv: dict, direction: str, synced_at: str):
    """Insert or update a single invoice in the local cache."""
    mark = inv.get("mark")
    if not mark:
        return
    net = _to_float(inv.get("totalNetValue", 0))
    vat = _to_float(inv.get("totalVatAmount", 0))
    gross = _to_float(inv.get("totalGrossValue", 0))
    conn.execute(
        """INSERT INTO invoices (company_id, mark, invoice_type, series, aa,
            issue_date, counterpart_afm, counterpart_name,
            net_amount, vat_amount, total_amount, direction, raw_json, synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(company_id, mark, direction) DO UPDATE SET
            invoice_type=excluded.invoice_type,
            series=excluded.series,
            aa=excluded.aa,
            issue_date=excluded.issue_date,
            counterpart_afm=excluded.counterpart_afm,
            counterpart_name=excluded.counterpart_name,
            net_amount=excluded.net_amount,
            vat_amount=excluded.vat_amount,
            total_amount=excluded.total_amount,
            raw_json=excluded.raw_json,
            synced_at=excluded.synced_at""",
        (
            company_id,
            mark,
            inv.get("invoiceType", ""),
            inv.get("series", ""),
            inv.get("aa", ""),
            inv.get("issueDate", ""),
            inv.get("counterpart_vat", "") if direction == "sent" else inv.get("issuer_vat", ""),
            inv.get("counterpart_name", "") if direction == "sent" else inv.get("issuer_name", ""),
            net,
            vat,
            gross,
            direction,
            json.dumps(inv, ensure_ascii=False),
            synced_at,
        ),
    )


def _to_float(val) -> float:
    """Safely convert value to float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# --- Invoice endpoints ---

@app.get("/api/invoices")
async def list_invoices(
    company_id: int = Query(...),
    direction: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    """List invoices with filters and pagination."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    # Trigger background sync (non-blocking)
    asyncio.create_task(_sync_invoices(company_id))

    clauses = ["company_id = ?"]
    params: list = [company_id]

    if direction:
        clauses.append("direction = ?")
        params.append(direction)
    if date_from:
        clauses.append("issue_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("issue_date <= ?")
        params.append(date_to)
    if search:
        clauses.append("(counterpart_afm LIKE ? OR counterpart_name LIKE ? OR mark LIKE ? OR series LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q, q, q])

    where = " AND ".join(clauses)
    offset = (page - 1) * per_page

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM invoices WHERE {where}", params).fetchone()["cnt"]
        summary = conn.execute(
            f"""SELECT
                COALESCE(SUM(net_amount), 0) as total_net,
                COALESCE(SUM(vat_amount), 0) as total_vat,
                COALESCE(SUM(total_amount), 0) as total_gross,
                COALESCE(SUM(CASE WHEN direction='sent' THEN total_amount ELSE 0 END), 0) as sent_total,
                COALESCE(SUM(CASE WHEN direction='received' THEN total_amount ELSE 0 END), 0) as received_total
            FROM invoices WHERE {where}""",
            params,
        ).fetchone()
        rows = conn.execute(
            f"SELECT * FROM invoices WHERE {where} ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "summary": {
            "net": summary["total_net"],
            "vat": summary["total_vat"],
            "gross": summary["total_gross"],
            "sent": summary["sent_total"],
            "received": summary["received_total"],
        },
    }


@app.get("/api/invoices/{mark}")
async def get_invoice(mark: str, company_id: int = Query(...), user=Depends(get_current_user)):
    """Get a single invoice by MARK number."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM invoices WHERE mark = ? AND company_id = ?",
            (mark, company_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Invoice not found")
    result = dict(row)
    result["raw_json"] = json.loads(result.get("raw_json", "{}"))
    return result


# --- Report endpoints ---

@app.get("/api/reports/presets")
async def report_presets(user=Depends(get_current_user)):
    """Return available report presets."""
    from reports import PRESETS
    return PRESETS


class ReportReq(BaseModel):
    company_id: int
    preset: str
    params: dict = {}


@app.post("/api/reports/generate")
async def generate_report(req: ReportReq, user=Depends(get_current_user)):
    """Generate an accounting report (xlsx)."""
    role = get_member_role(user["id"], req.company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    from reports import generate_report as do_generate, PRESETS
    if req.preset not in PRESETS:
        raise HTTPException(400, f"Unknown preset: {req.preset}")

    try:
        result = await do_generate(req.company_id, user["id"], req.preset, req.params)
    except Exception as e:
        raise HTTPException(500, str(e))
    return result


@app.get("/api/reports/history")
async def report_history(
    company_id: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    """List report generation history."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    offset = (page - 1) * per_page
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM report_history WHERE company_id=?", (company_id,)
        ).fetchone()["cnt"]
        rows = conn.execute(
            "SELECT * FROM report_history WHERE company_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (company_id, per_page, offset),
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@app.get("/api/reports/download/{report_id}")
async def download_report(report_id: int, user=Depends(get_current_user)):
    """Download a generated report file."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM report_history WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Report not found")

    # Check access
    role = get_member_role(user["id"], row["company_id"])
    if not role:
        raise HTTPException(403, "Not a member of this company")

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "Report file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# --- Email report ---

class EmailReportReq(BaseModel):
    to: list[str]
    subject: str = ""
    body: str = ""


@app.post("/api/reports/{report_id}/email")
async def email_report(report_id: int, req: EmailReportReq, user=Depends(get_current_user)):
    """Email a report as attachment."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM report_history WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Report not found")

    role = get_member_role(user["id"], row["company_id"])
    if not role:
        raise HTTPException(403, "Not a member of this company")

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "Report file not found")

    if not req.to:
        raise HTTPException(400, "No recipients specified")

    subject = req.subject or f"Αναφορά {row['preset']} - {file_path.stem}"
    body_html = req.body or f"<p>Επισυνάπτεται η αναφορά <b>{file_path.name}</b>.</p><p>Αποστολή από Timologia.</p>"

    from email_sender import send_email
    result = send_email(req.to, subject, body_html, attachments=[str(file_path)])
    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Email send failed"))

    return result


# --- Schedule endpoints ---

@app.post("/api/reports/schedules")
async def create_schedule(req: ScheduleReq, user=Depends(get_current_user)):
    """Create a report schedule (requires accountant+ role)."""
    require_role(user["id"], req.company_id, "accountant")

    # Validate cron format
    from jobs import _parse_cron
    try:
        _parse_cron(req.cron)
    except ValueError as e:
        raise HTTPException(400, str(e))

    params_json = json.dumps(req.params or {}, ensure_ascii=False)
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO report_schedules (company_id, created_by, preset, params, cron, recipients, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (req.company_id, user["id"], req.preset, params_json,
             req.cron, req.recipients, 1 if req.enabled else 0),
        )
        schedule_id = cur.lastrowid
    return {
        "id": schedule_id,
        "preset": req.preset,
        "params": params_json,
        "cron": req.cron,
        "recipients": req.recipients,
        "enabled": req.enabled,
    }


@app.get("/api/reports/schedules")
async def list_schedules(
    company_id: int = Query(...),
    user=Depends(get_current_user),
):
    """List report schedules for a company."""
    role = get_member_role(user["id"], company_id)
    if not role:
        raise HTTPException(403, "Not a member of this company")

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM report_schedules WHERE company_id=? ORDER BY id DESC",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.put("/api/reports/schedules/{schedule_id}")
async def update_schedule(schedule_id: int, req: ScheduleReq, user=Depends(get_current_user)):
    """Update a report schedule (requires accountant+ role)."""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM report_schedules WHERE id=?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "Schedule not found")

    require_role(user["id"], existing["company_id"], "accountant")

    # Validate cron format
    from jobs import _parse_cron
    try:
        _parse_cron(req.cron)
    except ValueError as e:
        raise HTTPException(400, str(e))

    params_json = json.dumps(req.params or {}, ensure_ascii=False)
    with get_db() as conn:
        conn.execute(
            """UPDATE report_schedules
               SET preset=?, params=?, cron=?, recipients=?, enabled=?
               WHERE id=?""",
            (req.preset, params_json, req.cron, req.recipients,
             1 if req.enabled else 0, schedule_id),
        )
    return {"ok": True}


@app.patch("/api/reports/schedules/{schedule_id}")
async def toggle_schedule(schedule_id: int, body: dict, user=Depends(get_current_user)):
    """Toggle a report schedule enabled/disabled."""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM report_schedules WHERE id=?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "Schedule not found")

    require_role(user["id"], existing["company_id"], "accountant")

    enabled = 1 if body.get("enabled") else 0
    with get_db() as conn:
        conn.execute("UPDATE report_schedules SET enabled=? WHERE id=?", (enabled, schedule_id))
    return {"ok": True}


@app.delete("/api/reports/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, user=Depends(get_current_user)):
    """Delete a report schedule (requires accountant+ role)."""
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM report_schedules WHERE id=?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "Schedule not found")

    require_role(user["id"], existing["company_id"], "accountant")

    with get_db() as conn:
        conn.execute("DELETE FROM report_schedules WHERE id=?", (schedule_id,))
    return {"ok": True}


# --- AFM Lookup ---

@app.get("/api/lookup-afm/{afm}")
async def api_lookup_afm(afm: str, user=Depends(get_current_user)):
    """Look up business details by AFM via AADE GSIS SOAP service."""
    from agent import _validate_afm, _afm_cache_get, _afm_cache_put, _soap_lookup_afm

    afm = afm.strip().replace("EL", "").replace("el", "")
    if not _validate_afm(afm):
        raise HTTPException(400, f"Μη έγκυρο ΑΦΜ: {afm}")

    # Check cache
    cached = _afm_cache_get(afm)
    if cached:
        cached["_source"] = "cache"
        return cached

    # SOAP lookup
    try:
        info = _soap_lookup_afm(afm)
    except Exception as e:
        raise HTTPException(502, f"Αποτυχία αναζήτησης ΑΑΔΕ: {e}")

    _afm_cache_put(afm, info)
    info["_source"] = "aade_live"
    return info


# --- Entry point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
