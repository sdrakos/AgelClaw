# FastAPI Server for myDATA Agent Tools

Production-ready HTTP server exposing myDATA operations as API endpoints for agent tool calls. Supports multi-AFM credential management via SQLite for accountants and multi-entity businesses.

## Installation

```bash
pip install fastapi uvicorn httpx lxml python-dotenv
```

## mydata_api.py

```python
"""
FastAPI server wrapping AADE myDATA client.
Deploy with: uvicorn mydata_api:app --host 0.0.0.0 --port 8100
Manage with: pm2 start "uvicorn mydata_api:app --host 0.0.0.0 --port 8100" --name mydata-api
"""

import os
from datetime import date
from decimal import Decimal
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mydata_client import (
    MyDataClient, CredentialStore, InvoiceData, Party, InvoiceLine,
    PaymentInfo, InvoiceType, VatCategory, PaymentMethod, build_invoice_xml,
)


# ── Lifespan (init/cleanup client) ──

client: Optional[MyDataClient] = None
cred_store = CredentialStore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = MyDataClient.from_db_or_env()
    yield
    await client.close()


def _get_client(issuer_afm: Optional[str] = None) -> MyDataClient:
    """Get client for a specific AFM, or the default."""
    if issuer_afm:
        return MyDataClient.from_db(issuer_afm)
    return client

app = FastAPI(
    title="myDATA Agent API",
    description="AADE myDATA invoice management for AI agents",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request Models ──

class InvoiceItem(BaseModel):
    description: Optional[str] = None
    net_value: float
    vat_category: int = Field(default=1, ge=1, le=8)
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    income_classification_type: str = "E3_561_003"
    income_classification_category: str = "category1_3"

class SendInvoiceRequest(BaseModel):
    counterpart_vat: str
    invoice_type: str
    series: str
    number: int
    items: list[InvoiceItem]
    payment_method: int = Field(default=3, ge=1, le=8)
    counterpart_country: str = "GR"
    counterpart_name: str = ""
    issue_date: Optional[str] = None
    currency: str = "EUR"
    issuer_afm: Optional[str] = None  # Use specific AFM's credentials

class CancelInvoiceRequest(BaseModel):
    mark: int
    entity_vat: Optional[str] = None
    issuer_afm: Optional[str] = None

class GetInvoicesRequest(BaseModel):
    direction: str = "received"  # "received" or "sent"
    mark: int = 0
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    issuer_afm: Optional[str] = None

class DateRangeRequest(BaseModel):
    date_from: str
    date_to: str
    issuer_afm: Optional[str] = None

class AddCredentialsRequest(BaseModel):
    afm: str
    user_id: str
    subscription_key: str
    env: str = "dev"
    country: str = "GR"
    branch: int = 0
    label: str = ""

class SetDefaultAfmRequest(BaseModel):
    afm: str


# ── Endpoints ──

@app.get("/health")
async def health():
    return {"status": "ok", "env": os.environ.get("MYDATA_ENV", "dev")}


# ── Credential Management Endpoints ──

@app.post("/tools/credentials")
async def add_credentials(req: AddCredentialsRequest):
    """Add or update myDATA credentials for an AFM."""
    try:
        cred_store.add(
            afm=req.afm,
            user_id=req.user_id,
            subscription_key=req.subscription_key,
            env=req.env,
            country=req.country,
            branch=req.branch,
            label=req.label,
        )
        return {"status": "ok", "afm": req.afm}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/credentials")
async def list_credentials():
    """List all stored AFMs (no secrets)."""
    try:
        creds = cred_store.list_all()
        return {
            "credentials": [
                {"afm": c["afm"], "label": c["label"], "env": c["env"]}
                for c in creds
            ],
            "default_afm": cred_store.get_default(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tools/credentials/{afm}")
async def remove_credentials(afm: str):
    """Remove credentials for an AFM."""
    try:
        removed = cred_store.remove(afm)
        if not removed:
            raise HTTPException(status_code=404, detail=f"AFM {afm} not found")
        return {"status": "ok", "afm": afm}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/credentials/default")
async def set_default_afm(req: SetDefaultAfmRequest):
    """Set the default AFM for operations."""
    try:
        cred_store.set_default(req.afm)
        return {"status": "ok", "default_afm": req.afm}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Invoice Endpoints ──

@app.post("/tools/send-invoice")
async def send_invoice(req: SendInvoiceRequest):
    """Send an invoice to AADE myDATA."""
    try:
        active_client = _get_client(req.issuer_afm)
        issue_dt = date.fromisoformat(req.issue_date) if req.issue_date else None

        items = [
            {
                "net_value": item.net_value,
                "vat_category": item.vat_category,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "income_classification_type": item.income_classification_type,
                "income_classification_category": item.income_classification_category,
            }
            for item in req.items
        ]

        results = await active_client.send_invoice_simple(
            counterpart_vat=req.counterpart_vat,
            invoice_type=req.invoice_type,
            series=req.series,
            number=req.number,
            items=items,
            payment_method=req.payment_method,
            counterpart_country=req.counterpart_country,
            counterpart_name=req.counterpart_name,
            issue_date=issue_dt,
            currency=req.currency,
        )

        return {
            "results": [
                {
                    "success": r.success,
                    "mark": r.invoice_mark,
                    "uid": r.invoice_uid,
                    "errors": r.errors,
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/cancel-invoice")
async def cancel_invoice(req: CancelInvoiceRequest):
    """Cancel an invoice by MARK."""
    try:
        active_client = _get_client(req.issuer_afm)
        results = await active_client.cancel_invoice(req.mark, req.entity_vat)
        return {
            "results": [
                {
                    "success": r.success,
                    "cancellation_mark": r.cancellation_mark,
                    "errors": r.errors,
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get-invoices")
async def get_invoices(req: GetInvoicesRequest):
    """Retrieve invoices from AADE."""
    try:
        active_client = _get_client(req.issuer_afm)
        if req.direction == "received":
            invoices = await active_client.get_received_invoices(
                req.mark, req.date_from, req.date_to
            )
        else:
            invoices = await active_client.get_sent_invoices(
                req.mark, req.date_from, req.date_to
            )

        return {"invoices": invoices, "count": len(invoices)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/income-summary")
async def income_summary(req: DateRangeRequest):
    """Get income summary for date range."""
    try:
        active_client = _get_client(req.issuer_afm)
        result = await active_client.get_income(req.date_from, req.date_to)
        return {"data": result.decode("utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/expenses-summary")
async def expenses_summary(req: DateRangeRequest):
    """Get expenses summary for date range."""
    try:
        active_client = _get_client(req.issuer_afm)
        result = await active_client.get_expenses(req.date_from, req.date_to)
        return {"data": result.decode("utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/generate-xml")
async def generate_xml(req: SendInvoiceRequest):
    """Generate myDATA XML without sending. Returns XML string."""
    try:
        active_client = _get_client(req.issuer_afm)
        lines = []
        for i, item in enumerate(req.items, 1):
            lines.append(InvoiceLine(
                line_number=i,
                net_value=Decimal(str(item.net_value)),
                vat_category=VatCategory(item.vat_category),
                description=item.description,
                income_classification_type=item.income_classification_type,
                income_classification_category=item.income_classification_category,
            ))

        total_gross = sum(l.gross_value for l in lines)

        invoice = InvoiceData(
            issuer=active_client.issuer,
            counterpart=Party(
                vat_number=req.counterpart_vat,
                country=req.counterpart_country,
                name=req.counterpart_name if req.counterpart_country != "GR" else None,
            ),
            invoice_type=InvoiceType(req.invoice_type),
            series=req.series,
            number=req.number,
            issue_date=date.fromisoformat(req.issue_date) if req.issue_date else date.today(),
            lines=lines,
            payments=[PaymentInfo(
                method=PaymentMethod(req.payment_method),
                amount=total_gross,
            )],
            currency=req.currency,
        )

        xml_bytes = build_invoice_xml(invoice)
        return {"xml": xml_bytes.decode("utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
```

