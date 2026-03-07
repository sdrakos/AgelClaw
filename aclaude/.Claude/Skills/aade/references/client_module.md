# myDATA Client Module — Complete Implementation

This file contains the full `mydata_client.py` module. Copy it into your project and configure via `.env`.

## Dependencies

```bash
pip install httpx lxml python-dotenv
# SQLite is included in Python stdlib — no extra install needed
```

## mydata_client.py

```python
"""
AADE myDATA REST API Client
Complete async Python client for sending, receiving, cancelling
and classifying invoices through the Greek tax authority API.

Usage:
    from mydata_client import MyDataClient
    
    client = MyDataClient.from_env()
    result = await client.send_invoice(invoice_data)
"""

import os
import asyncio
import sqlite3
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from pathlib import Path

import httpx
from lxml import etree


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

ENVIRONMENTS = {
    "dev": "https://mydata-dev.azure-api.net",
    "prod": "https://mydatapi.aade.gr/myDATA",
}

NAMESPACES = {
    None: "http://www.aade.gr/myDATA/invoice/v1.0",
    "icls": "http://www.aade.gr/myDATA/incomeClassificaton/v1.0",
    "ecls": "http://www.aade.gr/myDATA/expensesClassificaton/v1.0",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

NS_INV = "http://www.aade.gr/myDATA/invoice/v1.0"
NS_ICLS = "http://www.aade.gr/myDATA/incomeClassificaton/v1.0"
NS_ECLS = "http://www.aade.gr/myDATA/expensesClassificaton/v1.0"


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class InvoiceType(str, Enum):
    SALES_INVOICE = "1.1"
    SALES_INVOICE_INTRA_EU = "1.2"
    SALES_INVOICE_THIRD_COUNTRY = "1.3"
    SALES_INVOICE_INTRA_EU_THIRD = "1.4"
    SALES_COMPLEMENT = "1.5"
    SELF_SUPPLY = "1.6"
    SERVICES_INVOICE = "2.1"
    SERVICES_INTRA_EU = "2.2"
    SERVICES_THIRD_COUNTRY = "2.3"
    CONTRACT_INCOME = "2.4"
    TITLE_ACQUISITION = "3.1"
    TITLE_ACQUISITION_DENIED = "3.2"
    CREDIT_NOTE_CORRELATED = "5.1"
    CREDIT_NOTE_UNCORRELATED = "5.2"
    RETAIL_RECEIPT = "11.1"
    SERVICES_RECEIPT = "11.2"
    RETAIL_CREDIT_NOTE = "11.4"
    PAYROLL = "17.1"
    DEPRECIATION = "17.2"


class VatCategory(int, Enum):
    STANDARD_24 = 1
    REDUCED_13 = 2
    SUPER_REDUCED_6 = 3
    ISLAND_17 = 4
    ISLAND_9 = 5
    ISLAND_4 = 6
    EXEMPT_WITH_DEDUCTION = 7
    NO_VAT = 8


VAT_RATES = {
    VatCategory.STANDARD_24: Decimal("0.24"),
    VatCategory.REDUCED_13: Decimal("0.13"),
    VatCategory.SUPER_REDUCED_6: Decimal("0.06"),
    VatCategory.ISLAND_17: Decimal("0.17"),
    VatCategory.ISLAND_9: Decimal("0.09"),
    VatCategory.ISLAND_4: Decimal("0.04"),
    VatCategory.EXEMPT_WITH_DEDUCTION: Decimal("0"),
    VatCategory.NO_VAT: Decimal("0"),
}


class PaymentMethod(int, Enum):
    DOMESTIC_BANK = 1
    FOREIGN_BANK = 2
    CASH = 3
    CHEQUE = 4
    CREDIT = 5
    WEB_BANKING = 6
    POS = 7


# ──────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────

@dataclass
class Party:
    vat_number: str
    country: str = "GR"
    branch: int = 0
    name: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_postal_code: Optional[str] = None
    address_city: Optional[str] = None


@dataclass
class InvoiceLine:
    line_number: int
    net_value: Decimal
    vat_category: VatCategory
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    income_classification_type: str = "E3_561_003"
    income_classification_category: str = "category1_3"
    
    @property
    def vat_amount(self) -> Decimal:
        rate = VAT_RATES[self.vat_category]
        return (self.net_value * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @property
    def gross_value(self) -> Decimal:
        return self.net_value + self.vat_amount


@dataclass
class PaymentInfo:
    method: PaymentMethod
    amount: Decimal
    info: Optional[str] = None


@dataclass
class InvoiceData:
    """All data needed to build a myDATA invoice XML."""
    issuer: Party
    counterpart: Party
    invoice_type: InvoiceType
    series: str
    number: int
    issue_date: date
    lines: list[InvoiceLine]
    payments: list[PaymentInfo]
    currency: str = "EUR"
    correlated_invoices: Optional[list[int]] = None  # MARKs for credit notes
    
    @property
    def total_net(self) -> Decimal:
        return sum(line.net_value for line in self.lines)
    
    @property
    def total_vat(self) -> Decimal:
        return sum(line.vat_amount for line in self.lines)
    
    @property
    def total_gross(self) -> Decimal:
        return self.total_net + self.total_vat


@dataclass
class MyDataResponse:
    success: bool
    index: Optional[int] = None
    invoice_uid: Optional[str] = None
    invoice_mark: Optional[int] = None
    classification_mark: Optional[int] = None
    cancellation_mark: Optional[int] = None
    qr_url: Optional[str] = None
    status_code: Optional[str] = None
    errors: list[dict] = field(default_factory=list)


# ──────────────────────────────────────────────
# XML Builder
# ──────────────────────────────────────────────

def _el(parent, tag, text=None, ns=NS_INV):
    """Create a sub-element with the correct namespace."""
    elem = etree.SubElement(parent, f"{{{ns}}}{tag}" if ns else tag)
    if text is not None:
        elem.text = str(text)
    return elem


def build_invoice_xml(invoice: InvoiceData) -> bytes:
    """Build a complete InvoicesDoc XML from InvoiceData.
    
    Element ordering follows AADE XSD specification exactly.
    Incorrect ordering will cause XMLSyntaxError rejection.
    """
    nsmap = {
        None: NS_INV,
        "icls": NS_ICLS,
        "ecls": NS_ECLS,
    }
    
    root = etree.Element(f"{{{NS_INV}}}InvoicesDoc", nsmap=nsmap)
    inv = _el(root, "invoice")
    
    # 1. Issuer (required)
    issuer = _el(inv, "issuer")
    _el(issuer, "vatNumber", invoice.issuer.vat_number)
    _el(issuer, "country", invoice.issuer.country)
    _el(issuer, "branch", invoice.issuer.branch)
    
    # 2. Counterpart (required for most types)
    if invoice.counterpart:
        cp = _el(inv, "counterpart")
        _el(cp, "vatNumber", invoice.counterpart.vat_number)
        _el(cp, "country", invoice.counterpart.country)
        _el(cp, "branch", invoice.counterpart.branch)
        # Name required only for non-GR counterparts
        if invoice.counterpart.country != "GR" and invoice.counterpart.name:
            _el(cp, "name", invoice.counterpart.name)
        # Address (optional)
        if invoice.counterpart.address_city:
            addr = _el(cp, "address")
            if invoice.counterpart.address_street:
                _el(addr, "street", invoice.counterpart.address_street)
            if invoice.counterpart.address_number:
                _el(addr, "number", invoice.counterpart.address_number)
            if invoice.counterpart.address_postal_code:
                _el(addr, "postalCode", invoice.counterpart.address_postal_code)
            _el(addr, "city", invoice.counterpart.address_city)
    
    # 3. Invoice header
    header = _el(inv, "invoiceHeader")
    _el(header, "series", invoice.series)
    _el(header, "aa", invoice.number)
    _el(header, "issueDate", invoice.issue_date.isoformat())
    _el(header, "invoiceType", invoice.invoice_type.value)
    _el(header, "currency", invoice.currency)
    
    # Correlated invoices (for credit notes)
    if invoice.correlated_invoices:
        for mark in invoice.correlated_invoices:
            _el(header, "correlatedInvoices", mark)
    
    # 4. Payment methods
    payments = _el(inv, "paymentMethods")
    for pmt in invoice.payments:
        pmd = _el(payments, "paymentMethodDetails")
        _el(pmd, "type", pmt.method.value)
        _el(pmd, "amount", f"{pmt.amount:.2f}")
        if pmt.info:
            _el(pmd, "paymentMethodInfo", pmt.info)
    
    # 5. Invoice detail lines
    for line in invoice.lines:
        det = _el(inv, "invoiceDetails")
        _el(det, "lineNumber", line.line_number)
        _el(det, "netValue", f"{line.net_value:.2f}")
        _el(det, "vatCategory", line.vat_category.value)
        _el(det, "vatAmount", f"{line.vat_amount:.2f}")
        
        # Income classification per line
        icls = _el(det, "incomeClassification")
        _el(icls, "classificationType", line.income_classification_type, ns=NS_ICLS)
        _el(icls, "classificationCategory", line.income_classification_category, ns=NS_ICLS)
        _el(icls, "amount", f"{line.net_value:.2f}", ns=NS_ICLS)
    
    # 6. Invoice summary
    summary = _el(inv, "invoiceSummary")
    _el(summary, "totalNetValue", f"{invoice.total_net:.2f}")
    _el(summary, "totalVatAmount", f"{invoice.total_vat:.2f}")
    _el(summary, "totalWithheldAmount", "0.00")
    _el(summary, "totalFeesAmount", "0.00")
    _el(summary, "totalStampDutyAmount", "0.00")
    _el(summary, "totalOtherTaxesAmount", "0.00")
    _el(summary, "totalDeductionsAmount", "0.00")
    _el(summary, "totalGrossValue", f"{invoice.total_gross:.2f}")
    
    # Aggregate income classifications in summary
    classifications = {}
    for line in invoice.lines:
        key = (line.income_classification_type, line.income_classification_category)
        classifications[key] = classifications.get(key, Decimal("0")) + line.net_value
    
    for (cls_type, cls_cat), amount in classifications.items():
        icls_sum = _el(summary, "incomeClassification")
        _el(icls_sum, "classificationType", cls_type, ns=NS_ICLS)
        _el(icls_sum, "classificationCategory", cls_cat, ns=NS_ICLS)
        _el(icls_sum, "amount", f"{amount:.2f}", ns=NS_ICLS)
    
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ──────────────────────────────────────────────
# Response Parser
# ──────────────────────────────────────────────

def parse_response(xml_bytes: bytes) -> list[MyDataResponse]:
    """Parse AADE ResponseDoc XML into a list of MyDataResponse objects."""
    root = etree.fromstring(xml_bytes)
    ns = {"r": "http://www.aade.gr/myDATA/response/v1.0"}
    
    results = []
    for resp_elem in root.findall(".//r:response", ns):
        r = MyDataResponse(success=False)
        
        status = resp_elem.findtext("r:statusCode", namespaces=ns)
        r.status_code = status
        r.success = status == "Success"
        
        idx = resp_elem.findtext("r:index", namespaces=ns)
        r.index = int(idx) if idx else None
        
        r.invoice_uid = resp_elem.findtext("r:invoiceUid", namespaces=ns)
        
        mark = resp_elem.findtext("r:invoiceMark", namespaces=ns)
        r.invoice_mark = int(mark) if mark else None
        
        cls_mark = resp_elem.findtext("r:classificationMark", namespaces=ns)
        r.classification_mark = int(cls_mark) if cls_mark else None
        
        cancel_mark = resp_elem.findtext("r:cancellationMark", namespaces=ns)
        r.cancellation_mark = int(cancel_mark) if cancel_mark else None
        
        r.qr_url = resp_elem.findtext("r:qrUrl", namespaces=ns)
        
        # Collect errors
        for err in resp_elem.findall(".//r:error", ns):
            r.errors.append({
                "code": err.findtext("r:code", namespaces=ns),
                "message": err.findtext("r:message", namespaces=ns),
            })
        
        results.append(r)
    
    return results


def parse_invoices_response(xml_bytes: bytes) -> list[dict]:
    """Parse RequestDocs / RequestTransmittedDocs response into dicts."""
    root = etree.fromstring(xml_bytes)
    invoices = []
    
    for inv_elem in root.iter(f"{{{NS_INV}}}invoice"):
        invoice = {}
        
        # Extract header info
        header = inv_elem.find(f"{{{NS_INV}}}invoiceHeader")
        if header is not None:
            invoice["series"] = header.findtext(f"{{{NS_INV}}}series")
            invoice["number"] = header.findtext(f"{{{NS_INV}}}aa")
            invoice["issue_date"] = header.findtext(f"{{{NS_INV}}}issueDate")
            invoice["invoice_type"] = header.findtext(f"{{{NS_INV}}}invoiceType")
        
        # MARK and UID
        invoice["uid"] = inv_elem.findtext(f"{{{NS_INV}}}uid")
        invoice["mark"] = inv_elem.findtext(f"{{{NS_INV}}}mark")
        
        # Issuer
        issuer = inv_elem.find(f"{{{NS_INV}}}issuer")
        if issuer is not None:
            invoice["issuer_vat"] = issuer.findtext(f"{{{NS_INV}}}vatNumber")
        
        # Counterpart
        cp = inv_elem.find(f"{{{NS_INV}}}counterpart")
        if cp is not None:
            invoice["counterpart_vat"] = cp.findtext(f"{{{NS_INV}}}vatNumber")
        
        # Summary
        summary = inv_elem.find(f"{{{NS_INV}}}invoiceSummary")
        if summary is not None:
            invoice["total_net"] = summary.findtext(f"{{{NS_INV}}}totalNetValue")
            invoice["total_vat"] = summary.findtext(f"{{{NS_INV}}}totalVatAmount")
            invoice["total_gross"] = summary.findtext(f"{{{NS_INV}}}totalGrossValue")
        
        invoices.append(invoice)
    
    return invoices


# ──────────────────────────────────────────────
# Credential Store (SQLite — multi-AFM support)
# ──────────────────────────────────────────────

DEFAULT_DB_PATH = Path.home() / ".agelclaw" / "data" / "mydata_credentials.db"


class CredentialStore:
    """SQLite-backed credential store for multiple AFMs.

    Useful for accountants managing many clients or businesses
    with multiple tax numbers (AFM). Each AFM has its own
    MYDATA_USER_ID and MYDATA_SUBSCRIPTION_KEY.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    afm TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    subscription_key TEXT NOT NULL,
                    env TEXT NOT NULL DEFAULT 'dev',
                    country TEXT NOT NULL DEFAULT 'GR',
                    branch INTEGER NOT NULL DEFAULT 0,
                    label TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def add(self, afm: str, user_id: str, subscription_key: str,
            env: str = "dev", country: str = "GR", branch: int = 0,
            label: str = "") -> None:
        """Add or update credentials for an AFM."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO credentials (afm, user_id, subscription_key, env, country, branch, label)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(afm) DO UPDATE SET
                    user_id = excluded.user_id,
                    subscription_key = excluded.subscription_key,
                    env = excluded.env,
                    country = excluded.country,
                    branch = excluded.branch,
                    label = excluded.label,
                    updated_at = datetime('now')
            """, (afm, user_id, subscription_key, env, country, branch, label))

    def get(self, afm: str) -> Optional[dict]:
        """Get credentials for a specific AFM. Returns None if not found."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM credentials WHERE afm = ?", (afm,)
            ).fetchone()
            return dict(row) if row else None

    def list_all(self) -> list[dict]:
        """List all stored AFMs with their labels and env."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT afm, label, env, country, branch, created_at FROM credentials ORDER BY afm"
            ).fetchall()
            return [dict(r) for r in rows]

    def remove(self, afm: str) -> bool:
        """Remove credentials for an AFM. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM credentials WHERE afm = ?", (afm,))
            return cursor.rowcount > 0

    def set_default(self, afm: str) -> None:
        """Mark an AFM as the default (stored in a separate key-value row)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                INSERT INTO settings (key, value) VALUES ('default_afm', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (afm,))

    def get_default(self) -> Optional[str]:
        """Get the default AFM, or None."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = 'default_afm'"
                ).fetchone()
                return row[0] if row else None
            except sqlite3.OperationalError:
                return None


# ──────────────────────────────────────────────
# HTTP Client
# ──────────────────────────────────────────────

class MyDataClient:
    """Async HTTP client for AADE myDATA REST API."""
    
    def __init__(self, user_id: str, subscription_key: str, 
                 env: str = "dev", issuer_vat: str = "",
                 issuer_country: str = "GR", issuer_branch: int = 0):
        self.base_url = ENVIRONMENTS[env]
        self.headers = {
            "aade-user-id": user_id,
            "ocp-apim-subscription-key": subscription_key,
            "Content-Type": "application/xml",
        }
        self.issuer = Party(
            vat_number=issuer_vat,
            country=issuer_country,
            branch=issuer_branch,
        )
        self._client = httpx.AsyncClient(timeout=30.0)
    
    @classmethod
    def from_env(cls) -> "MyDataClient":
        """Create client from environment variables (single-AFM mode)."""
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            user_id=os.environ["MYDATA_USER_ID"],
            subscription_key=os.environ["MYDATA_SUBSCRIPTION_KEY"],
            env=os.environ.get("MYDATA_ENV", "dev"),
            issuer_vat=os.environ.get("ISSUER_VAT", ""),
            issuer_country=os.environ.get("ISSUER_COUNTRY", "GR"),
            issuer_branch=int(os.environ.get("ISSUER_BRANCH", "0")),
        )

    @classmethod
    def from_db(cls, afm: str, db_path: Optional[Path] = None) -> "MyDataClient":
        """Create client from SQLite credential store for a specific AFM.

        Args:
            afm: The issuer's VAT number (ΑΦΜ) to load credentials for.
            db_path: Path to the credentials database. Defaults to
                     ~/.agelclaw/data/mydata_credentials.db

        Raises:
            ValueError: If no credentials found for the given AFM.
        """
        store = CredentialStore(db_path)
        creds = store.get(afm)
        if not creds:
            raise ValueError(
                f"No myDATA credentials found for AFM {afm}. "
                f"Add them with: CredentialStore().add('{afm}', user_id, subscription_key)"
            )
        return cls(
            user_id=creds["user_id"],
            subscription_key=creds["subscription_key"],
            env=creds["env"],
            issuer_vat=afm,
            issuer_country=creds["country"],
            issuer_branch=creds["branch"],
        )

    @classmethod
    def from_db_or_env(cls, afm: Optional[str] = None, db_path: Optional[Path] = None) -> "MyDataClient":
        """Try SQLite first (if afm given or default set), fall back to .env.

        This is the recommended constructor for multi-AFM setups:
        - If afm is provided, loads from DB
        - If afm is None, checks for a default AFM in DB
        - If no default, falls back to .env variables
        """
        store = CredentialStore(db_path)
        if afm is None:
            afm = store.get_default()
        if afm:
            creds = store.get(afm)
            if creds:
                return cls(
                    user_id=creds["user_id"],
                    subscription_key=creds["subscription_key"],
                    env=creds["env"],
                    issuer_vat=afm,
                    issuer_country=creds["country"],
                    issuer_branch=creds["branch"],
                )
        return cls.from_env()
    
    async def close(self):
        await self._client.aclose()
    
    # ── Send Invoice ──
    
    async def send_invoice(self, invoice: InvoiceData) -> list[MyDataResponse]:
        """Send one invoice to AADE myDATA. Returns list of responses."""
        xml_body = build_invoice_xml(invoice)
        resp = await self._client.post(
            f"{self.base_url}/SendInvoices",
            headers=self.headers,
            content=xml_body,
        )
        resp.raise_for_status()
        return parse_response(resp.content)
    
    async def send_invoice_simple(
        self,
        counterpart_vat: str,
        invoice_type: str,
        series: str,
        number: int,
        items: list[dict],
        payment_method: int = 3,
        counterpart_country: str = "GR",
        counterpart_name: str = "",
        currency: str = "EUR",
        issue_date: Optional[date] = None,
    ) -> list[MyDataResponse]:
        """Simplified invoice sending — builds InvoiceData from basic params.
        
        items: list of dicts with keys: net_value, vat_category (1-8),
               and optionally: description, quantity, unit_price,
               income_classification_type, income_classification_category
        """
        if issue_date is None:
            issue_date = date.today()
        
        lines = []
        total = Decimal("0")
        for i, item in enumerate(items, 1):
            net = Decimal(str(item["net_value"]))
            vat_cat = VatCategory(item.get("vat_category", 1))
            
            line = InvoiceLine(
                line_number=i,
                net_value=net,
                vat_category=vat_cat,
                description=item.get("description"),
                quantity=Decimal(str(item["quantity"])) if "quantity" in item else None,
                unit_price=Decimal(str(item["unit_price"])) if "unit_price" in item else None,
                income_classification_type=item.get("income_classification_type", "E3_561_003"),
                income_classification_category=item.get("income_classification_category", "category1_3"),
            )
            lines.append(line)
            total += line.gross_value
        
        counterpart = Party(
            vat_number=counterpart_vat,
            country=counterpart_country,
            name=counterpart_name if counterpart_country != "GR" else None,
        )
        
        invoice = InvoiceData(
            issuer=self.issuer,
            counterpart=counterpart,
            invoice_type=InvoiceType(invoice_type),
            series=series,
            number=number,
            issue_date=issue_date,
            lines=lines,
            payments=[PaymentInfo(
                method=PaymentMethod(payment_method),
                amount=total,
            )],
            currency=currency,
        )
        
        return await self.send_invoice(invoice)
    
    # ── Cancel Invoice ──
    
    async def cancel_invoice(self, mark: int, entity_vat: Optional[str] = None) -> list[MyDataResponse]:
        """Cancel an invoice by its MARK."""
        params = {"mark": mark}
        if entity_vat:
            params["entityVatNumber"] = entity_vat
        
        resp = await self._client.post(
            f"{self.base_url}/CancelInvoice",
            headers=self.headers,
            params=params,
        )
        resp.raise_for_status()
        return parse_response(resp.content)
    
    # ── Retrieve Invoices ──
    
    async def get_received_invoices(
        self, mark: int = 0, date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> list[dict]:
        """Get invoices received from other parties (where you are the counterpart)."""
        params = {"mark": mark}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        
        resp = await self._client.get(
            f"{self.base_url}/RequestDocs",
            headers=self.headers,
            params=params,
        )
        resp.raise_for_status()
        return parse_invoices_response(resp.content)
    
    async def get_sent_invoices(
        self, mark: int = 0, date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> list[dict]:
        """Get invoices you have sent (transmitted)."""
        params = {"mark": mark}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        
        resp = await self._client.get(
            f"{self.base_url}/RequestTransmittedDocs",
            headers=self.headers,
            params=params,
        )
        resp.raise_for_status()
        return parse_invoices_response(resp.content)
    
    # ── Income / Expenses ──
    
    async def get_income(self, date_from: str, date_to: str) -> bytes:
        """Get income summary for a date range. Dates in dd/MM/yyyy format."""
        resp = await self._client.get(
            f"{self.base_url}/RequestMyIncome",
            headers=self.headers,
            params={"dateFrom": date_from, "dateTo": date_to},
        )
        resp.raise_for_status()
        return resp.content
    
    async def get_expenses(self, date_from: str, date_to: str) -> bytes:
        """Get expenses summary for a date range. Dates in dd/MM/yyyy format."""
        resp = await self._client.get(
            f"{self.base_url}/RequestMyExpenses",
            headers=self.headers,
            params={"dateFrom": date_from, "dateTo": date_to},
        )
        resp.raise_for_status()
        return resp.content
```

