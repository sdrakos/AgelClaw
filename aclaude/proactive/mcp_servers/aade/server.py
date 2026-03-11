"""
AADE myDATA MCP Server
======================
Invoice management, multi-AFM credential storage, and daily accounting
reports via the Greek tax authority REST API.

Tools: send_invoice, get_invoices, cancel_invoice, income_summary,
       expenses_summary, generate_xml, add_credentials, list_credentials,
       remove_credentials, set_default_afm, daily_accounting_report,
       configure_accounting, accounting_status
"""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import re

import httpx
from lxml import etree
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

try:
    from zeep import Client as SoapClient
    from zeep.transports import Transport
    from zeep.wsse.username import UsernameToken
    HAS_ZEEP = True
except ImportError:
    HAS_ZEEP = False


# ── .env loading & project dir (search upward) ──

def _find_project_dir() -> Path:
    """Search parent directories for the project dir (has config.yaml or .agelclaw marker).
    Falls back to ~/.agelclaw/ if not found."""
    env_home = os.environ.get("AGELCLAW_HOME")
    if env_home:
        return Path(env_home).resolve()
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "config.yaml").exists() or (d / ".agelclaw").exists():
            return d
        d = d.parent
    return Path.home() / ".agelclaw"


PROJECT_DIR = _find_project_dir()
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _find_env():
    """Search parent directories for .env file."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        for name in ("proactive/.env", ".env"):
            env_path = d / name
            if env_path.exists():
                return env_path
        d = d.parent
    return None


def _load_env():
    env_path = _find_env()
    if env_path:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


_load_env()


# ── AADE API Configuration ──

ENVIRONMENTS = {
    "dev": "https://mydataapidev.aade.gr",
    "prod": "https://mydatapi.aade.gr/myDATA",
}

NS_INV = "http://www.aade.gr/myDATA/invoice/v1.0"
# Dev API uses https:// namespace URIs for classification elements
NS_ICLS = "https://www.aade.gr/myDATA/incomeClassificaton/v1.0"
NS_ECLS = "https://www.aade.gr/myDATA/expensesClassificaton/v1.0"

NAMESPACES = {
    None: NS_INV,
    "icls": NS_ICLS,
    "ecls": NS_ECLS,
}

VAT_RATES = {
    1: Decimal("0.24"),
    2: Decimal("0.13"),
    3: Decimal("0.06"),
    4: Decimal("0.17"),
    5: Decimal("0.09"),
    6: Decimal("0.04"),
    7: Decimal("0"),
    8: Decimal("0"),
}

DEFAULT_DB_PATH = DATA_DIR / "mydata_credentials.db"
AFM_CACHE_DB = DATA_DIR / "afm_cache.db"
GSIS_WSDL = "https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2?WSDL"


# ── AFM Validation & Lookup ──

def _validate_afm(afm: str) -> bool:
    """Validate Greek AFM using the official check digit algorithm."""
    afm = afm.strip().replace("EL", "").replace("el", "")
    if not re.match(r'^\d{9}$', afm):
        return False
    digits = [int(d) for d in afm]
    total = sum(digits[i] * (2 ** (8 - i)) for i in range(8))
    return (total % 11) % 10 == digits[8]


class AFMCacheDB:
    """SQLite cache for AFM lookup results."""

    def __init__(self, db_path: Path = AFM_CACHE_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    afm TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    lookup_date TEXT NOT NULL
                )
            """)

    def get(self, afm: str, max_age_days: int = 90) -> Optional[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT data, lookup_date FROM businesses WHERE afm = ?", (afm,)
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        from datetime import timedelta
        lookup_dt = datetime.fromisoformat(row[1])
        if (datetime.now() - lookup_dt).days > max_age_days:
            return None
        return data

    def put(self, afm: str, data: dict):
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO businesses (afm, data, lookup_date) VALUES (?, ?, ?)",
                (afm, json.dumps(data, ensure_ascii=False), now)
            )

    def list_all(self) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT afm, json_extract(data, '$.name'), "
                "json_extract(data, '$.primary_kad'), lookup_date "
                "FROM businesses ORDER BY lookup_date DESC"
            ).fetchall()
        return [{"afm": r[0], "name": r[1], "primary_kad": r[2], "cached": r[3]} for r in rows]