## PM2 Ecosystem Configuration

```javascript
// ecosystem.config.js
// Note: env vars are fallback for single-AFM setups.
// For multi-AFM, use the /tools/credentials endpoints to store per-AFM credentials in SQLite.
module.exports = {
  apps: [
    {
      name: "mydata-api",
      script: "uvicorn",
      args: "mydata_api:app --host 0.0.0.0 --port 8100",
      interpreter: "none",
      cwd: "/path/to/mydata-project",
      env: {
        MYDATA_USER_ID: "your-user-id",       // fallback if no SQLite credentials
        MYDATA_SUBSCRIPTION_KEY: "your-key",
        MYDATA_ENV: "dev",
        ISSUER_VAT: "999999999",
        ISSUER_COUNTRY: "GR",
        ISSUER_BRANCH: "0",
      },
      env_production: {
        MYDATA_ENV: "prod",
      },
    },
  ],
};
```

## Agent HTTP Tool Integration

When the agent runs separately, it calls the FastAPI endpoints:

```python
import httpx

MYDATA_API = "http://localhost:8100"

async def handle_tool_via_http(tool_name: str, tool_input: dict) -> str:
    """Route agent tool calls to the FastAPI server."""
    
    endpoint_map = {
        "send_mydata_invoice": ("POST", "/tools/send-invoice"),
        "cancel_mydata_invoice": ("POST", "/tools/cancel-invoice"),
        "get_mydata_invoices": ("POST", "/tools/get-invoices"),
        "get_mydata_income_summary": ("POST", "/tools/income-summary"),
        "get_mydata_expenses_summary": ("POST", "/tools/expenses-summary"),
        "generate_mydata_xml": ("POST", "/tools/generate-xml"),
        "add_mydata_credentials": ("POST", "/tools/credentials"),
        "list_mydata_credentials": ("GET", "/tools/credentials"),
        "remove_mydata_credentials": ("DELETE", None),  # dynamic path
        "set_default_mydata_afm": ("POST", "/tools/credentials/default"),
    }
    
    entry = endpoint_map.get(tool_name)
    if not entry:
        return f"Unknown tool: {tool_name}"

    method, endpoint = entry

    async with httpx.AsyncClient() as http:
        # Handle dynamic path for remove_mydata_credentials
        if tool_name == "remove_mydata_credentials":
            afm = tool_input.get("afm", "")
            resp = await http.delete(
                f"{MYDATA_API}/tools/credentials/{afm}",
                timeout=30.0,
            )
        elif method == "GET":
            resp = await http.get(
                f"{MYDATA_API}{endpoint}",
                timeout=30.0,
            )
        else:
            resp = await http.post(
                f"{MYDATA_API}{endpoint}",
                json=tool_input,
                timeout=30.0,
            )

        if resp.status_code != 200:
            return f"Error {resp.status_code}: {resp.text}"

        return resp.text
```