## Usage Examples

### Send a services invoice

```python
import asyncio
from mydata_client import MyDataClient

async def main():
    client = MyDataClient.from_env()
    
    results = await client.send_invoice_simple(
        counterpart_vat="012345678",
        invoice_type="2.1",  # Services invoice
        series="B",
        number=42,
        items=[
            {
                "net_value": 500.00,
                "vat_category": 1,  # 24%
                "description": "Υπηρεσίες συμβούλου πληροφορικής",
            },
            {
                "net_value": 200.00,
                "vat_category": 1,
                "description": "Εγκατάσταση λογισμικού",
            },
        ],
        payment_method=7,  # POS
    )
    
    for r in results:
        if r.success:
            print(f"✅ MARK: {r.invoice_mark}")
        else:
            print(f"❌ Errors: {r.errors}")
    
    await client.close()

asyncio.run(main())
```

### Retrieve and display received invoices

```python
async def show_received():
    client = MyDataClient.from_env()
    invoices = await client.get_received_invoices(
        date_from="01/01/2026",
        date_to="31/03/2026"
    )
    
    for inv in invoices:
        print(f"MARK: {inv['mark']} | From: {inv.get('issuer_vat')} "
              f"| Amount: {inv.get('total_gross')}€ "
              f"| Date: {inv.get('issue_date')}")
    
    await client.close()
```

