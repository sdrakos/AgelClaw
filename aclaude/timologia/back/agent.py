"""OpenAI Agents SDK — Timologia assistant with AADE tools."""
import json
import re
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from agents import Agent, RunContextWrapper, function_tool
from db import get_db


# ── Greek timezone ──

def _greek_now() -> datetime:
    """Return current datetime in Greek timezone."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Athens"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=3)))


# ── AFM Lookup (GSIS SOAP + SQLite cache) ──

_AFM_CACHE_DB = Path(__file__).parent / "data" / "afm_cache.db"
_GSIS_WSDL = "https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2?WSDL"


def _validate_afm(afm: str) -> bool:
    afm = afm.strip().replace("EL", "").replace("el", "")
    if not re.match(r'^\d{9}$', afm):
        return False
    digits = [int(d) for d in afm]
    total = sum(digits[i] * (2 ** (8 - i)) for i in range(8))
    return (total % 11) % 10 == digits[8]


def _afm_cache_get(afm: str) -> dict | None:
    """Get cached AFM info (90-day TTL)."""
    _AFM_CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(_AFM_CACHE_DB)) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS businesses (
                afm TEXT PRIMARY KEY, data JSON NOT NULL, lookup_date TEXT NOT NULL
            )""")
            row = conn.execute("SELECT data, lookup_date FROM businesses WHERE afm=?", (afm,)).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        lookup_dt = datetime.fromisoformat(row[1])
        if (datetime.now() - lookup_dt).days > 90:
            return None
        return data
    except Exception:
        return None


