---
name: aade-mydata-agent
description: "Complete AADE myDATA integration for Python — AI agent tools for sending, receiving, cancelling and classifying invoices via the Greek tax authority REST API. Use this skill whenever the user mentions myDATA, ΑΑΔΕ, Greek invoicing, ηλεκτρονικά τιμολόγια, παραστατικά, MARK, e-invoicing Greece, τιμολόγιο παροχής υπηρεσιών, SendInvoices, RequestDocs, income/expense classification (χαρακτηρισμός εσόδων/εξόδων), or wants to build an AI agent that interacts with the AADE myDATA platform. Also trigger when the user asks about Greek tax compliance automation, myDATA XML generation, invoice submission to AADE, or building tools/bots that manage Greek business invoices programmatically. Covers both test (sandbox) and production environments."
---

# AADE myDATA Agent Integration

## Overview

This skill provides everything needed to build a Python-based AI agent that sends, receives, cancels and classifies invoices through the AADE myDATA REST API — the mandatory electronic invoicing platform for all Greek businesses.

The skill produces two outputs:
1. **Standalone Python module** (`mydata_client.py`) — async HTTP client + XML builder + SQLite credential store for direct API interaction
2. **Agent tool definitions** — ready-to-use tool schemas for Claude Agent SDK, LangChain, or any tool-calling LLM

**Multi-AFM support**: Credentials (MYDATA_USER_ID, MYDATA_SUBSCRIPTION_KEY) are stored per-AFM in SQLite, making it ideal for accountants managing multiple clients or businesses with multiple tax numbers. Single-AFM setups via `.env` are still supported as fallback.

## When to use this skill

- User wants to send invoices to AADE myDATA programmatically
- User wants to retrieve received/transmitted invoices from myDATA
- User wants to build a Telegram/WhatsApp bot or web app that manages Greek invoices
- User asks about myDATA XML format, invoice types, VAT categories, or income/expense classifications
- User needs to automate invoice submission from their ERP, Stripe, or custom system
- User is a **accountant (λογιστής)** managing invoices for multiple clients/AFMs
- User has a business with **multiple AFMs** and needs to switch between them
- User mentions "τιμολόγιο", "ΑΑΔΕ", "myDATA", "MARK", "παραστατικό", or "χαρακτηρισμός"

## Prerequisites

Before writing any code, confirm these with the user:

1. **AADE Credentials** — the user needs `aade-user-id` and `ocp-apim-subscription-key`
   - **Production**: Register at `https://www1.aade.gr/saadeapps2/bookkeeper-web` (requires TAXISnet login)
   - **Test/Sandbox**: Register at `https://mydata-dev-register.azurewebsites.net/` (no TAXISnet needed)
2. **Python 3.9+** with `httpx` and `lxml` installed
3. **Issuer VAT number** (ΑΦΜ) — automatically linked to the credentials during registration

If the user doesn't have credentials yet, guide them through the registration process. For development/testing, always recommend the sandbox environment first.

---

## Architecture

The integration follows a layered architecture designed for AI agent use:

```
User (natural language)
    │
    ▼
AI Agent (Claude SDK / LangChain / custom)
    │  ← Uses tool definitions from this skill
    ▼
FastAPI Tool Server (runs on user's VPS/server)
    │  ← Exposes tools as HTTP endpoints
    ▼
MyDataClient (Python module)
    │  ← Builds XML, handles auth, parses responses
    ▼
AADE myDATA REST API
    (mydatapi.aade.gr or mydata-dev.azure-api.net)
```

For simpler setups (no FastAPI), the agent can call the MyDataClient directly as a Python function.

---

## Quick Start

### Step 1: Install dependencies

```bash
pip install httpx lxml python-dotenv
```

### Step 2: Set up credentials

**Option A: Single AFM (via .env)**

Create `.env` file:
```
MYDATA_USER_ID=your-username
MYDATA_SUBSCRIPTION_KEY=your-subscription-key
MYDATA_ENV=dev
# MYDATA_ENV=prod  # for production
ISSUER_VAT=999999999
ISSUER_COUNTRY=GR
ISSUER_BRANCH=0
```

**Option B: Multiple AFMs (via SQLite — recommended for accountants)**

```python
from mydata_client import CredentialStore

store = CredentialStore()  # auto-creates ~/.agelclaw/data/mydata_credentials.db

# Add credentials per AFM
store.add("999999999", "user1", "key1", env="dev", label="Εταιρεία Α")
store.add("888888888", "user2", "key2", env="dev", label="Εταιρεία Β")

# Set a default AFM (optional)
store.set_default("999999999")
```