### Cancel an invoice

```python
async def cancel():
    client = MyDataClient.from_env()
    results = await client.cancel_invoice(mark=400012345)

    for r in results:
        if r.success:
            print(f"✅ Cancelled. Cancellation MARK: {r.cancellation_mark}")
        else:
            print(f"❌ {r.errors}")

    await client.close()
```

### Multi-AFM: Managing credentials

```python
from mydata_client import CredentialStore, MyDataClient

# Create credential store (auto-creates SQLite DB)
store = CredentialStore()

# Add credentials for multiple AFMs
store.add(
    afm="999999999",
    user_id="user1",
    subscription_key="key1",
    env="dev",
    label="Εταιρεία Α"
)
store.add(
    afm="888888888",
    user_id="user2",
    subscription_key="key2",
    env="dev",
    label="Εταιρεία Β"
)

# Set default AFM
store.set_default("999999999")

# List all stored AFMs
for cred in store.list_all():
    print(f"{cred['afm']} - {cred['label']} ({cred['env']})")

# Create client for a specific AFM
client = MyDataClient.from_db("888888888")

# Or use the smart constructor (tries DB first, falls back to .env)
client = MyDataClient.from_db_or_env(afm="888888888")
client = MyDataClient.from_db_or_env()  # uses default AFM or .env
```