def _soap_lookup_afm(afm: str) -> dict:
    """Call AADE RgWsPublic2 SOAP service to look up business info."""
    if not HAS_ZEEP:
        raise RuntimeError("zeep not installed: pip install zeep")

    username = os.environ.get("GSIS_AFM_USERNAME", "")
    password = os.environ.get("GSIS_AFM_PASSWORD", "")
    caller = os.environ.get("GSIS_CALLER_AFM", "")

    if not username or not password:
        raise ValueError("GSIS_AFM_USERNAME and GSIS_AFM_PASSWORD not set in .env")

    transport = Transport(timeout=30)
    wsse = UsernameToken(username, password)
    client = SoapClient(GSIS_WSDL, transport=transport, wsse=wsse)

    result = client.service.rgWsPublic2AfmMethod(
        INPUT_REC={"afm_called_by": caller, "afm_called_for": afm}
    )

    # Check for errors
    if result.error_rec and result.error_rec.error_code:
        raise RuntimeError(f"AADE error: {result.error_rec.error_code} - {result.error_rec.error_descr}")

    # Parse response
    basic = result.basic_rec if hasattr(result, "basic_rec") else result
    info = {
        "afm": afm,
        "name": getattr(basic, "onomasia", "") or "",
        "commercial_title": getattr(basic, "commer_title", "") or "",
        "doy_code": str(getattr(basic, "doy", "") or ""),
        "doy_description": getattr(basic, "doy_descr", "") or "",
        "legal_status": getattr(basic, "legal_status_descr", "") or "",
        "is_active": str(getattr(basic, "deactivation_flag", "1")) != "2",
        "address_street": getattr(basic, "postal_address", "") or "",
        "address_number": getattr(basic, "postal_address_no", "") or "",
        "address_postal_code": getattr(basic, "postal_zip_code", "") or "",
        "address_city": getattr(basic, "postal_area_description", "") or "",
        "kad_list": [],
        "primary_kad": None,
    }

    if hasattr(result, "firm_act_tab") and result.firm_act_tab:
        activities = result.firm_act_tab
        if hasattr(activities, "item"):
            for act in activities.item:
                kad = {
                    "code": str(getattr(act, "firm_act_code", "") or ""),
                    "description": str(getattr(act, "firm_act_descr", "") or ""),
                    "kind": str(getattr(act, "firm_act_kind_descr", "") or ""),
                    "kind_code": int(getattr(act, "firm_act_kind", 2) or 2),
                }
                info["kad_list"].append(kad)
                if kad["kind_code"] == 1:
                    info["primary_kad"] = kad["code"]

    if not info["primary_kad"] and info["kad_list"]:
        info["primary_kad"] = info["kad_list"][0]["code"]

    return info


_afm_cache = AFMCacheDB()


def _lookup_afm(afm: str, force_refresh: bool = False) -> str:
    """Lookup AFM: cache first, then AADE SOAP."""
    afm = afm.strip().replace("EL", "").replace("el", "")

    if not _validate_afm(afm):
        return json.dumps({"error": f"Invalid AFM: {afm} (check digit failed)"}, ensure_ascii=False)

    # Check cache
    if not force_refresh:
        cached = _afm_cache.get(afm)
        if cached:
            cached["_source"] = "cache"
            return json.dumps(cached, ensure_ascii=False, indent=2)

    # SOAP call
    try:
        info = _soap_lookup_afm(afm)
    except Exception as e:
        return json.dumps({"error": f"AADE lookup failed: {e}"}, ensure_ascii=False)

    _afm_cache.put(afm, info)
    info["_source"] = "aade_live"
    return json.dumps(info, ensure_ascii=False, indent=2)


# ── Credential Store (SQLite) ──

class CredentialStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    afm TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    subscription_key TEXT NOT NULL,
                    env TEXT DEFAULT 'dev',
                    country TEXT DEFAULT 'GR',
                    branch INTEGER DEFAULT 0,
                    label TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_invoices (
                    mark TEXT NOT NULL,
                    afm TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    issue_date TEXT,
                    invoice_type TEXT,
                    type_name TEXT,
                    series TEXT,
                    aa TEXT,
                    counterpart_vat TEXT,
                    net_value REAL DEFAULT 0,
                    vat_amount REAL DEFAULT 0,
                    gross_value REAL DEFAULT 0,
                    processed_at TEXT DEFAULT (datetime('now')),
                    report_date TEXT,
                    PRIMARY KEY (mark, afm, direction)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounting_settings (
                    afm TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (afm, key)
                )
            """)

    def add(self, afm, user_id, subscription_key, env="dev", country="GR", branch=0, label=""):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO credentials (afm, user_id, subscription_key, env, country, branch, label, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(afm) DO UPDATE SET
                    user_id=excluded.user_id,
                    subscription_key=excluded.subscription_key,
                    env=excluded.env,
                    country=excluded.country,
                    branch=excluded.branch,
                    label=excluded.label,
                    updated_at=datetime('now')
            """, (afm, user_id, subscription_key, env, country, branch, label))

    def get(self, afm):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM credentials WHERE afm=?", (afm,)).fetchone()
            return dict(row) if row else None

    def list_all(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT afm, label, env, country, branch FROM credentials ORDER BY afm").fetchall()]

    def remove(self, afm):
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("DELETE FROM credentials WHERE afm=?", (afm,))
            return cur.rowcount > 0

    def set_default(self, afm):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('default_afm', ?)", (afm,))

    def get_default(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='default_afm'").fetchone()
            return row[0] if row else None

    # ── Accounting methods ──

    def is_invoice_processed(self, mark: str, afm: str, direction: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_invoices WHERE mark=? AND afm=? AND direction=?",
                (mark, afm, direction),
            ).fetchone()
            return row is not None

    def mark_invoices_processed(self, invoices: list, afm: str, direction: str,
                                report_date: str) -> int:
        """Insert invoices into processed_invoices. Returns count of newly inserted."""
        inserted = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            for inv in invoices:
                try:
                    changes_before = conn.total_changes
                    conn.execute("""
                        INSERT OR IGNORE INTO processed_invoices
                        (mark, afm, direction, issue_date, invoice_type, type_name,
                         series, aa, counterpart_vat, net_value, vat_amount, gross_value, report_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(inv.get("mark", "")),
                        afm,
                        direction,
                        inv.get("issueDate", ""),
                        inv.get("invoiceType", ""),
                        inv.get("type_name", ""),
                        inv.get("series", ""),
                        inv.get("aa", ""),
                        inv.get("counterpart_vat", ""),
                        float(inv.get("totalNetValue", 0)),
                        float(inv.get("totalVatAmount", 0)),
                        float(inv.get("totalGrossValue", 0)),
                        report_date,
                    ))
                    if conn.total_changes > changes_before:
                        inserted += 1
                except Exception:
                    pass
            conn.commit()
        return inserted

    def get_accounting_setting(self, afm: str, key: str, default=None) -> Optional[str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM accounting_settings WHERE afm=? AND key=?",
                (afm, key),
            ).fetchone()
            return row[0] if row else default

    def set_accounting_setting(self, afm: str, key: str, value: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO accounting_settings (afm, key, value) VALUES (?, ?, ?)",
                (afm, key, value),
            )

    def get_accounting_stats(self, afm: str) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM processed_invoices WHERE afm=?", (afm,)
            ).fetchone()[0]
            sent = conn.execute(
                "SELECT COUNT(*) FROM processed_invoices WHERE afm=? AND direction='sent'", (afm,)
            ).fetchone()[0]
            received = conn.execute(
                "SELECT COUNT(*) FROM processed_invoices WHERE afm=? AND direction='received'", (afm,)
            ).fetchone()[0]
            last_report = conn.execute(
                "SELECT MAX(report_date) FROM processed_invoices WHERE afm=?", (afm,)
            ).fetchone()[0]
            return {
                "total_processed": total,
                "sent": sent,
                "received": received,
                "last_report_date": last_report,
            }


cred_store = CredentialStore()


# ── AADE HTTP Client ──

class MyDataClient:
    def __init__(self, user_id, subscription_key, issuer_vat, env="dev",
                 issuer_country="GR", issuer_branch=0):
        self.base_url = ENVIRONMENTS.get(env, ENVIRONMENTS["dev"])
        self.headers = {
            "aade-user-id": user_id,
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/xml",
        }
        self.issuer_vat = issuer_vat
        self.issuer_country = issuer_country
        self.issuer_branch = issuer_branch
        self._http = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_env(cls):
        return cls(
            user_id=os.environ.get("MYDATA_USER_ID", ""),
            subscription_key=os.environ.get("MYDATA_SUBSCRIPTION_KEY", ""),
            issuer_vat=os.environ.get("ISSUER_VAT", ""),
            env=os.environ.get("MYDATA_ENV", "dev"),
            issuer_country=os.environ.get("ISSUER_COUNTRY", "GR"),
            issuer_branch=int(os.environ.get("ISSUER_BRANCH", "0")),
        )

    @classmethod
    def from_db(cls, afm):
        cred = cred_store.get(afm)
        if not cred:
            raise ValueError(f"No credentials found for AFM {afm}")
        return cls(
            user_id=cred["user_id"],
            subscription_key=cred["subscription_key"],
            issuer_vat=afm,
            env=cred["env"],
            issuer_country=cred["country"],
            issuer_branch=cred["branch"],
        )

    @classmethod
    def from_db_or_env(cls, afm=None):
        if afm:
            return cls.from_db(afm)
        default = cred_store.get_default()
        if default:
            cred = cred_store.get(default)
            if cred:
                return cls.from_db(default)
        return cls.from_env()

    async def close(self):
        await self._http.aclose()

    async def _post(self, endpoint, xml_data):
        resp = await self._http.post(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            content=xml_data,
        )
        return resp.content

    async def _get(self, endpoint, params=None):
        resp = await self._http.get(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            params=params,
        )
        return resp.content

    async def send_invoice_xml(self, xml_bytes):
        return await self._post("SendInvoices", xml_bytes)

    @staticmethod
    def _to_aade_date(d):
        """Convert YYYY-MM-DD to dd/MM/yyyy for AADE API."""
        if not d:
            return None
        if "/" in d:
            return d  # already dd/MM/yyyy
        parts = d.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return d

    async def get_sent_invoices(self, mark=0, date_from=None, date_to=None):
        params = {"mark": str(mark)}
        df = self._to_aade_date(date_from)
        dt = self._to_aade_date(date_to)
        if df:
            params["dateFrom"] = df
        if dt:
            params["dateTo"] = dt
        data = await self._get("RequestTransmittedDocs", params)
        return self._parse_invoices(data)

    async def get_received_invoices(self, mark=0, date_from=None, date_to=None):
        params = {"mark": str(mark)}
        df = self._to_aade_date(date_from)
        dt = self._to_aade_date(date_to)
        if df:
            params["dateFrom"] = df
        if dt:
            params["dateTo"] = dt
        data = await self._get("RequestDocs", params)
        return self._parse_invoices(data)

    async def cancel_invoice(self, mark):
        params = {"mark": str(mark)}
        data = await self._get("CancelInvoice", params)
        return self._parse_response(data)

    async def get_income(self, date_from, date_to):
        return await self._get("RequestMyIncome", {
            "dateFrom": self._to_aade_date(date_from),
            "dateTo": self._to_aade_date(date_to),
        })

    async def get_expenses(self, date_from, date_to):
        return await self._get("RequestMyExpenses", {
            "dateFrom": self._to_aade_date(date_from),
            "dateTo": self._to_aade_date(date_to),
        })

    def _parse_invoices(self, xml_data):
        """Parse invoice list from AADE response XML."""
        try:
            root = etree.fromstring(xml_data)
        except Exception:
            return [{"raw": xml_data.decode("utf-8", errors="replace")}]

        invoices = []
        for inv in root.iter(f"{{{NS_INV}}}invoice"):
            info = {}
            # Extract key fields
            for tag in ("mark", "uid", "invoiceType", "series", "aa"):
                el = inv.find(f".//{{{NS_INV}}}{tag}")
                if el is not None and el.text:
                    info[tag] = el.text
            # Issuer/counterpart VAT
            issuer_vat = inv.find(f".//{{{NS_INV}}}issuer/{{{NS_INV}}}vatNumber")
            if issuer_vat is not None:
                info["issuer_vat"] = issuer_vat.text
            cp_vat = inv.find(f".//{{{NS_INV}}}counterpart/{{{NS_INV}}}vatNumber")
            if cp_vat is not None:
                info["counterpart_vat"] = cp_vat.text
            # Totals
            for tag in ("totalNetValue", "totalVatAmount", "totalGrossValue"):
                el = inv.find(f".//{{{NS_INV}}}{tag}")
                if el is not None and el.text:
                    info[tag] = el.text
            # Date
            issue_date = inv.find(f".//{{{NS_INV}}}issueDate")
            if issue_date is not None:
                info["issueDate"] = issue_date.text
            invoices.append(info)

        if not invoices:
            return [{"raw": xml_data.decode("utf-8", errors="replace")[:2000]}]
        return invoices

    def _parse_response(self, xml_data):
        """Parse AADE response for send/cancel operations."""
        try:
            root = etree.fromstring(xml_data)
        except Exception:
            return {"raw": xml_data.decode("utf-8", errors="replace")}

        results = []
        for resp in root.iter(f"{{{NS_INV}}}response"):
            r = {"success": False}
            status = resp.find(f"{{{NS_INV}}}statusCode")
            if status is not None:
                r["success"] = status.text == "Success"
            for tag in ("invoiceMark", "invoiceUid", "cancellationMark", "qrUrl"):
                el = resp.find(f"{{{NS_INV}}}{tag}")
                if el is not None and el.text:
                    r[tag] = el.text
            errors = []
            for err in resp.iter(f"{{{NS_INV}}}error"):
                msg = err.find(f"{{{NS_INV}}}message")
                code = err.find(f"{{{NS_INV}}}code")
                errors.append({
                    "code": code.text if code is not None else "",
                    "message": msg.text if msg is not None else "",
                })
            if errors:
                r["errors"] = errors
            results.append(r)

        return results if results else {"raw": xml_data.decode("utf-8", errors="replace")}


def _build_invoice_xml(client, counterpart_vat, invoice_type, series, number,
                       items, payment_method=3, counterpart_country="GR",
                       counterpart_name="", issue_date=None, currency="EUR"):
    """Build myDATA XML for an invoice."""
    root = etree.Element("InvoicesDoc", nsmap=NAMESPACES)
    inv = etree.SubElement(root, "invoice")

    # Issuer
    issuer = etree.SubElement(inv, "issuer")
    etree.SubElement(issuer, "vatNumber").text = client.issuer_vat
    etree.SubElement(issuer, "country").text = client.issuer_country
    etree.SubElement(issuer, "branch").text = str(client.issuer_branch)

    # Counterpart (omit for retail receipt types 11.x – AADE forbids it)
    if not invoice_type.startswith("11."):
        cp = etree.SubElement(inv, "counterpart")
        etree.SubElement(cp, "vatNumber").text = counterpart_vat
        etree.SubElement(cp, "country").text = counterpart_country
        if counterpart_name and counterpart_country != "GR":
            etree.SubElement(cp, "name").text = counterpart_name
        etree.SubElement(cp, "branch").text = "0"

    # Invoice header
    header = etree.SubElement(inv, "invoiceHeader")
    etree.SubElement(header, "series").text = series
    etree.SubElement(header, "aa").text = str(number)
    etree.SubElement(header, "issueDate").text = (issue_date or date.today()).isoformat()
    etree.SubElement(header, "invoiceType").text = invoice_type
    etree.SubElement(header, "currency").text = currency

    # Payment methods
    pm = etree.SubElement(inv, "paymentMethods")
    pay = etree.SubElement(pm, "paymentMethodDetails")

    total_net = Decimal("0")
    total_vat = Decimal("0")

    # Invoice details (lines)
    for i, item in enumerate(items, 1):
        net = Decimal(str(item["net_value"])).quantize(Decimal("0.01"))
        vat_cat = int(item.get("vat_category", 1))
        vat_rate = VAT_RATES.get(vat_cat, Decimal("0.24"))
        vat_amount = (net * vat_rate).quantize(Decimal("0.01"))

        detail = etree.SubElement(inv, "invoiceDetails")
        etree.SubElement(detail, "lineNumber").text = str(i)
        if item.get("quantity"):
            etree.SubElement(detail, "quantity").text = str(item["quantity"])
        if item.get("unit_price"):
            etree.SubElement(detail, "unitPrice").text = str(item["unit_price"])
        etree.SubElement(detail, "netValue").text = str(net)
        etree.SubElement(detail, "vatCategory").text = str(vat_cat)
        etree.SubElement(detail, "vatAmount").text = str(vat_amount)

        # Income classification (must be in invoice namespace, not icls)
        icls = etree.SubElement(detail, f"{{{NS_INV}}}incomeClassification")
        etree.SubElement(icls, f"{{{NS_ICLS}}}classificationType").text = item.get(
            "income_classification_type", "E3_561_003")
        etree.SubElement(icls, f"{{{NS_ICLS}}}classificationCategory").text = item.get(
            "income_classification_category", "category1_3")
        etree.SubElement(icls, f"{{{NS_ICLS}}}amount").text = str(net)

        total_net += net
        total_vat += vat_amount

    total_gross = total_net + total_vat

    # Payment
    etree.SubElement(pay, "type").text = str(payment_method)
    etree.SubElement(pay, "amount").text = str(total_gross)

    # Summary
    summary = etree.SubElement(inv, "invoiceSummary")
    etree.SubElement(summary, "totalNetValue").text = str(total_net)
    etree.SubElement(summary, "totalVatAmount").text = str(total_vat)
    etree.SubElement(summary, "totalWithheldAmount").text = "0.00"
    etree.SubElement(summary, "totalFeesAmount").text = "0.00"
    etree.SubElement(summary, "totalStampDutyAmount").text = "0.00"
    etree.SubElement(summary, "totalOtherTaxesAmount").text = "0.00"
    etree.SubElement(summary, "totalDeductionsAmount").text = "0.00"
    etree.SubElement(summary, "totalGrossValue").text = str(total_gross)

    # Income classification summary (must be in invoice namespace)
    icls_sum = etree.SubElement(summary, f"{{{NS_INV}}}incomeClassification")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}classificationType").text = items[0].get(
        "income_classification_type", "E3_561_003")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}classificationCategory").text = items[0].get(
        "income_classification_category", "category1_3")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}amount").text = str(total_net)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ── Helper ──

def _get_client(args: dict) -> MyDataClient:
    """Get client for specific AFM or default."""
    afm = args.pop("issuer_afm", None)
    return MyDataClient.from_db_or_env(afm)


# ── Tool Implementations ──

async def _send_invoice(args: dict) -> str:
    client = _get_client(args)
    try:
        issue_dt = date.fromisoformat(args["issue_date"]) if args.get("issue_date") else None
        xml = _build_invoice_xml(
            client,
            counterpart_vat=args["counterpart_vat"],
            invoice_type=args["invoice_type"],
            series=args["series"],
            number=args["number"],
            items=args["items"],
            payment_method=args.get("payment_method", 3),
            counterpart_country=args.get("counterpart_country", "GR"),
            counterpart_name=args.get("counterpart_name", ""),
            issue_date=issue_dt,
            currency=args.get("currency", "EUR"),
        )
        resp = await client.send_invoice_xml(xml)
        results = client._parse_response(resp)
        return json.dumps({"results": results}, ensure_ascii=False, indent=2)
    finally:
        await client.close()


async def _get_invoices(args: dict) -> str:
    client = _get_client(args)
    try:
        direction = args.get("direction", "received")
        mark = args.get("mark", 0)
        date_from = args.get("date_from")
        date_to = args.get("date_to")

        if direction == "received":
            invoices = await client.get_received_invoices(mark, date_from, date_to)
        else:
            invoices = await client.get_sent_invoices(mark, date_from, date_to)

        return json.dumps({"invoices": invoices, "count": len(invoices)}, ensure_ascii=False, indent=2)
    finally:
        await client.close()


async def _cancel_invoice(args: dict) -> str:
    client = _get_client(args)
    try:
        results = await client.cancel_invoice(args["mark"])
        return json.dumps({"results": results}, ensure_ascii=False, indent=2)
    finally:
        await client.close()


async def _income_summary(args: dict) -> str:
    client = _get_client(args)
    try:
        data = await client.get_income(args["date_from"], args["date_to"])
        return data.decode("utf-8", errors="replace")
    finally:
        await client.close()


async def _expenses_summary(args: dict) -> str:
    client = _get_client(args)
    try:
        data = await client.get_expenses(args["date_from"], args["date_to"])
        return data.decode("utf-8", errors="replace")
    finally:
        await client.close()


async def _generate_xml(args: dict) -> str:
    client = _get_client(args)
    try:
        issue_dt = date.fromisoformat(args["issue_date"]) if args.get("issue_date") else None
        xml = _build_invoice_xml(
            client,
            counterpart_vat=args["counterpart_vat"],
            invoice_type=args["invoice_type"],
            series=args["series"],
            number=args["number"],
            items=args["items"],
            payment_method=args.get("payment_method", 3),
            counterpart_country=args.get("counterpart_country", "GR"),
            counterpart_name=args.get("counterpart_name", ""),
            issue_date=issue_dt,
            currency=args.get("currency", "EUR"),
        )
        return json.dumps({"xml": xml.decode("utf-8")}, ensure_ascii=False)
    finally:
        await client.close()


def _add_credentials(args: dict) -> str:
    cred_store.add(
        afm=args["afm"],
        user_id=args["user_id"],
        subscription_key=args["subscription_key"],
        env=args.get("env", "dev"),
        country=args.get("country", "GR"),
        branch=args.get("branch", 0),
        label=args.get("label", ""),
    )
    return json.dumps({"status": "ok", "afm": args["afm"]}, ensure_ascii=False)


def _list_credentials(args: dict) -> str:
    creds = cred_store.list_all()
    default = cred_store.get_default()
    return json.dumps({
        "credentials": creds,
        "default_afm": default,
        "count": len(creds),
    }, ensure_ascii=False, indent=2)


def _remove_credentials(args: dict) -> str:
    removed = cred_store.remove(args["afm"])
    if not removed:
        return json.dumps({"error": f"AFM {args['afm']} not found"}, ensure_ascii=False)
    return json.dumps({"status": "ok", "afm": args["afm"]}, ensure_ascii=False)


def _set_default_afm(args: dict) -> str:
    cred_store.set_default(args["afm"])
    return json.dumps({"status": "ok", "default_afm": args["afm"]}, ensure_ascii=False)


# ── Accounting Tool Implementations ──

def _find_send_email_script() -> Optional[Path]:
    """Search multiple locations for the send_email.py script."""
    candidates = [
        # Bundled in package data
        Path(__file__).resolve().parent.parent.parent / "src" / "agelclaw" / "data" / "skills" / "microsoft-graph-email" / "scripts" / "send_email.py",
        # Project skills dir
        PROJECT_DIR / ".Claude" / "Skills" / "microsoft-graph-email" / "scripts" / "send_email.py",
        # User skills dir
        Path.home() / ".claude" / "skills" / "microsoft-graph-email" / "scripts" / "send_email.py",
    ]
    # Also search upward from this file
    d = Path(__file__).resolve().parent
    for _ in range(10):
        for sub in [
            ".Claude/Skills/microsoft-graph-email/scripts/send_email.py",
            "proactive/skills/microsoft-graph-email/scripts/send_email.py",
        ]:
            p = d / sub
            if p.exists():
                return p
        d = d.parent

    for p in candidates:
        if p.exists():
            return p
    return None


def _enrich_supplier_names(invoices: list) -> int:
    """Add issuer_name to expense invoices by looking up issuer VAT numbers.

    Uses AFM cache (90 days) first, then AADE SOAP for uncached VATs.
    Returns the number of successfully resolved names.
    """
    vat_set = set()
    for inv in invoices:
        vat = inv.get("issuer_vat", "").strip()
        if vat and len(vat) == 9:
            vat_set.add(vat)

    if not vat_set:
        return 0

    name_map = {}
    for vat in vat_set:
        cached = _afm_cache.get(vat)
        if cached:
            name_map[vat] = cached.get("name", "")
            continue
        if _validate_afm(vat):
            try:
                info = _soap_lookup_afm(vat)
                _afm_cache.put(vat, info)
                name_map[vat] = info.get("name", "")
            except Exception:
                name_map[vat] = ""
        else:
            name_map[vat] = ""

    resolved = 0
    for inv in invoices:
        vat = inv.get("issuer_vat", "").strip()
        name = name_map.get(vat, "")
        if name:
            inv["issuer_name"] = name
            resolved += 1

    return resolved


async def _daily_accounting_report(args: dict) -> str:
    """Fetch invoices, deduplicate, generate Excel, optionally email."""
    from accounting_xlsx import generate_xlsx

    afm = args.get("issuer_afm") or cred_store.get_default() or os.environ.get("ISSUER_VAT", "")
    if not afm:
        return json.dumps({"error": "No AFM specified. Use issuer_afm or set a default."}, ensure_ascii=False)

    today = date.today().isoformat()
    date_from = args.get("date_from", today)
    date_to = args.get("date_to", today)
    send_email = args.get("send_email", True)
    email_to = args.get("email_to", "")
    from_email = args.get("from_email", "") or cred_store.get_accounting_setting(afm, "email_sender", "")

    # Fetch invoices from AADE
    client = MyDataClient.from_db_or_env(afm)
    try:
        all_sent = await client.get_sent_invoices(0, date_from, date_to)
        all_received = await client.get_received_invoices(0, date_from, date_to)
    finally:
        await client.close()

    # Filter out raw/error responses (they have a "raw" key)
    if all_sent and isinstance(all_sent[0], dict) and "raw" in all_sent[0]:
        all_sent = []
    if all_received and isinstance(all_received[0], dict) and "raw" in all_received[0]:
        all_received = []

    # Deduplicate: skip already processed
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
        "period": f"{date_from} — {date_to}",
        "new_income": len(new_sent),
        "new_expenses": len(new_received),
        "skipped_dupes": skipped_sent + skipped_received,
    }

    if not new_sent and not new_received:
        result["message"] = "Δεν βρέθηκαν νέα παραστατικά για αυτή την περίοδο."
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Enrich expenses with supplier names (from cache/AADE SOAP)
    try:
        resolved = _enrich_supplier_names(new_received)
        result["supplier_names_resolved"] = resolved
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

    # Compute totals for email summary
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
        recipients = email_to or cred_store.get_accounting_setting(afm, "email_recipients", "")
        if not recipients:
            result["email_result"] = "Δεν έχουν οριστεί παραλήπτες. Χρησιμοποίησε configure_accounting."
        else:
            script = _find_send_email_script()
            if not script:
                result["email_result"] = "Δεν βρέθηκε το send_email.py script."
            else:
                subject = f"Λογιστική Κατάσταση ΑΑΔΕ - ΑΦΜ {afm} ({date_from})"
                body = (
                    f"<h2>Λογιστική Κατάσταση ΑΑΔΕ</h2>"
                    f"<p><b>ΑΦΜ:</b> {afm} | <b>Περίοδος:</b> {date_from} — {date_to}</p>"
                    f"<table border='1' cellpadding='5' cellspacing='0'>"
                    f"<tr><td><b>Νέα Έσοδα</b></td><td>{len(new_sent)} ({income_net:,.2f} €)</td></tr>"
                    f"<tr><td><b>Νέα Έξοδα</b></td><td>{len(new_received)} ({expense_net:,.2f} €)</td></tr>"
                    f"<tr><td><b>ΦΠΑ Εσόδων</b></td><td>{income_vat:,.2f} €</td></tr>"
                    f"<tr><td><b>ΦΠΑ Εξόδων</b></td><td>{expense_vat:,.2f} €</td></tr>"
                    f"<tr><td><b>Κέρδος/Ζημία</b></td><td>{income_net - expense_net:,.2f} €</td></tr>"
                    f"</table>"
                    f"<p>Δείτε τα αναλυτικά στοιχεία στο συνημμένο Excel.</p>"
                )
                try:
                    import asyncio as _aio
                    cmd = [
                        sys.executable, str(script),
                        "--to", recipients,
                        "--subject", subject,
                        "--body", body,
                        "--attachment", str(xlsx_path),
                    ]
                    if from_email:
                        cmd.extend(["--from", from_email])
                    proc = await _aio.create_subprocess_exec(
                        *cmd,
                        stdout=_aio.subprocess.PIPE,
                        stderr=_aio.subprocess.PIPE,
                    )
                    try:
                        stdout, stderr = await _aio.wait_for(proc.communicate(), timeout=60)
                    except _aio.TimeoutError:
                        proc.kill()
                        result["email_result"] = "Email timeout (60s)"
                        return json.dumps(result, ensure_ascii=False, indent=2)
                    if proc.returncode == 0:
                        result["email_result"] = f"Email στάλθηκε στο {recipients}"
                    else:
                        result["email_result"] = f"Email error: {stderr.decode(errors='replace')[:500]}"
                except Exception as e:
                    result["email_result"] = f"Email exception: {e}"

    return json.dumps(result, ensure_ascii=False, indent=2)


def _configure_accounting(args: dict) -> str:
    """Configure accounting settings for an AFM."""
    afm = args.get("afm", "")
    if not afm:
        return json.dumps({"error": "AFM is required"}, ensure_ascii=False)

    updated = []
    if "email_recipients" in args:
        cred_store.set_accounting_setting(afm, "email_recipients", args["email_recipients"])
        updated.append(f"email_recipients={args['email_recipients']}")

    return json.dumps({
        "status": "ok",
        "afm": afm,
        "updated": updated,
        "current_settings": {
            "email_recipients": cred_store.get_accounting_setting(afm, "email_recipients", ""),
        },
    }, ensure_ascii=False, indent=2)


def _accounting_status(args: dict) -> str:
    """Get accounting statistics for an AFM."""
    afm = args.get("afm") or cred_store.get_default() or os.environ.get("ISSUER_VAT", "")
    if not afm:
        return json.dumps({"error": "No AFM specified"}, ensure_ascii=False)

    stats = cred_store.get_accounting_stats(afm)
    stats["afm"] = afm
    stats["email_recipients"] = cred_store.get_accounting_setting(afm, "email_recipients", "")
    return json.dumps(stats, ensure_ascii=False, indent=2)


# ── MCP Server Setup ──

server = Server("aade")

TOOLS = [
    Tool(
        name="send_invoice",
        description="Send invoice to AADE myDATA. Returns MARK (unique registration number). Supports all invoice types: 1.1 (sales), 2.1 (services), 5.1/5.2 (credit notes), 11.1/11.2 (retail receipts).",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "Issuer AFM. If provided, loads credentials from SQLite. If omitted, uses default AFM or .env.",
                },
                "counterpart_vat": {
                    "type": "string",
                    "description": "Counterpart VAT number (9 digits for GR)",
                },
                "invoice_type": {
                    "type": "string",
                    "enum": ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "2.4", "3.1", "5.1", "5.2", "11.1", "11.2"],
                    "description": "Invoice type: 1.1=Sales, 2.1=Services, 5.1=Credit note (correlated), 5.2=Credit note (uncorrelated), 11.1=Retail receipt, 11.2=Services receipt",
                },
                "series": {
                    "type": "string",
                    "description": "Invoice series (e.g. 'A', 'B', 'TPY')",
                },
                "number": {
                    "type": "integer",
                    "description": "Invoice sequence number",
                },
                "items": {
                    "type": "array",
                    "description": "Invoice line items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "net_value": {"type": "number", "description": "Net value (before VAT)"},
                            "vat_category": {"type": "integer", "description": "VAT category: 1=24%, 2=13%, 3=6%, 4=17%(island), 5=9%(island), 6=4%(island), 7=exempt, 8=no VAT", "default": 1},
                            "description": {"type": "string", "description": "Line item description"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "income_classification_type": {"type": "string", "default": "E3_561_003"},
                            "income_classification_category": {"type": "string", "default": "category1_3"},
                        },
                        "required": ["net_value"],
                    },
                },
                "payment_method": {
                    "type": "integer",
                    "description": "Payment method: 1=Domestic, 2=Foreign, 3=Cash, 4=Check, 5=Credit, 6=Web Banking, 7=POS/Card",
                    "default": 3,
                },
                "counterpart_country": {"type": "string", "default": "GR"},
                "counterpart_name": {"type": "string", "default": ""},
                "issue_date": {"type": "string", "description": "Issue date YYYY-MM-DD (default: today)"},
                "currency": {"type": "string", "default": "EUR"},
            },
            "required": ["counterpart_vat", "invoice_type", "series", "number", "items"],
        },
    ),
    Tool(
        name="get_invoices",
        description="Retrieve sent or received invoices from AADE myDATA with optional date filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "Issuer AFM (optional, uses default if omitted)"},
                "direction": {
                    "type": "string",
                    "enum": ["received", "sent"],
                    "description": "Invoice direction: 'received' or 'sent'",
                    "default": "received",
                },
                "mark": {"type": "integer", "description": "Start from this MARK (0 = all)", "default": 0},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
        },
    ),
    Tool(
        name="cancel_invoice",
        description="Cancel an invoice by its MARK number.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "Issuer AFM (optional)"},
                "mark": {"type": "integer", "description": "MARK of the invoice to cancel"},
            },
            "required": ["mark"],
        },
    ),
    Tool(
        name="income_summary",
        description="Get income summary from AADE for a date range. Returns XML with income data.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "Issuer AFM (optional)"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["date_from", "date_to"],
        },
    ),
    Tool(
        name="expenses_summary",
        description="Get expenses summary from AADE for a date range. Returns XML with expense data.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "Issuer AFM (optional)"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["date_from", "date_to"],
        },
    ),
    Tool(
        name="generate_xml",
        description="Generate myDATA XML without sending to AADE (dry run). Useful for previewing the XML before submission.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "Issuer AFM (optional)"},
                "counterpart_vat": {"type": "string", "description": "Counterpart VAT number"},
                "invoice_type": {"type": "string", "description": "Invoice type (e.g. 2.1)"},
                "series": {"type": "string"},
                "number": {"type": "integer"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "net_value": {"type": "number"},
                            "vat_category": {"type": "integer", "default": 1},
                            "description": {"type": "string"},
                        },
                        "required": ["net_value"],
                    },
                },
                "payment_method": {"type": "integer", "default": 3},
                "counterpart_country": {"type": "string", "default": "GR"},
                "counterpart_name": {"type": "string", "default": ""},
                "issue_date": {"type": "string"},
                "currency": {"type": "string", "default": "EUR"},
            },
            "required": ["counterpart_vat", "invoice_type", "series", "number", "items"],
        },
    ),
    Tool(
        name="add_credentials",
        description="Store myDATA API credentials for an AFM in SQLite. Use this to set up multi-AFM support for accountants or multi-entity businesses.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "Greek VAT number (AFM)"},
                "user_id": {"type": "string", "description": "AADE myDATA User ID"},
                "subscription_key": {"type": "string", "description": "AADE myDATA Subscription Key"},
                "env": {"type": "string", "enum": ["dev", "prod"], "default": "dev", "description": "Environment: dev (testing) or prod (live)"},
                "country": {"type": "string", "default": "GR"},
                "branch": {"type": "integer", "default": 0},
                "label": {"type": "string", "description": "Human-readable label for this entity (e.g. company name)"},
            },
            "required": ["afm", "user_id", "subscription_key"],
        },
    ),
    Tool(
        name="list_credentials",
        description="List all stored myDATA AFMs with their labels. No secrets are shown.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="remove_credentials",
        description="Remove stored myDATA credentials for an AFM.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "AFM to remove"},
            },
            "required": ["afm"],
        },
    ),
    Tool(
        name="set_default_afm",
        description="Set the default AFM used when issuer_afm is not specified in invoice operations.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "AFM to set as default"},
            },
            "required": ["afm"],
        },
    ),
    Tool(
        name="daily_accounting_report",
        description="Generate daily accounting report: fetch invoices from AADE, deduplicate, create Excel (income/expenses/summary sheets), and optionally email. Idempotent — re-runs skip already processed invoices.",
        inputSchema={
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "AFM (uses default if omitted)"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (default: today)"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD (default: today)"},
                "send_email": {"type": "boolean", "description": "Send Excel via email (default: true)", "default": True},
                "email_to": {"type": "string", "description": "Override email recipients (comma-separated)"},
            },
        },
    ),
    Tool(
        name="configure_accounting",
        description="Configure accounting settings for an AFM — email recipients for daily reports.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "Greek VAT number (AFM)"},
                "email_recipients": {"type": "string", "description": "Comma-separated email addresses for report delivery"},
            },
            "required": ["afm"],
        },
    ),
    Tool(
        name="accounting_status",
        description="Get accounting statistics: total processed invoices, last report date, configured email recipients.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "AFM (uses default if omitted)"},
            },
        },
    ),
    Tool(
        name="lookup_afm",
        description="Look up business details from AADE by AFM. Returns: name, DOY, legal form, address, KAD codes (activity codes), active status. Uses local cache (90 days). WARNING: the AFM owner gets notified in TAXISnet.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "Greek AFM (9 digits)"},
                "force_refresh": {"type": "boolean", "default": False, "description": "True to bypass cache and call AADE again"},
            },
            "required": ["afm"],
        },
    ),
    Tool(
        name="validate_afm",
        description="Validate AFM check digit locally (no AADE call). Returns whether the number is mathematically valid.",
        inputSchema={
            "type": "object",
            "properties": {
                "afm": {"type": "string", "description": "Greek AFM to validate"},
            },
            "required": ["afm"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _handle_tool(name, dict(arguments))
        return [TextContent(type="text", text=result)]
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))]


async def _handle_tool(name: str, args: dict) -> str:
    """Dispatch tool calls."""
    if name == "send_invoice":
        return await _send_invoice(args)
    elif name == "get_invoices":
        return await _get_invoices(args)
    elif name == "cancel_invoice":
        return await _cancel_invoice(args)
    elif name == "income_summary":
        return await _income_summary(args)
    elif name == "expenses_summary":
        return await _expenses_summary(args)
    elif name == "generate_xml":
        return await _generate_xml(args)
    elif name == "add_credentials":
        return _add_credentials(args)
    elif name == "list_credentials":
        return _list_credentials(args)
    elif name == "remove_credentials":
        return _remove_credentials(args)
    elif name == "set_default_afm":
        return _set_default_afm(args)
    elif name == "daily_accounting_report":
        return await _daily_accounting_report(args)
    elif name == "configure_accounting":
        return _configure_accounting(args)
    elif name == "accounting_status":
        return _accounting_status(args)
    elif name == "lookup_afm":
        return _lookup_afm(args["afm"], args.get("force_refresh", False))
    elif name == "validate_afm":
        afm = args["afm"].strip().replace("EL", "").replace("el", "")
        valid = _validate_afm(afm)
        return json.dumps({"afm": afm, "valid": valid, "message": "Valid AFM" if valid else "Invalid AFM (check digit failed)"})
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
