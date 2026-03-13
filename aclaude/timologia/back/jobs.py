"""Scheduled report jobs — cron parsing, due checks, and execution."""
import asyncio
import json
import logging
import re
from datetime import datetime, date
from pathlib import Path

from db import get_db
from config import FERNET, REPORTS_DIR

logger = logging.getLogger(__name__)


# ── Cron parsing ──

def _parse_cron(cron: str) -> dict:
    """Parse extended cron syntax into a schedule descriptor.

    Supported formats:
        daily_HH:MM        — every day at HH:MM
        weekly_D_HH:MM     — every week on day D (0=Mon) at HH:MM
        monthly_D_HH:MM    — every month on day D at HH:MM
        every_Xm            — every X minutes
        every_Xh            — every X hours
    """
    cron = cron.strip()

    m = re.match(r"^daily_(\d{2}):(\d{2})$", cron)
    if m:
        return {"type": "daily", "hour": int(m.group(1)), "minute": int(m.group(2))}

    m = re.match(r"^weekly_(\d)_(\d{2}):(\d{2})$", cron)
    if m:
        return {"type": "weekly", "weekday": int(m.group(1)),
                "hour": int(m.group(2)), "minute": int(m.group(3))}

    m = re.match(r"^monthly_(\d{1,2})_(\d{2}):(\d{2})$", cron)
    if m:
        return {"type": "monthly", "day": int(m.group(1)),
                "hour": int(m.group(2)), "minute": int(m.group(3))}

    m = re.match(r"^every_(\d+)m$", cron)
    if m:
        return {"type": "interval_m", "minutes": int(m.group(1))}

    m = re.match(r"^every_(\d+)h$", cron)
    if m:
        return {"type": "interval_h", "hours": int(m.group(1))}

    raise ValueError(f"Unknown cron format: {cron}")


def is_due(schedule: dict) -> bool:
    """Check if a report_schedule row should run now.

    Args:
        schedule: sqlite Row dict with keys: cron, last_run_at, enabled
    """
    if not schedule["enabled"]:
        return False

    try:
        parsed = _parse_cron(schedule["cron"])
    except ValueError:
        logger.warning("Invalid cron for schedule %s: %s", schedule["id"], schedule["cron"])
        return False

    now = datetime.now()
    last_run = None
    if schedule["last_run_at"]:
        try:
            last_run = datetime.fromisoformat(schedule["last_run_at"])
        except (ValueError, TypeError):
            pass

    def _time_passed(hour, minute):
        """Check if we're at or past the target time today."""
        return (now.hour, now.minute) >= (hour, minute)

    if parsed["type"] == "daily":
        if not _time_passed(parsed["hour"], parsed["minute"]):
            return False
        if last_run and last_run.date() == now.date():
            return False
        return True

    elif parsed["type"] == "weekly":
        if now.weekday() != parsed["weekday"]:
            return False
        if not _time_passed(parsed["hour"], parsed["minute"]):
            return False
        if last_run and (now - last_run).total_seconds() < 86400:
            return False
        return True

    elif parsed["type"] == "monthly":
        if now.day != parsed["day"]:
            return False
        if not _time_passed(parsed["hour"], parsed["minute"]):
            return False
        if last_run and last_run.month == now.month and last_run.year == now.year:
            return False
        return True

    elif parsed["type"] == "interval_m":
        if not last_run:
            return True
        elapsed = (now - last_run).total_seconds()
        return elapsed >= parsed["minutes"] * 60

    elif parsed["type"] == "interval_h":
        if not last_run:
            return True
        elapsed = (now - last_run).total_seconds()
        return elapsed >= parsed["hours"] * 3600

    return False


# ── Scheduled report execution ──