def _afm_cache_put(afm: str, data: dict):
    _AFM_CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(_AFM_CACHE_DB)) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS businesses (
                afm TEXT PRIMARY KEY, data JSON NOT NULL, lookup_date TEXT NOT NULL
            )""")
            conn.execute(
                "INSERT OR REPLACE INTO businesses (afm, data, lookup_date) VALUES (?, ?, ?)",
                (afm, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
            )
    except Exception:
        pass


def _soap_lookup_afm(afm: str) -> dict:
    """Call AADE RgWsPublic2 SOAP to look up business info by AFM."""
    try:
        from zeep import Client as SoapClient
        from zeep.transports import Transport
        from zeep.wsse.username import UsernameToken
    except ImportError:
        raise RuntimeError("zeep not installed: pip install zeep")

    username = os.environ.get("GSIS_AFM_USERNAME", "")
    password = os.environ.get("GSIS_AFM_PASSWORD", "")
    caller = os.environ.get("GSIS_CALLER_AFM", "")

    if not username or not password:
        raise ValueError("GSIS_AFM_USERNAME and GSIS_AFM_PASSWORD env vars not set")

    transport = Transport(timeout=30)
    wsse = UsernameToken(username, password)
    client = SoapClient(_GSIS_WSDL, transport=transport, wsse=wsse)

    result = client.service.rgWsPublic2AfmMethod(
        INPUT_REC={"afm_called_by": caller, "afm_called_for": afm}
    )

    if result.error_rec and result.error_rec.error_code:
        raise RuntimeError(f"AADE error: {result.error_rec.error_code} - {result.error_rec.error_descr}")

    basic = result.basic_rec if hasattr(result, "basic_rec") else result
    info = {
        "afm": afm,
        "name": getattr(basic, "onomasia", "") or "",
        "commercial_title": getattr(basic, "commer_title", "") or "",
        "doy_code": str(getattr(basic, "doy", "") or ""),
        "doy_description": getattr(basic, "doy_descr", "") or "",
        "legal_status": getattr(basic, "legal_status_descr", "") or "",
        "is_active": str(getattr(basic, "deactivation_flag", "1")) != "2",
        "address": f"{getattr(basic, 'postal_address', '') or ''} {getattr(basic, 'postal_address_no', '') or ''}, {getattr(basic, 'postal_zip_code', '') or ''} {getattr(basic, 'postal_area_description', '') or ''}".strip(", "),
    }

    # Extract ΚΑΔ (business activity codes)
    activities = []
    if hasattr(result, "firm_act_tab") and result.firm_act_tab:
        act_list = result.firm_act_tab.item if hasattr(result.firm_act_tab, "item") else result.firm_act_tab
        if not isinstance(act_list, list):
            act_list = [act_list]
        for act in act_list:
            kad = {
                "code": str(getattr(act, "firm_act_code", "") or ""),
                "description": getattr(act, "firm_act_descr", "") or "",
                "kind": str(getattr(act, "firm_act_kind", "") or ""),
            }
            # kind: 1=κύρια, 2=δευτερεύουσα
            kad["kind_description"] = "Κύρια" if kad["kind"] == "1" else "Δευτερεύουσα"
            activities.append(kad)
    info["activities"] = activities
    return info


@dataclass
class TimologiaContext:
    user_id: int
    user_role: str
    company_id: int
    afm: str
    company_name: str
    aade_user_id: str
    aade_subscription_key: str
    aade_env: str


def _get_client(ctx: TimologiaContext):
    from aade_client import MyDataClient
    return MyDataClient(
        ctx.aade_user_id, ctx.aade_subscription_key,
        ctx.afm, env=ctx.aade_env,
    )


# ── Tool 1: Get Invoices (local cache) ──

@function_tool
async def get_invoices(
    ctx: RunContextWrapper[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
    direction: str = "all",
    counterpart_afm: str = "",
    counterpart_name: str = "",
) -> str:
    """Αναζήτηση παραστατικών από τοπικό cache (ίδια δεδομένα με το web).
    date_from, date_to: μορφή YYYY-MM-DD (π.χ. '2026-02-01').
    direction: 'sent', 'received', ή 'all' (default).
    counterpart_afm: φιλτράρισμα κατά ΑΦΜ αντισυμβαλλομένου (προαιρετικό).
    counterpart_name: αναζήτηση κατά επωνυμία αντισυμβαλλομένου (LIKE, προαιρετικό).
    Επιστρέφει λίστα παραστατικών + σύνοψη (πλήθος, καθαρή αξία, ΦΠΑ, σύνολο)."""
    tc = ctx.context

    # Trigger sync if needed (background-safe)
    try:
        from app import _sync_invoices
        await _sync_invoices(tc.company_id)
    except Exception:
        pass

    query = "SELECT * FROM invoices WHERE company_id = ?"
    params: list = [tc.company_id]

    if date_from:
        query += " AND issue_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND issue_date <= ?"
        params.append(date_to)
    if direction and direction != "all":
        query += " AND direction = ?"
        params.append(direction)
    if counterpart_afm:
        query += " AND counterpart_afm = ?"
        params.append(counterpart_afm)
    if counterpart_name:
        query += " AND counterpart_name LIKE ?"
        params.append(f"%{counterpart_name}%")

    query += " ORDER BY issue_date DESC LIMIT 100"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    invoices = []
    total_net = 0.0
    total_vat = 0.0
    total_gross = 0.0
    for r in rows:
        inv = {
            "mark": r["mark"],
            "invoice_type": r["invoice_type"],
            "series": r["series"],
            "aa": r["aa"],
            "issue_date": r["issue_date"],
            "counterpart_afm": r["counterpart_afm"],
            "counterpart_name": r["counterpart_name"],
            "net_amount": r["net_amount"],
            "vat_amount": r["vat_amount"],
            "total_amount": r["total_amount"],
            "direction": r["direction"],
        }
        invoices.append(inv)
        total_net += r["net_amount"] or 0
        total_vat += r["vat_amount"] or 0
        total_gross += r["total_amount"] or 0

    result = {
        "invoices": invoices,
        "summary": {
            "count": len(invoices),
            "total_net": round(total_net, 2),
            "total_vat": round(total_vat, 2),
            "total_gross": round(total_gross, 2),
        },
    }
    return json.dumps(result, ensure_ascii=False)


# ── Tool 2: Income Summary ──

@function_tool
async def income_summary(
    ctx: RunContextWrapper[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Σύνοψη εσόδων κατά κατηγορία ΦΠΑ (raw XML από AADE API). ΜΗΝ χρησιμοποιείς για λίστα/πλήθος/ποσά παραστατικών — χρησιμοποίησε get_invoices αντ' αυτού. date_from, date_to: μορφή YYYY-MM-DD."""
    tc = ctx.context
    today = _greek_now().strftime("%Y-%m-%d")
    if not date_from:
        date_from = today
    if not date_to:
        date_to = today
    client = _get_client(tc)
    try:
        data = await client.get_income(date_from, date_to)
    finally:
        await client.close()
    return data.decode("utf-8", errors="replace")[:4000]


