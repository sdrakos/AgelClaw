"""
AADE myDATA HTTP Client
========================
Adapted from the AgelClaw AADE MCP server for the Timologia web app.
Handles invoice submission, retrieval, cancellation, and income/expenses queries.
"""
import asyncio
import httpx
from datetime import date
from decimal import Decimal
from lxml import etree


# ── AADE API Configuration ──

AADE_URLS = {
    "dev": "https://mydataapidev.aade.gr",
    "prod": "https://mydatapi.aade.gr/myDATA",
}

NS_INV = "http://www.aade.gr/myDATA/invoice/v1.0"
# Dev API uses https:// namespace URIs for classification elements
NS_ICLS = "https://www.aade.gr/myDATA/incomeClassificaton/v1.0"
NS_ECLS = "https://www.aade.gr/myDATA/expensesClassificaton/v1.0"


class MyDataClient:
    """Async HTTP client for the AADE myDATA REST API."""

    def __init__(self, user_id: str, subscription_key: str, issuer_vat: str,
                 env: str = "dev", issuer_country: str = "GR", issuer_branch: int = 0):
        self.base_url = AADE_URLS.get(env, AADE_URLS["dev"])
        self.headers = {
            "aade-user-id": user_id,
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/xml",
        }
        self.issuer_vat = issuer_vat
        self.issuer_country = issuer_country
        self.issuer_branch = issuer_branch
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._http.aclose()

    async def _post(self, endpoint, xml_data):
        for attempt in range(4):
            resp = await self._http.post(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                content=xml_data,
            )
            if resp.status_code != 429:
                return resp.content
            # Rate limited — wait and retry
            wait = self._parse_retry_after(resp)
            await asyncio.sleep(wait)
        return resp.content

    async def _get(self, endpoint, params=None):
        for attempt in range(4):
            resp = await self._http.get(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                params=params,
            )
            if resp.status_code != 429:
                return resp.content
            # Rate limited — wait and retry
            wait = self._parse_retry_after(resp)
            await asyncio.sleep(wait)
        return resp.content

    @staticmethod
    def _parse_retry_after(resp) -> int:
        """Extract wait seconds from 429 response."""
        try:
            import json as _json
            body = _json.loads(resp.content)
            msg = body.get("message", "")
            # "Try again in 48 seconds."
            import re
            m = re.search(r"(\d+)\s*second", msg)
            if m:
                return int(m.group(1)) + 1
        except Exception:
            pass
        return 30

    async def send_invoice_xml(self, xml_bytes: bytes):
        """Send pre-built invoice XML to AADE."""
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
        """Retrieve transmitted (sent) invoices from AADE."""
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
        """Retrieve received invoices from AADE."""
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
        """Cancel an invoice by its MARK number."""
        params = {"mark": str(mark)}
        data = await self._get("CancelInvoice", params)
        return self._parse_response(data)

    async def get_income(self, date_from, date_to):
        """Get income summary for a date range."""
        return await self._get("RequestMyIncome", {
            "dateFrom": self._to_aade_date(date_from),
            "dateTo": self._to_aade_date(date_to),
        })

    async def get_expenses(self, date_from, date_to):
        """Get expenses summary for a date range."""
        return await self._get("RequestMyExpenses", {
            "dateFrom": self._to_aade_date(date_from),
            "dateTo": self._to_aade_date(date_to),
        })

    def _parse_invoices(self, xml_data: bytes) -> list[dict]:
        """Parse invoice list from AADE response XML.

        Iterates over all <invoice> elements in the AADE namespace,
        extracting key fields: mark, uid, invoiceType, series, aa,
        issuer/counterpart VAT, totals, and issue date.

        Returns a list of dicts. If parsing fails or no invoices found,
        returns a single-element list with the raw XML text.
        """
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

    def _parse_response(self, xml_data: bytes) -> list[dict] | dict:
        """Parse AADE response for send/cancel operations.

        Iterates over all <response> elements, extracting:
        - statusCode (mapped to success bool)
        - invoiceMark, invoiceUid, cancellationMark, qrUrl
        - error codes and messages

        Returns a list of result dicts, or a single dict with raw XML on failure.
        """
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