## Testing

```bash
# Health check
curl http://localhost:8100/health

# ── Credential Management ──

# Add credentials for an AFM
curl -X POST http://localhost:8100/tools/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "afm": "123456789",
    "user_id": "user-id-from-aade",
    "subscription_key": "subscription-key-from-aade",
    "env": "dev",
    "label": "Εταιρεία Α"
  }'

# Add a second AFM
curl -X POST http://localhost:8100/tools/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "afm": "987654321",
    "user_id": "another-user-id",
    "subscription_key": "another-key",
    "env": "dev",
    "label": "Εταιρεία Β"
  }'

# List all stored AFMs
curl http://localhost:8100/tools/credentials

# Set default AFM
curl -X POST http://localhost:8100/tools/credentials/default \
  -H "Content-Type: application/json" \
  -d '{"afm": "123456789"}'

# Remove credentials
curl -X DELETE http://localhost:8100/tools/credentials/987654321

# ── Invoice Operations ──

# Generate XML (no AADE call)
curl -X POST http://localhost:8100/tools/generate-xml \
  -H "Content-Type: application/json" \
  -d '{
    "counterpart_vat": "012345678",
    "invoice_type": "2.1",
    "series": "TEST",
    "number": 1,
    "items": [{"net_value": 100, "vat_category": 1}],
    "payment_method": 3
  }'

# Generate XML for a specific AFM
curl -X POST http://localhost:8100/tools/generate-xml \
  -H "Content-Type: application/json" \
  -d '{
    "counterpart_vat": "012345678",
    "invoice_type": "2.1",
    "series": "TEST",
    "number": 1,
    "items": [{"net_value": 100, "vat_category": 1}],
    "payment_method": 3,
    "issuer_afm": "987654321"
  }'

# Send invoice (requires valid AADE credentials)
curl -X POST http://localhost:8100/tools/send-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "counterpart_vat": "012345678",
    "invoice_type": "2.1",
    "series": "B",
    "number": 1,
    "items": [
      {"net_value": 500, "vat_category": 1, "description": "Consulting services"}
    ],
    "payment_method": 7
  }'
```