Or use the agent tool: `add_mydata_credentials(afm="999999999", user_id="user1", subscription_key="key1", label="Εταιρεία Α")`

### Step 3: Generate the client module

Run `scripts/generate_client.py` to produce a complete `mydata_client.py` module:

```bash
python scripts/generate_client.py
```

Or read `references/client_module.md` for the full implementation and copy it directly.

### Step 4: Generate agent tool definitions

Read `references/agent_tools.md` for ready-to-use tool schemas compatible with Claude Agent SDK.

---

## API Reference

### Environments

| Environment | Base URL | Registration |
|------------|----------|-------------|
| **Production** | `https://mydatapi.aade.gr/myDATA/` | TAXISnet login required |
| **Test/Dev** | `https://mydata-dev.azure-api.net/` | Free registration |
| **Dev Portal** | `https://mydata-dev.portal.azure-api.net/` | API docs + live testing |

### Authentication

Every request requires two headers:

```
aade-user-id: {username}
ocp-apim-subscription-key: {subscription_key}
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/SendInvoices` | Submit one or more invoices (XML body) |
| POST | `/CancelInvoice?mark={mark}` | Cancel invoice by MARK |
| GET | `/RequestDocs?mark={mark}` | Retrieve received invoices |
| GET | `/RequestTransmittedDocs?mark={mark}` | Retrieve sent invoices |
| GET | `/RequestMyIncome?dateFrom=&dateTo=` | Income summary for period |
| GET | `/RequestMyExpenses?dateFrom=&dateTo=` | Expenses summary for period |
| POST | `/SendIncomeClassification` | Classify income on invoices |
| POST | `/SendExpensesClassification` | Classify expenses on invoices |

### Response Format

All submission endpoints return `ResponseDoc` XML:

```xml
<ResponseDoc>
  <response>
    <index>1</index>
    <statusCode>Success</statusCode>
    <invoiceUid>...</invoiceUid>
    <invoiceMark>400012345</invoiceMark>
  </response>
</ResponseDoc>
```

Status codes: `Success`, `ValidationError`, `TechnicalError`, `XMLSyntaxError`

---

## Invoice Types (most common)

For full reference, read `references/invoice_types.md`.

| Code | Greek Name | English | Use Case |
|------|-----------|---------|----------|
| 1.1 | Τιμολόγιο Πώλησης | Sales Invoice | Selling goods |
| 1.6 | Τιμολόγιο Αυτοπαράδοσης | Self-supply Invoice | Internal use |
| 2.1 | Τιμολόγιο Παροχής Υπηρεσιών | Services Invoice | Freelancers, consulting |
| 2.4 | Συμβόλαιο - Έσοδο | Contract - Income | Recurring services |
| 3.1 | Τίτλος Κτήσης (μη υπόχρεος) | Title of Acquisition | Paying non-VAT individuals |
| 5.1 | Πιστωτικό Τιμολόγιο | Credit Note (correlated) | Refund linked to invoice |
| 5.2 | Πιστωτικό Τιμολόγιο | Credit Note (uncorrelated) | Standalone refund |
| 11.1 | ΑΛΠ - Απόδειξη Λιανικής | Retail Receipt | B2C sales |
| 11.2 | ΑΠΥ - Απόδειξη Παροχής Υπηρεσιών | Services Receipt | B2C services |

## VAT Categories

| Code | Rate | Description |
|------|------|-------------|
| 1 | 24% | Standard rate (κανονικός) |
| 2 | 13% | Reduced rate (μειωμένος) |
| 3 | 6% | Super-reduced (υπερμειωμένος) |
| 4 | 17% | Island standard (νησιωτικός κανονικός) |
| 5 | 9% | Island reduced (νησιωτικός μειωμένος) |
| 6 | 4% | Island super-reduced (νησιωτικός υπερμειωμένος) |
| 7 | 0% | Exempt with right to deduction |
| 8 | - | Records without VAT |

## Payment Methods

| Code | Method |
|------|--------|
| 1 | Domestic bank account |
| 2 | Foreign bank account |
| 3 | Cash |
| 4 | Cheque |
| 5 | Credit/Debit on credit |
| 6 | Web banking |
| 7 | POS / e-POS |

---

## XML Structure