# ── Tool 3: Expenses Summary ──

@function_tool
async def expenses_summary(
    ctx: RunContextWrapper[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Σύνοψη εξόδων κατά κατηγορία ΦΠΑ (raw XML από AADE API). ΜΗΝ χρησιμοποιείς για λίστα/πλήθος/ποσά παραστατικών — χρησιμοποίησε get_invoices αντ' αυτού. date_from, date_to: μορφή YYYY-MM-DD."""
    tc = ctx.context
    today = _greek_now().strftime("%Y-%m-%d")
    if not date_from:
        date_from = today
    if not date_to:
        date_to = today
    client = _get_client(tc)
    try:
        data = await client.get_expenses(date_from, date_to)
    finally:
        await client.close()
    return data.decode("utf-8", errors="replace")[:4000]


# ── Tool 4: Send Invoice ──

@function_tool
async def send_invoice(
    ctx: RunContextWrapper[TimologiaContext],
    counterpart_vat: str,
    invoice_type: str,
    series: str,
    number: int,
    items_json: str,
    dry_run: bool = True,
) -> str:
    """Αποστολή παραστατικού στο AADE.
    items_json: JSON string, π.χ. '[{"net_value": 100, "vat_category": 1}]'
    dry_run=True: επιστρέφει preview χωρίς αποστολή.
    dry_run=False: αποστέλλει πραγματικά στο AADE.
    """
    tc = ctx.context
    items = json.loads(items_json)

    from invoice_xml import build_invoice_xml

    # Build XML for preview or actual send
    xml_bytes = build_invoice_xml(
        issuer_vat=tc.afm,
        issuer_country="GR",
        issuer_branch=0,
        counterpart_vat=counterpart_vat,
        invoice_type=invoice_type,
        series=series,
        number=number,
        items=items,
        env=tc.aade_env,
    )

    if dry_run:
        from lxml import etree
        pretty = etree.tostring(
            etree.fromstring(xml_bytes), pretty_print=True, encoding="unicode",
        )
        # Calculate totals for preview
        from decimal import Decimal
        total_net = sum(Decimal(str(it["net_value"])) for it in items)
        from invoice_xml import VAT_RATES
        total_vat = sum(
            (Decimal(str(it["net_value"])) * VAT_RATES.get(int(it.get("vat_category", 1)), Decimal("0.24"))).quantize(Decimal("0.01"))
            for it in items
        )
        total_gross = total_net + total_vat

        return json.dumps({
            "dry_run": True,
            "action_type": "send_invoice",
            "preview": {
                "issuer_afm": tc.afm,
                "counterpart_vat": counterpart_vat,
                "invoice_type": invoice_type,
                "series": series,
                "number": number,
                "items_count": len(items),
                "total_net": str(total_net),
                "total_vat": str(total_vat),
                "total_gross": str(total_gross),
                "xml_preview": pretty[:2000],
            },
            "original_args": {
                "counterpart_vat": counterpart_vat,
                "invoice_type": invoice_type,
                "series": series,
                "number": number,
                "items": items,
            },
            "message": "Προεπισκόπηση παραστατικού. Πατήστε 'Επιβεβαίωση' για αποστολή.",
        }, ensure_ascii=False)

    # Real send
    client = _get_client(tc)
    try:
        result = await client.send_invoice_xml(xml_bytes)
        parsed = client._parse_response(result)
    finally:
        await client.close()

    return json.dumps({
        "dry_run": False,
        "action_type": "send_invoice",
        "result": parsed,
    }, ensure_ascii=False, default=str)


# ── Tool 5: Cancel Invoice ──

@function_tool
async def cancel_invoice(
    ctx: RunContextWrapper[TimologiaContext],
    mark: str,
    dry_run: bool = True,
) -> str:
    """Ακύρωση παραστατικού βάσει MARK.
    dry_run=True: επιστρέφει preview.
    dry_run=False: ακυρώνει πραγματικά.
    """
    tc = ctx.context

    if dry_run:
        return json.dumps({
            "dry_run": True,
            "action_type": "cancel_invoice",
            "preview": {
                "mark": mark,
                "company_afm": tc.afm,
            },
            "original_args": {
                "mark": mark,
            },
            "message": f"Θα ακυρωθεί το παραστατικό με MARK {mark}. Πατήστε 'Επιβεβαίωση' για ακύρωση.",
        }, ensure_ascii=False)

    # Real cancel
    client = _get_client(tc)
    try:
        result = await client.cancel_invoice(mark)
    finally:
        await client.close()

    return json.dumps({
        "dry_run": False,
        "action_type": "cancel_invoice",
        "result": result,
    }, ensure_ascii=False, default=str)


# ── Tool 6: Generate Report ──

@function_tool
async def generate_report_tool(
    ctx: RunContextWrapper[TimologiaContext],
    preset: str = "daily_summary",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Δημιουργία λογιστικής αναφοράς (Excel).
    presets: daily_summary, monthly_vat, quarterly_income, annual_overview, custom.
    ΣΗΜΑΝΤΙΚΟ: Αν ο χρήστης ζητήσει αναφορά για συγκεκριμένη ημερομηνία (π.χ. "10/03/2026"),
    χρησιμοποίησε preset="custom" με date_from και date_to σε μορφή YYYY-MM-DD.
    Χρησιμοποίησε daily_summary ΜΟΝΟ αν ζητήσει "σήμερα" ή "ημερήσια" χωρίς ημερομηνία.
    Το αρχείο Excel κατεβαίνει αυτόματα στον χρήστη — ΜΗΝ εμφανίσεις path ή link.
    """
    tc = ctx.context
    from reports import generate_report

    params = {}
    # If date_from/date_to provided, always use custom preset
    if date_from or date_to:
        preset = "custom"
        params = {"date_from": date_from, "date_to": date_to}
    elif preset == "custom":
        params = {"date_from": date_from, "date_to": date_to}

    result = await generate_report(tc.company_id, tc.user_id, preset, params)
    # Remove file_path — the frontend handles download via report ID
    result.pop("file_path", None)
    return json.dumps(result, ensure_ascii=False, default=str)


# ── Tool 7: List Companies ──

@function_tool
async def list_companies(ctx: RunContextWrapper[TimologiaContext]) -> str:
    """Λίστα εταιρειών στις οποίες έχει πρόσβαση ο χρήστης."""
    tc = ctx.context
    with get_db() as conn:
        rows = conn.execute(
            "SELECT c.id, c.name, c.afm, c.aade_env, cm.role "
            "FROM companies c "
            "JOIN company_members cm ON cm.company_id=c.id "
            "WHERE cm.user_id=? ORDER BY c.name",
            (tc.user_id,),
        ).fetchall()
    companies = [dict(r) for r in rows]
    return json.dumps(companies, ensure_ascii=False)


# ── Tool 8: Get Company Settings ──

@function_tool
async def get_company_settings(ctx: RunContextWrapper[TimologiaContext]) -> str:
    """Ρυθμίσεις τρέχουσας εταιρείας."""
    tc = ctx.context
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, afm, aade_env, default_branch, created_at FROM companies WHERE id=?",
            (tc.company_id,),
        ).fetchone()
    if not row:
        return json.dumps({"error": "Company not found"})
    return json.dumps(dict(row), ensure_ascii=False)


# ── Tool 9: Update Company Settings ──

@function_tool
async def update_company_settings(
    ctx: RunContextWrapper[TimologiaContext],
    name: str = "",
    aade_env: str = "",
    dry_run: bool = True,
) -> str:
    """Ενημέρωση ρυθμίσεων εταιρείας. Απαιτεί ρόλο owner.
    dry_run=True: επιστρέφει preview.
    dry_run=False: εφαρμόζει τις αλλαγές.
    """
    tc = ctx.context

    if tc.user_role not in ("owner", "admin"):
        return json.dumps({"error": "Απαιτείται ρόλος owner ή admin."}, ensure_ascii=False)

    changes = {}
    if name:
        changes["name"] = name
    if aade_env and aade_env in ("dev", "prod"):
        changes["aade_env"] = aade_env

    if not changes:
        return json.dumps({"error": "Δεν δόθηκαν αλλαγές."}, ensure_ascii=False)

    if dry_run:
        return json.dumps({
            "dry_run": True,
            "action_type": "update_company_settings",
            "preview": {
                "company_id": tc.company_id,
                "changes": changes,
            },
            "original_args": {
                "name": name,
                "aade_env": aade_env,
            },
            "message": f"Θα ενημερωθούν οι ρυθμίσεις: {changes}. Πατήστε 'Επιβεβαίωση'.",
        }, ensure_ascii=False)

    # Apply changes
    with get_db() as conn:
        for key, val in changes.items():
            conn.execute(f"UPDATE companies SET {key}=? WHERE id=?", (val, tc.company_id))

    return json.dumps({
        "dry_run": False,
        "action_type": "update_company_settings",
        "result": {"updated": changes},
    }, ensure_ascii=False)


# ── Tool 10: Lookup AFM ──

@function_tool
async def lookup_afm(
    ctx: RunContextWrapper[TimologiaContext],
    afm: str,
) -> str:
    """Αναζήτηση στοιχείων επιχείρησης από ΑΦΜ μέσω ΑΑΔΕ (GSIS).
    Επιστρέφει: επωνυμία, ΔΟΥ, διεύθυνση, νομική μορφή, κατάσταση, ΚΑΔ (κωδικοί δραστηριότητας).
    Χρησιμοποίησε αυτό το tool για να βρεις το όνομα ενός προμηθευτή/πελάτη από το ΑΦΜ του
    ή για να δεις τους ΚΑΔ (κύριους και δευτερεύοντες).
    """
    afm = afm.strip().replace("EL", "").replace("el", "")

    if not _validate_afm(afm):
        return json.dumps({"error": f"Μη έγκυρο ΑΦΜ: {afm}"}, ensure_ascii=False)

    # Check cache first (skip if missing activities — old cache format)
    cached = _afm_cache_get(afm)
    if cached and "activities" in cached:
        cached["_source"] = "cache"
        return json.dumps(cached, ensure_ascii=False)

    # SOAP lookup
    try:
        info = _soap_lookup_afm(afm)
    except Exception as e:
        return json.dumps({"error": f"Αποτυχία αναζήτησης ΑΑΔΕ: {e}"}, ensure_ascii=False)

    _afm_cache_put(afm, info)
    info["_source"] = "aade_live"
    return json.dumps(info, ensure_ascii=False)


# ── Tool 11: Email Report ──

@function_tool
async def email_report(
    ctx: RunContextWrapper[TimologiaContext],
    report_id: int,
    to_emails: str,
    subject: str = "",
    body: str = "",
) -> str:
    """Αποστολή αναφοράς Excel με email.
    report_id: ID αναφοράς (από generate_report_tool).
    to_emails: Email παραληπτών χωρισμένα με κόμμα (π.χ. "a@b.com, c@d.com").
    subject: Θέμα email (προαιρετικό).
    body: HTML περιεχόμενο email (προαιρετικό).
    """
    tc = ctx.context
    recipients = [e.strip() for e in to_emails.split(",") if e.strip()]
    if not recipients:
        return json.dumps({"error": "Δεν δόθηκαν παραλήπτες."}, ensure_ascii=False)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM report_history WHERE id=? AND company_id=?",
            (report_id, tc.company_id),
        ).fetchone()
    if not row:
        return json.dumps({"error": f"Αναφορά #{report_id} δεν βρέθηκε."}, ensure_ascii=False)

    from pathlib import Path
    file_path = Path(row["file_path"])
    if not file_path.exists():
        return json.dumps({"error": "Το αρχείο αναφοράς δεν βρέθηκε στον δίσκο."}, ensure_ascii=False)

    if not subject:
        subject = f"Αναφορά {row['preset']} - {tc.company_name}"
    if not body:
        body = f"<p>Επισυνάπτεται η αναφορά <b>{file_path.name}</b> για την εταιρεία {tc.company_name}.</p>"

    from email_sender import send_email
    result = send_email(recipients, subject, body, attachments=[str(file_path)])
    return json.dumps(result, ensure_ascii=False)


# ── Agent Factory ──

def create_agent(context: TimologiaContext) -> Agent:
    """Create a Timologia AI agent for the given company context."""
    now = _greek_now()
    today_str = now.strftime("%d/%m/%Y")
    day_names = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
    day_name = day_names[now.weekday()]
    time_str = now.strftime("%H:%M")

    instructions = f"""Είσαι ο βοηθός παραστατικών για την εταιρεία "{context.company_name}" (ΑΦΜ: {context.afm}).
Περιβάλλον AADE: {context.aade_env}.
Σημερινή ημερομηνία: {day_name} {today_str}, ώρα {time_str} (Ελλάδα).

ΚΑΝΟΝΕΣ:
1. Απαντάς ΠΑΝΤΑ στα Ελληνικά.
2. Για κάθε ενέργεια εγγραφής (αποστολή παραστατικού, ακύρωση, αλλαγή ρυθμίσεων) ΠΑΝΤΑ κάνεις πρώτα dry_run=True.
3. ΠΟΤΕ μην στέλνεις παραστατικό ή ακυρώνεις χωρίς dry_run πρώτα — ο χρήστης πρέπει να επιβεβαιώσει.
4. Όταν ο χρήστης ρωτάει για παραστατικά/έσοδα/έξοδα, ΠΑΝΤΑ χρησιμοποίησε get_invoices (τοπικός cache — πλήρη δεδομένα, ίδια με το web app). Για έσοδα: direction='sent'. Για έξοδα: direction='received'. Για όλα: direction='all'. Τα income_summary/expenses_summary επιστρέφουν ΜΟΝΟ χαρακτηρισμένα παραστατικά (classified) από AADE — χρησιμοποίησέ τα ΜΟΝΟ αν ο χρήστης ζητήσει ρητά "χαρακτηρισμένα" έσοδα/έξοδα.
5. Για αναφορές/reports χρησιμοποίησε generate_report_tool.
6. Μην εμφανίζεις ποτέ credentials (aade_user_id, subscription_key).
7. Τα ποσά εμφανίζονται σε EUR με 2 δεκαδικά.
8. Ο χρήστης έχει ρόλο "{context.user_role}" σε αυτή την εταιρεία.
9. Όταν ένα παραστατικό εμφανίζει μόνο ΑΦΜ αντισυμβαλλομένου χωρίς επωνυμία, ΠΑΝΤΑ χρησιμοποίησε lookup_afm για να βρεις την επωνυμία.
10. Στα αποτελέσματα εμφάνιζε ΠΑΝΤΑ την επωνυμία μαζί με το ΑΦΜ (π.χ. "ΕΤΑΙΡΕΙΑ ΑΕ (ΑΦΜ: 094388099)").
11. Όταν δημιουργείται αναφορά Excel, ΜΗΝ εμφανίσεις file path, link ή URL. Απλά ανέφερε ότι η αναφορά δημιουργήθηκε — το κουμπί λήψης εμφανίζεται αυτόματα στο chat.
12. Για αποστολή αναφοράς με email, χρησιμοποίησε email_report με το report_id από generate_report_tool. Ρώτα τον χρήστη για τη διεύθυνση email αν δεν τη δώσει.
13. ΜΟΡΦΟΠΟΙΗΣΗ: Γράψε απλό κείμενο χωρίς Markdown σύμβολα. ΠΟΤΕ μην χρησιμοποιείς **, ##, ###, ---, ``` ή άλλα σύμβολα μορφοποίησης. Για λίστες χρησιμοποίησε απλές παύλες (-). Για πίνακες χρησιμοποίησε στοίχιση με κενά ή απλή λίστα.
14. ΗΜΕΡΟΜΗΝΙΕΣ: Πέρασε ημερομηνίες στα tools ΠΑΝΤΑ σε μορφή YYYY-MM-DD (π.χ. '2026-02-01'). Υπολόγισε σχετικές ημερομηνίες μόνος σου: "περασμένο μήνα" = πρώτη και τελευταία μέρα του προηγούμενου μήνα, "αυτή τη βδομάδα" = Δευτέρα έως σήμερα, κλπ. ΜΗΝ ρωτάς τον χρήστη για ημερομηνίες αν μπορείς να τις υπολογίσεις.
"""

    return Agent(
        name="Timologia Assistant",
        model="gpt-4.1",
        instructions=instructions,
        tools=[
            get_invoices,
            income_summary,
            expenses_summary,
            send_invoice,
            cancel_invoice,
            generate_report_tool,
            list_companies,
            get_company_settings,
            update_company_settings,
            lookup_afm,
            email_report,
        ],
    )