async def run_scheduled_report(schedule_id: int):
    """Fetch data, generate xlsx, send email, update last_run_at."""
    with get_db() as conn:
        sched = conn.execute("SELECT * FROM report_schedules WHERE id=?", (schedule_id,)).fetchone()
    if not sched:
        logger.error("Schedule %d not found", schedule_id)
        return

    sched = dict(sched)
    company_id = sched["company_id"]
    preset = sched.get("preset") or "daily_summary"
    params = json.loads(sched.get("params") or "{}")
    recipients = [r.strip() for r in sched["recipients"].split(",") if r.strip()]

    if not recipients:
        logger.warning("Schedule %d has no recipients", schedule_id)
        return

    # Load company
    with get_db() as conn:
        company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    if not company:
        logger.error("Company %d not found for schedule %d", company_id, schedule_id)
        return

    company = dict(company)

    try:
        # Generate report using reports module
        from reports import generate_report as do_generate
        result = await do_generate(company_id, sched["created_by"], preset, params)

        file_path = result.get("file_path")

        # Send email
        from email_sender import send_email
        subject = f"Αναφορά {company['name']} — {datetime.now().strftime('%d/%m/%Y')}"
        body = (
            f"<p>Αυτόματη αναφορά: <strong>{preset}</strong></p>"
            f"<p>Εταιρεία: {company['name']} (ΑΦΜ: {company['afm']})</p>"
            f"<p>Περίοδος: {result.get('date_from', '')} — {result.get('date_to', '')}</p>"
            f"<p>Έσοδα: {result.get('income_count', 0)} | Έξοδα: {result.get('expense_count', 0)}</p>"
        )
        attachments = [file_path] if file_path else []
        email_result = send_email(recipients, subject, body, attachments=attachments)

        if not email_result.get("success"):
            logger.error("Email send failed for schedule %d: %s", schedule_id, email_result.get("error"))

        # Update last_run_at
        with get_db() as conn:
            conn.execute(
                "UPDATE report_schedules SET last_run_at=? WHERE id=?",
                (datetime.now().isoformat(), schedule_id),
            )

        # Update report_history with schedule_id
        if result.get("id"):
            with get_db() as conn:
                conn.execute(
                    "UPDATE report_history SET schedule_id=? WHERE id=?",
                    (schedule_id, result["id"]),
                )

        logger.info("Schedule %d executed successfully", schedule_id)

    except Exception as e:
        logger.error("Schedule %d failed: %s", schedule_id, e, exc_info=True)
        # Log failure in report_history
        with get_db() as conn:
            conn.execute(
                """INSERT INTO report_history (company_id, user_id, preset, params, status, error, schedule_id)
                   VALUES (?, ?, ?, ?, 'error', ?, ?)""",
                (company_id, sched["created_by"], preset,
                 json.dumps(params, ensure_ascii=False), str(e)[:1000], schedule_id),
            )
            conn.execute(
                "UPDATE report_schedules SET last_run_at=? WHERE id=?",
                (datetime.now().isoformat(), schedule_id),
            )


def check_and_enqueue_schedules(queue=None):
    """Check all enabled schedules, enqueue due ones.

    Args:
        queue: optional RQ queue. If None, runs synchronously via asyncio.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM report_schedules WHERE enabled=1"
        ).fetchall()

    due_count = 0
    for row in rows:
        sched = dict(row)
        if is_due(sched):
            due_count += 1
            if queue:
                queue.enqueue(run_scheduled_report_sync, sched["id"])
            else:
                # Run directly via asyncio
                try:
                    asyncio.get_event_loop().run_until_complete(
                        run_scheduled_report(sched["id"])
                    )
                except RuntimeError:
                    # No running loop — create one
                    asyncio.run(run_scheduled_report(sched["id"]))

    if due_count:
        logger.info("Enqueued %d due schedules", due_count)
    return due_count


def run_scheduled_report_sync(schedule_id: int):
    """Synchronous wrapper for RQ worker."""
    asyncio.run(run_scheduled_report(schedule_id))


async def check_and_enqueue_schedules_async():
    """Async version — runs due schedules directly (no Redis/RQ needed)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM report_schedules WHERE enabled=1"
        ).fetchall()

    due_count = 0
    for row in rows:
        sched = dict(row)
        if is_due(sched):
            due_count += 1
            try:
                await run_scheduled_report(sched["id"])
            except Exception as e:
                logger.error("Schedule %d failed: %s", sched["id"], e, exc_info=True)

    return due_count