The XML element order is critical — AADE will reject documents with incorrect field ordering. Always use the builder functions from this skill rather than constructing XML manually.

### Invoice XML skeleton

```xml
<?xml version="1.0" encoding="UTF-8"?>
<InvoicesDoc xmlns="http://www.aade.gr/myDATA/invoice/v1.0"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xmlns:icls="http://www.aade.gr/myDATA/incomeClassificaton/v1.0"
             xmlns:ecls="http://www.aade.gr/myDATA/expensesClassificaton/v1.0">
  <invoice>
    <issuer>
      <vatNumber>999999999</vatNumber>
      <country>GR</country>
      <branch>0</branch>
    </issuer>
    <counterpart>
      <vatNumber>012345678</vatNumber>
      <country>GR</country>
      <branch>0</branch>
    </counterpart>
    <invoiceHeader>
      <series>A</series>
      <aa>1</aa>
      <issueDate>2026-03-06</issueDate>
      <invoiceType>2.1</invoiceType>
      <currency>EUR</currency>
    </invoiceHeader>
    <paymentMethods>
      <paymentMethodDetails>
        <type>3</type>
        <amount>1240.00</amount>
        <paymentMethodInfo>Cash payment</paymentMethodInfo>
      </paymentMethodDetails>
    </paymentMethods>
    <invoiceDetails>
      <lineNumber>1</lineNumber>
      <netValue>1000.00</netValue>
      <vatCategory>1</vatCategory>
      <vatAmount>240.00</vatAmount>
      <incomeClassification>
        <icls:classificationType>E3_561_001</icls:classificationType>
        <icls:classificationCategory>category1_1</icls:classificationCategory>
        <icls:amount>1000.00</icls:amount>
      </incomeClassification>
    </invoiceDetails>
    <invoiceSummary>
      <totalNetValue>1000.00</totalNetValue>
      <totalVatAmount>240.00</totalVatAmount>
      <totalWithheldAmount>0.00</totalWithheldAmount>
      <totalFeesAmount>0.00</totalFeesAmount>
      <totalStampDutyAmount>0.00</totalStampDutyAmount>
      <totalOtherTaxesAmount>0.00</totalOtherTaxesAmount>
      <totalDeductionsAmount>0.00</totalDeductionsAmount>
      <totalGrossValue>1240.00</totalGrossValue>
      <incomeClassification>
        <icls:classificationType>E3_561_001</icls:classificationType>
        <icls:classificationCategory>category1_1</icls:classificationCategory>
        <icls:amount>1000.00</icls:amount>
      </incomeClassification>
    </invoiceSummary>
  </invoice>
</InvoicesDoc>
```

---

## Income Classification Types (most common)

For services invoices (type 2.1), use these combinations:

| Classification Type | Category | When to use |
|---------------------|----------|-------------|
| E3_561_001 | category1_1 | Sales of goods, wholesale |
| E3_561_002 | category1_2 | Sales of goods on behalf of third parties |
| E3_561_003 | category1_3 | Sales of services (ΤΠΥ revenue) |
| E3_561_007 | category1_7 | Sales of goods for third-party account |
| E3_563 | category1_3 | Other ordinary income |
| E3_570 | category1_95 | Extraordinary income |
| E3_595 | category1_95 | Self-delivery/self-use expenses |

For the complete classification table, read `references/invoice_types.md`.

---

## Deployment Patterns

### Pattern A: Agent SDK Direct (simplest)

The Claude Agent SDK calls Python functions directly:

```python
import anthropic
from mydata_client import MyDataClient

# Multi-AFM: tries SQLite DB first, falls back to .env
client = MyDataClient.from_db_or_env()

# Define as tool
tools = [...]  # from references/agent_tools.md (includes credential management tools)

# In the tool handler:
async def handle_tool(name, input):
    if name == "send_invoice":
        result = await client.send_invoice(**input)
        return str(result)
```

### Pattern B: FastAPI + PM2 (production)

Wrap the client in a FastAPI server, managed by PM2:

```bash
pm2 start "uvicorn mydata_api:app --host 0.0.0.0 --port 8100" --name mydata-api
```

The agent calls HTTP endpoints. Read `references/fastapi_server.md` for the complete server code.

### Pattern C: Telegram Bot + Agent (end-user facing)

Combine with a Telegram bot for natural language invoice management:

```
User: "Στείλε ΤΠΥ 500€ στον Παπαδόπουλο ΑΦΜ 123456789"
Bot → Agent → MyDataClient → AADE → MARK returned
Bot: "Τιμολόγιο εστάλη. MARK: 400012345"
```

Multi-AFM example:
```
User: "Στείλε τιμολόγιο από την Εταιρεία Β (ΑΦΜ 888888888) στον 123456789 για 1000€"
Bot → Agent → MyDataClient.from_db("888888888") → AADE
Bot: "Τιμολόγιο εστάλη από 888888888. MARK: 400012346"
```

---

## Error Handling

Common AADE errors and their solutions:

| Error Code | Message | Solution |
|-----------|---------|----------|
| 101 | XML syntax error | Check XML element order — AADE is strict about ordering |
| 102 | Validation error | Check required fields (issuer VAT, invoice type, amounts) |
| 201 | Invalid VAT number | Verify counterpart VAT exists in TAXISnet |
| 301 | Duplicate invoice | Same series+aa already submitted — use different number |
| 401 | Authentication error | Check aade-user-id and subscription key |
| 501 | Service unavailable | AADE is down — implement retry with exponential backoff |

Always wrap API calls in try/except and implement retry logic for 5xx errors.

---

## ΑΦΜ Lookup & Auto-Classification

The agent can automatically determine the correct invoice type and income classification by looking up the counterpart's ΑΦΜ. The flow:

```
ΑΦΜ → AADE SOAP lookup → ΚΑΔ (activity code) → mapping → E3 code + category
```

This requires separate credentials from myDATA (GSIS RgWsPublic2 service). Read `references/afm_lookup.md` for the complete implementation including:
- Local ΑΦΜ check digit validation (no API call needed)
- AADE SOAP client for business details (name, address, KAD, DOY, legal status)
- KAD-to-myDATA mapping table covering all 2-digit sectors
- SQLite cache so repeated lookups are instant
- Manual business entry for when SOAP credentials aren't available
- 5 additional agent tools: `lookup_afm`, `validate_afm`, `get_mydata_classification`, `add_business_manually`, `list_cached_businesses`

The KAD mapping is the key intelligence — it converts a 2-digit sector code into the correct invoice type (1.1 for goods, 2.1 for services), E3 classification, and default VAT category. This eliminates the need for the user to know anything about myDATA codes.

---

## Reference Files

Read these files for complete implementations:

- **`references/client_module.md`** — Complete `mydata_client.py` Python module with async HTTP client, XML builder, response parser, SQLite `CredentialStore` for multi-AFM support, and all helper functions
- **`references/agent_tools.md`** — Tool definitions for Claude Agent SDK with input schemas, descriptions, handler implementations, and 4 credential management tools (add/list/remove/set_default)
- **`references/invoice_types.md`** — Complete tables of all invoice types, VAT categories, withholding taxes, income/expense classification codes, payment methods, and measurement units
- **`references/fastapi_server.md`** — Production-ready FastAPI server wrapping the myDATA client as HTTP endpoints for agent tool use
- **`references/afm_lookup.md`** — ΑΦΜ validation, AADE SOAP lookup client, KAD→myDATA mapping table (all sectors), SQLite cache, and agent tool definitions for auto-classification

---

## Important Notes

1. **XML field order matters** — AADE validates not just the content but the order of XML elements. Always use the builder functions.
2. **MARK is your receipt** — Every successful submission returns a MARK (unique registration number). Store it — you need it for cancellations and classifications.
3. **Test first** — Always develop against the sandbox (`mydata-dev.azure-api.net`) before switching to production.
4. **Rate limiting** — AADE doesn't document rate limits, but implement reasonable delays (100ms between calls) for bulk submissions.
5. **Mandatory from March 2026** — e-invoicing through myDATA is mandatory for businesses with turnover >€1M from March 2026, and for all businesses from October 2026.
6. **Income classification is mandatory** — When sending invoices, you must include income classifications (icls) in the invoice details and summary.
7. **Multi-AFM credentials** — Stored in SQLite at `~/.agelclaw/data/mydata_credentials.db`. Each AFM has its own `user_id`, `subscription_key`, and `env` (dev/prod). The `CredentialStore` auto-creates the DB on first use. All existing tools accept optional `issuer_afm` parameter to switch between AFMs.
8. **Backward compatibility** — Single-AFM setups via `.env` still work. `MyDataClient.from_db_or_env()` tries SQLite first (default AFM), falls back to `.env`.
