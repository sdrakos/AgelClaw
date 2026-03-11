#!/usr/bin/env python3
"""
Standalone CLI wrapper for daily_accounting_report.

Bypasses MCP stdio pipe (hangs on Windows) by running as a regular script.
Usage:
    python run_report.py --afm 101660691 --date-from 2026-01-01 --date-to 2026-03-07 --env prod
    python run_report.py --afm 101660691  # defaults: today, dev, send email
    python run_report.py --afm 101660691 --no-email  # skip email
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add this directory to path so we can import server and accounting_xlsx
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server import (
    CredentialStore,
    MyDataClient,
    _find_send_email_script,
    _afm_cache,
    _soap_lookup_afm,
    _validate_afm,
    ENVIRONMENTS,
    PROJECT_DIR,
)
from accounting_xlsx import generate_xlsx
from datetime import date


def _enrich_supplier_names(invoices: list) -> int:
    """Add issuer_name to expense invoices by looking up issuer VAT numbers.

    Uses AFM cache (90 days) first, then AADE SOAP for uncached VATs.
    Returns the number of successfully resolved names.
    """
    # Collect unique VAT numbers
    vat_set = set()
    for inv in invoices:
        vat = inv.get("issuer_vat", "").strip()
        if vat and len(vat) == 9:
            vat_set.add(vat)

    if not vat_set:
        return 0

    # Batch lookup: cache first, then SOAP for misses
    name_map = {}  # vat -> name
    for vat in vat_set:
        # Try cache first
        cached = _afm_cache.get(vat)
        if cached:
            name_map[vat] = cached.get("name", "")
            continue
        # Try SOAP lookup
        if _validate_afm(vat):
            try:
                info = _soap_lookup_afm(vat)
                _afm_cache.put(vat, info)
                name_map[vat] = info.get("name", "")
            except Exception:
                name_map[vat] = ""  # Failed lookup, leave empty
        else:
            name_map[vat] = ""

    # Enrich invoices
    resolved = 0
    for inv in invoices:
        vat = inv.get("issuer_vat", "").strip()
        name = name_map.get(vat, "")
        if name:
            inv["issuer_name"] = name
            resolved += 1

    return resolved


async def run_report(afm: str, date_from: str, date_to: str, env: str,
                     send_email: bool, email_to: str, force: bool = False,
                     from_email: str = "") -> dict:
    """Same logic as _daily_accounting_report in server.py."""
    import os

    # Override environment if specified
    if env == "prod":
        os.environ["MYDATA_ENV"] = "prod"

    cred_store = CredentialStore()

    if not afm:
        afm = cred_store.get_default() or os.environ.get("ISSUER_VAT", "")
    if not afm:
        return {"error": "No AFM specified. Use --afm or set a default."}

    today = date.today().isoformat()

    # Fetch invoices from AADE
    client = MyDataClient.from_db_or_env(afm)
    try:
        all_sent = await client.get_sent_invoices(0, date_from, date_to)
        all_received = await client.get_received_invoices(0, date_from, date_to)
    finally:
        await client.close()

    # Filter out raw/error responses
    if all_sent and isinstance(all_sent[0], dict) and "raw" in all_sent[0]:
        all_sent = []
    if all_received and isinstance(all_received[0], dict) and "raw" in all_received[0]:
        all_received = []

    # Deduplicate: skip already processed (unless --force)
    if force:
        new_sent = [inv for inv in all_sent if inv.get("mark")]
        new_received = [inv for inv in all_received if inv.get("mark")]
        skipped_sent = skipped_received = 0
    else:
        new_sent = [
            inv for inv in all_sent
            if inv.get("mark") and not cred_store.is_invoice_processed(str(inv["mark"]), afm, "sent")
        ]
        new_received = [
            inv for inv in all_received
            if inv.get("mark") and not cred_store.is_invoice_processed(str(inv["mark"]), afm, "received")
        ]
        skipped_sent = len(all_sent) - len(new_sent)
        skipped_received = len(all_received) - len(new_received)

    result = {
        "afm": afm,
        "period": f"{date_from} -- {date_to}",
        "new_income": len(new_sent),
        "new_expenses": len(new_received),
        "skipped_dupes": skipped_sent + skipped_received,
        "force": force,
    }

    if not new_sent and not new_received:
        result["message"] = "No invoices found for this period."
        return result

    # Enrich expenses with supplier names (from cache/AADE SOAP)
    try:
        resolved_names = _enrich_supplier_names(new_received)
        result["supplier_names_resolved"] = resolved_names
    except Exception as e:
        result["supplier_names_error"] = str(e)

    # Generate Excel
    reports_dir = PROJECT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"accounting_{afm}_{date_from}_{date_to}.xlsx"
    xlsx_path = reports_dir / filename

    generate_xlsx(xlsx_path, new_sent, new_received, afm, date_from, date_to)
    result["xlsx_path"] = str(xlsx_path)

    # Mark as processed
    cred_store.mark_invoices_processed(new_sent, afm, "sent", today)
    cred_store.mark_invoices_processed(new_received, afm, "received", today)

    # Compute totals
    income_net = sum(float(inv.get("totalNetValue", 0)) for inv in new_sent)
    income_vat = sum(float(inv.get("totalVatAmount", 0)) for inv in new_sent)
    expense_net = sum(float(inv.get("totalNetValue", 0)) for inv in new_received)
    expense_vat = sum(float(inv.get("totalVatAmount", 0)) for inv in new_received)

    result["totals"] = {
        "income_net": round(income_net, 2),
        "income_vat": round(income_vat, 2),
        "expense_net": round(expense_net, 2),
        "expense_vat": round(expense_vat, 2),
        "profit": round(income_net - expense_net, 2),
    }

    # Email
    if send_email:
        # Resolve sender email: CLI arg → per-AFM setting → default (config.yaml)
        effective_from = from_email or cred_store.get_accounting_setting(afm, "email_sender", "")
        recipients = email_to or cred_store.get_accounting_setting(afm, "email_recipients", "")
        if not recipients:
            result["email_result"] = "No recipients configured. Use configure_accounting."
        else:
            script = _find_send_email_script()
            if not script:
                result["email_result"] = "send_email.py script not found."
            else:
                import subprocess
                subject = f"Accounting Report AADE - AFM {afm} ({date_from})"
                body = (
                    f"<h2>AADE Accounting Report</h2>"
                    f"<p><b>AFM:</b> {afm} | <b>Period:</b> {date_from} -- {date_to}</p>"
                    f"<table border='1' cellpadding='5' cellspacing='0'>"
                    f"<tr><td><b>New Income</b></td><td>{len(new_sent)} ({income_net:,.2f} EUR)</td></tr>"
                    f"<tr><td><b>New Expenses</b></td><td>{len(new_received)} ({expense_net:,.2f} EUR)</td></tr>"
                    f"<tr><td><b>Income VAT</b></td><td>{income_vat:,.2f} EUR</td></tr>"
                    f"<tr><td><b>Expense VAT</b></td><td>{expense_vat:,.2f} EUR</td></tr>"
                    f"<tr><td><b>Profit/Loss</b></td><td>{income_net - expense_net:,.2f} EUR</td></tr>"
                    f"</table>"
                    f"<p>See attached Excel for details.</p>"
                )
                try:
                    cmd = [sys.executable, str(script),
                         "--to", recipients,
                         "--subject", subject,
                         "--body", body,
                         "--attachment", str(xlsx_path)]
                    # Override sender email (e.g. info@timologia.me)
                    if effective_from:
                        cmd.extend(["--from", effective_from])
                    proc = subprocess.run(
                        cmd,
                        capture_output=True, text=True, timeout=60,
                    )
                    if proc.returncode == 0:
                        result["email_result"] = f"Email sent to {recipients}"
                    else:
                        result["email_result"] = f"Email error: {proc.stderr[:500]}"
                except subprocess.TimeoutExpired:
                    result["email_result"] = "Email timeout (60s)"
                except Exception as e:
                    result["email_result"] = f"Email exception: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(description="AADE Daily Accounting Report")
    parser.add_argument("--afm", default="", help="Issuer AFM (VAT number)")
    parser.add_argument("--date-from", default=date.today().isoformat(), help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    parser.add_argument("--env", default="dev", choices=["dev", "prod"], help="AADE environment")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email")
    parser.add_argument("--email-to", default="", help="Override email recipients")
    parser.add_argument("--force", action="store_true", help="Skip dedup, include ALL invoices")
    parser.add_argument("--from-email", default="", help="Override sender email (e.g. info@timologia.me)")
    args = parser.parse_args()

    # Dynamic date aliases
    if args.date_from == "month_start":
        args.date_from = date.today().replace(day=1).isoformat()
    if args.date_to == "month_start":
        args.date_to = date.today().replace(day=1).isoformat()

    result = asyncio.run(run_report(
        afm=args.afm,
        date_from=args.date_from,
        date_to=args.date_to,
        env=args.env,
        send_email=not args.no_email,
        email_to=args.email_to,
        force=args.force,
        from_email=args.from_email,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
