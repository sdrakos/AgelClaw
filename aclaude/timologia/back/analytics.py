from fastapi import APIRouter, Depends, Query
from db import get_db
from auth import get_current_user, get_member_role
from fastapi import HTTPException
from datetime import datetime, date, timedelta
from collections import defaultdict
import calendar
import json

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

GREEK_MONTHS = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μάι", "Ιουν",
                "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
GREEK_WEEKDAYS = ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]


def _vat_bucket(net, vat):
    if net is None or net == 0 or vat is None:
        return "0%"
    ratio = vat / net
    if ratio > 0.20:
        return "24%"
    elif ratio > 0.10:
        return "13%"
    elif ratio > 0.03:
        return "6%"
    return "0%"


@router.get("")
async def get_analytics(
    company_id: int = Query(...),
    user=Depends(get_current_user),
):
    role = get_member_role(user["id"], company_id)
    if not role and user.get("role") != "admin":
        raise HTTPException(403, "No access to this company")

    today = date.today()

    # ── Period boundaries ──
    cur_month_start = today.replace(day=1)
    prev_month_last = cur_month_start - timedelta(days=1)
    prev_month_start = prev_month_last.replace(day=1)

    # Current week (Monday-based)
    cur_week_start = today - timedelta(days=today.weekday())
    prev_week_start = cur_week_start - timedelta(days=7)
    prev_week_end = cur_week_start - timedelta(days=1)

    # Year-over-year: same month last year
    yoy_prev_start = cur_month_start.replace(year=today.year - 1)
    yoy_prev_end_day = calendar.monthrange(today.year - 1, today.month)[1]
    yoy_prev_end = date(today.year - 1, today.month, yoy_prev_end_day)

    # ── Fetch all invoices for this company at once ──
    with get_db() as conn:
        rows = conn.execute(
            """SELECT mark, invoice_type, issue_date, counterpart_afm,
                      counterpart_name, net_amount, vat_amount, total_amount,
                      direction, raw_json
               FROM invoices WHERE company_id = ?""",
            (company_id,),
        ).fetchall()

    # ── Accumulators ──
    def empty_period():
        return {"net": 0.0, "vat": 0.0, "gross": 0.0, "count": 0}

    cur_month_sent = empty_period()
    prev_month_sent = empty_period()
    cur_week_sent = empty_period()
    prev_week_sent = empty_period()
    yoy_current = {"net": 0.0, "gross": 0.0, "count": 0}
    yoy_previous = {"net": 0.0, "gross": 0.0, "count": 0}

    daily_income = defaultdict(float)
    daily_expense = defaultdict(float)

    vat_buckets = defaultdict(lambda: {"net": 0.0, "vat": 0.0, "count": 0})

    supplier_agg = defaultdict(lambda: {"name": "", "gross": 0.0, "count": 0})
    customer_agg = defaultdict(lambda: {"name": "", "gross": 0.0, "count": 0})

    monthly_income = defaultdict(float)
    monthly_expense = defaultdict(float)
    monthly_sent_totals = defaultdict(lambda: {"total": 0.0, "count": 0})

    seasonality_agg = defaultdict(lambda: {"total": 0.0, "years": set()})
    weekday_agg = defaultdict(lambda: {"total": 0.0, "count": 0})

    forecast_actual = 0.0

    thirty_days_ago = today - timedelta(days=29)

    for row in rows:
        issue_str = row["issue_date"]
        if not issue_str:
            continue
        try:
            issue = datetime.strptime(issue_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        net = row["net_amount"] or 0.0
        vat = row["vat_amount"] or 0.0
        gross = row["total_amount"] or 0.0
        direction = row["direction"]
        afm = row["counterpart_afm"] or ""
        name = row["counterpart_name"] or afm

        # ── Period comparison (sent = income only) ──
        if direction == "sent":
            if cur_month_start <= issue <= today:
                cur_month_sent["net"] += net
                cur_month_sent["vat"] += vat
                cur_month_sent["gross"] += gross
                cur_month_sent["count"] += 1
                forecast_actual += gross

            if prev_month_start <= issue <= prev_month_last:
                prev_month_sent["net"] += net
                prev_month_sent["vat"] += vat
                prev_month_sent["gross"] += gross
                prev_month_sent["count"] += 1

            if cur_week_start <= issue <= today:
                cur_week_sent["net"] += net
                cur_week_sent["vat"] += vat
                cur_week_sent["gross"] += gross
                cur_week_sent["count"] += 1

            if prev_week_start <= issue <= prev_week_end:
                prev_week_sent["net"] += net
                prev_week_sent["vat"] += vat
                prev_week_sent["gross"] += gross
                prev_week_sent["count"] += 1

            # YoY
            if cur_month_start <= issue <= today:
                yoy_current["net"] += net
                yoy_current["gross"] += gross
                yoy_current["count"] += 1
            if yoy_prev_start <= issue <= yoy_prev_end:
                yoy_previous["net"] += net
                yoy_previous["gross"] += gross
                yoy_previous["count"] += 1

        # ── Daily revenue (last 30 days) ──
        if thirty_days_ago <= issue <= today:
            if direction == "sent":
                daily_income[issue.isoformat()] += gross
            else:
                daily_expense[issue.isoformat()] += gross

        # ── VAT breakdown (all invoices) ──
        bucket = _vat_bucket(net, vat)
        vat_buckets[bucket]["net"] += net
        vat_buckets[bucket]["vat"] += vat
        vat_buckets[bucket]["count"] += 1

        # ── Top suppliers / customers ──
        if afm:
            if direction == "received":
                supplier_agg[afm]["name"] = name
                supplier_agg[afm]["gross"] += gross
                supplier_agg[afm]["count"] += 1
            else:
                customer_agg[afm]["name"] = name
                customer_agg[afm]["gross"] += gross
                customer_agg[afm]["count"] += 1

        # ── Monthly evolution (last 12 months) ──
        month_key = issue.strftime("%Y-%m")
        if direction == "sent":
            monthly_income[month_key] += gross
            monthly_sent_totals[month_key]["total"] += gross
            monthly_sent_totals[month_key]["count"] += 1
        else:
            monthly_expense[month_key] += gross

        # ── Seasonality (sent only, all years) ──
        if direction == "sent":
            seasonality_agg[issue.month]["total"] += gross
            seasonality_agg[issue.month]["years"].add(issue.year)

        # ── Weekday revenue (sent only) ──
        if direction == "sent":
            wd = issue.weekday()
            weekday_agg[wd]["total"] += gross
            weekday_agg[wd]["count"] += 1

    # ── Build daily_revenue (last 30 days, fill gaps with 0) ──
    daily_revenue = []
    for i in range(30):
        d = (thirty_days_ago + timedelta(days=i)).isoformat()
        daily_revenue.append({
            "date": d,
            "income": round(daily_income.get(d, 0.0), 2),
            "expenses": round(daily_expense.get(d, 0.0), 2),
        })

    # ── VAT breakdown list ──
    vat_breakdown = []
    for rate in ["24%", "13%", "6%", "0%"]:
        b = vat_buckets.get(rate)
        if b and b["count"] > 0:
            vat_breakdown.append({
                "rate": rate,
                "net": round(b["net"], 2),
                "vat": round(b["vat"], 2),
                "count": b["count"],
            })

    # ── Top suppliers / customers ──
    top_suppliers = sorted(
        [{"afm": k, "name": v["name"], "gross": round(v["gross"], 2), "count": v["count"]}
         for k, v in supplier_agg.items()],
        key=lambda x: x["gross"], reverse=True,
    )[:10]

    top_customers = sorted(
        [{"afm": k, "name": v["name"], "gross": round(v["gross"], 2), "count": v["count"]}
         for k, v in customer_agg.items()],
        key=lambda x: x["gross"], reverse=True,
    )[:10]

    # ── Avg invoice by month (last 12 months, sent) ──
    avg_invoice_by_month = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        mk = f"{y}-{m:02d}"
        entry = monthly_sent_totals.get(mk)
        if entry and entry["count"] > 0:
            avg_invoice_by_month.append({
                "month": mk,
                "avg": round(entry["total"] / entry["count"], 2),
                "count": entry["count"],
            })
        else:
            avg_invoice_by_month.append({"month": mk, "avg": 0.0, "count": 0})

    # ── Month forecast (sent only) ──
    days_elapsed = today.day
    days_total = calendar.monthrange(today.year, today.month)[1]
    projected = (forecast_actual / days_elapsed * days_total) if days_elapsed > 0 else 0.0
    month_forecast = {
        "actual": round(forecast_actual, 2),
        "days_elapsed": days_elapsed,
        "days_total": days_total,
        "projected": round(projected, 2),
    }

    # ── Seasonality ──
    seasonality = []
    for m in range(1, 13):
        entry = seasonality_agg.get(m)
        if entry and len(entry["years"]) > 0:
            avg_rev = entry["total"] / len(entry["years"])
        else:
            avg_rev = 0.0
        seasonality.append({
            "month": m,
            "label": GREEK_MONTHS[m - 1],
            "avg_revenue": round(avg_rev, 2),
        })

    # ── Weekday revenue ──
    weekday_revenue = []
    for d in range(7):
        entry = weekday_agg.get(d)
        if entry and entry["count"] > 0:
            avg_rev = entry["total"] / entry["count"]
        else:
            avg_rev = 0.0
        weekday_revenue.append({
            "day": d,
            "label": GREEK_WEEKDAYS[d],
            "avg_revenue": round(avg_rev, 2),
        })

    # ── Monthly evolution (last 12 months) ──
    monthly_evolution = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        mk = f"{y}-{m:02d}"
        monthly_evolution.append({
            "month": mk,
            "income": round(monthly_income.get(mk, 0.0), 2),
            "expenses": round(monthly_expense.get(mk, 0.0), 2),
        })

    # ── Round period comparison values ──
    def _round_period(p):
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in p.items()}

    return {
        "period_comparison": {
            "current_month": _round_period(cur_month_sent),
            "prev_month": _round_period(prev_month_sent),
            "current_week": _round_period(cur_week_sent),
            "prev_week": _round_period(prev_week_sent),
            "yoy_current": {k: round(v, 2) if isinstance(v, float) else v for k, v in yoy_current.items()},
            "yoy_previous": {k: round(v, 2) if isinstance(v, float) else v for k, v in yoy_previous.items()},
        },
        "daily_revenue": daily_revenue,
        "vat_breakdown": vat_breakdown,
        "top_suppliers": top_suppliers,
        "top_customers": top_customers,
        "avg_invoice_by_month": avg_invoice_by_month,
        "month_forecast": month_forecast,
        "seasonality": seasonality,
        "weekday_revenue": weekday_revenue,
        "monthly_evolution": monthly_evolution,
    }
