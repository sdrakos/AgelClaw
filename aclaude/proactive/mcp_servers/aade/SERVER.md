---
name: aade
description: AADE myDATA invoice management + daily accounting reports — send, receive, cancel invoices, manage multi-AFM credentials, and generate Excel accounting reports via the Greek tax authority API
version: 1.1.0
command: python
args: [server.py]
auto_load: false
scope: all
tools:
  - send_invoice
  - get_invoices
  - cancel_invoice
  - income_summary
  - expenses_summary
  - generate_xml
  - add_credentials
  - list_credentials
  - remove_credentials
  - set_default_afm
  - daily_accounting_report
  - configure_accounting
  - accounting_status
  - lookup_afm
  - validate_afm
---

# AADE myDATA MCP Server

AADE myDATA invoice management and daily accounting for AI agents. Supports multi-AFM credential storage via SQLite for accountants and multi-entity businesses.

## Dependencies

```bash
pip install httpx lxml python-dotenv openpyxl
```

## Configuration

Credentials loaded from SQLite (`<project_dir>/data/mydata_credentials.db`) or `.env` fallback. Project dir resolved: `AGELCLAW_HOME` → CWD with config.yaml → `~/.agelclaw/`.

```
MYDATA_USER_ID=your-user-id
MYDATA_SUBSCRIPTION_KEY=your-subscription-key
MYDATA_ENV=dev          # dev or prod
ISSUER_VAT=999999999
ISSUER_COUNTRY=GR
ISSUER_BRANCH=0
```

## Tools

### Invoice Operations
- **send_invoice** -- Send invoice to AADE myDATA. Returns MARK (unique registration number)
- **get_invoices** -- Retrieve sent or received invoices with optional date filters
- **cancel_invoice** -- Cancel an invoice by its MARK number
- **income_summary** -- Get income summary for a date range
- **expenses_summary** -- Get expenses summary for a date range
- **generate_xml** -- Generate myDATA XML without sending (dry run)

### Credential Management (Multi-AFM)
- **add_credentials** -- Store myDATA credentials for an AFM in SQLite
- **list_credentials** -- List all stored AFMs (no secrets shown)
- **remove_credentials** -- Remove credentials for an AFM
- **set_default_afm** -- Set which AFM is used by default when issuer_afm is not specified

### Λογιστική (Accounting)
- **daily_accounting_report** -- Ημερήσια λογιστική αναφορά: ανακτά παραστατικά από ΑΑΔΕ, αποκλείει ήδη επεξεργασμένα (dedup), δημιουργεί Excel (Έσοδα/Έξοδα/Σύνοψη), αποστέλλει email. Idempotent — επαναληπτική εκτέλεση αγνοεί ήδη καταχωρημένα.
- **configure_accounting** -- Ρύθμιση email παραληπτών για ημερήσιες αναφορές ανά ΑΦΜ
- **accounting_status** -- Στατιστικά λογιστικής: σύνολο επεξεργασμένων, τελευταία αναφορά, παραλήπτες
