"""OpenAI Agents SDK — Timologia assistant with AADE tools."""
import json
from dataclasses import dataclass
from datetime import datetime
from agents import Agent, RunContext, function_tool
from db import get_db


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


# ── Tool 1: Get Invoices ──

@function_tool
async def get_invoices(
    ctx: RunContext[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
    direction: str = "sent",
) -> str:
    """Ανάκτηση τιμολογίων από AADE. direction: 'sent' ή 'received'."""
    tc = ctx.context
    client = _get_client(tc)
    try:
        if direction == "received":
            invoices = await client.get_received_invoices(
                date_from=date_from or None, date_to=date_to or None,
            )
        else:
            invoices = await client.get_sent_invoices(
                date_from=date_from or None, date_to=date_to or None,
            )
    finally:
        await client.close()

    # Limit to 50 results
    invoices = invoices[:50]
    return json.dumps(invoices, ensure_ascii=False)


# ── Tool 2: Income Summary ──

@function_tool
async def income_summary(
    ctx: RunContext[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Σύνοψη εσόδων για περίοδο. Επιστρέφει XML από AADE."""
    tc = ctx.context
    if not date_from:
        date_from = datetime.now().strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    client = _get_client(tc)
    try:
        data = await client.get_income(date_from, date_to)
    finally:
        await client.close()
    return data.decode("utf-8", errors="replace")[:4000]


# ── Tool 3: Expenses Summary ──

@function_tool
async def expenses_summary(
    ctx: RunContext[TimologiaContext],
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Σύνοψη εξόδων για περίοδο. Επιστρέφει XML από AADE."""
    tc = ctx.context
    if not date_from:
        date_from = datetime.now().strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    client = _get_client(tc)
    try:
        data = await client.get_expenses(date_from, date_to)
    finally:
        await client.close()
    return data.decode("utf-8", errors="replace")[:4000]


# ── Tool 4: Send Invoice ──

@function_tool
async def send_invoice(
    ctx: RunContext[TimologiaContext],
    counterpart_vat: str,
    invoice_type: str,
    series: str,
    number: int,
    items: list[dict],
    dry_run: bool = True,
) -> str:
    """Αποστολή τιμολογίου στο AADE.
    items: [{"net_value": 100, "vat_category": 1, ...}]
    dry_run=True: επιστρέφει preview χωρίς αποστολή.
    dry_run=False: αποστέλλει πραγματικά στο AADE.
    """
    tc = ctx.context

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
            "message": "Προεπισκόπηση τιμολογίου. Πατήστε 'Επιβεβαίωση' για αποστολή.",
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
    ctx: RunContext[TimologiaContext],
    mark: str,
    dry_run: bool = True,
) -> str:
    """Ακύρωση τιμολογίου βάσει MARK.
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
            "message": f"Θα ακυρωθεί το τιμολόγιο με MARK {mark}. Πατήστε 'Επιβεβαίωση' για ακύρωση.",
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
    ctx: RunContext[TimologiaContext],
    preset: str = "daily_summary",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Δημιουργία λογιστικής αναφοράς (Excel).
    presets: daily_summary, monthly_vat, quarterly_income, annual_overview, custom.
    """
    tc = ctx.context
    from reports import generate_report

    params = {}
    if preset == "custom":
        params = {"date_from": date_from, "date_to": date_to}

    result = await generate_report(tc.company_id, tc.user_id, preset, params)
    return json.dumps(result, ensure_ascii=False, default=str)


# ── Tool 7: List Companies ──

@function_tool
async def list_companies(ctx: RunContext[TimologiaContext]) -> str:
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
async def get_company_settings(ctx: RunContext[TimologiaContext]) -> str:
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
    ctx: RunContext[TimologiaContext],
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


# ── Agent Factory ──

def create_agent(context: TimologiaContext) -> Agent:
    """Create a Timologia AI agent for the given company context."""
    instructions = f"""Είσαι ο βοηθός τιμολόγησης για την εταιρεία "{context.company_name}" (ΑΦΜ: {context.afm}).
Περιβάλλον AADE: {context.aade_env}.

ΚΑΝΟΝΕΣ:
1. Απαντάς ΠΑΝΤΑ στα Ελληνικά.
2. Για κάθε ενέργεια εγγραφής (αποστολή τιμολογίου, ακύρωση, αλλαγή ρυθμίσεων) ΠΑΝΤΑ κάνεις πρώτα dry_run=True.
3. ΠΟΤΕ μην στέλνεις τιμολόγιο ή ακυρώνεις χωρίς dry_run πρώτα — ο χρήστης πρέπει να επιβεβαιώσει.
4. Όταν ο χρήστης ρωτάει για τιμολόγια, χρησιμοποίησε get_invoices.
5. Για αναφορές/reports χρησιμοποίησε generate_report_tool.
6. Μην εμφανίζεις ποτέ credentials (aade_user_id, subscription_key).
7. Τα ποσά εμφανίζονται σε EUR με 2 δεκαδικά.
8. Ο χρήστης έχει ρόλο "{context.user_role}" σε αυτή την εταιρεία.
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
        ],
    )
