---
name: aade-accounting
description: >-
  Λογιστική αναφορά AADE myDATA — Excel (Έσοδα/Έξοδα/Σύνοψη) + email.
  Για ημερήσια, μηνιαία ή ετήσια συγκεντρωτική κατάσταση παραστατικών.
provider: auto
task_type: script
command: "python mcp_servers/aade/run_report.py --env prod --force"
timeout: 300
max_retries: 1
---

# AADE Accounting Report — Direct Script Execution

Τρέχει ΑΠΕΥΘΕΙΑΣ ως subprocess (task_type: script).
Δεν χρησιμοποιεί AI agent — εκτελεί μόνο το Python script.

## Τι Κάνει
1. Φέρνει όλα τα παραστατικά (sent + received) από AADE myDATA API
2. Δημιουργεί Excel με 3 sheets: Έσοδα, Έξοδα, Σύνοψη
3. Στέλνει email με attachment μέσω Microsoft Graph API (Outlook)
4. Output: JSON με totals + xlsx_path + email_result

## CLI Παράμετροι
- `--afm <AFM>` — ΑΦΜ (υποχρεωτικό στο task description)
- `--date-from YYYY-MM-DD` — Αρχή περιόδου
- `--date-to YYYY-MM-DD` — Τέλος περιόδου
- `--env dev|prod` — Περιβάλλον AADE (default: prod στο command)
- `--force` — Συμπερίληψη ΟΛΩΝ των παραστατικών (default: ναι στο command)
- `--no-email` — Χωρίς email
- `--email-to EMAIL` — Override παραλήπτη

## Παραδείγματα Task Description
- `--afm 101660691 --date-from 2024-01-01 --date-to 2026-03-07`
- `--afm 101660691` (σήμερα μόνο)
- `--afm 101660691 --date-from 2026-03-01 --no-email`

## Email Configuration
- Παραλήπτες ρυθμίζονται μέσω `mcp__aade__configure_accounting(afm, email_recipients)`
- Αποστολέας: Outlook μέσω Microsoft Graph API (OAuth2/MSAL)
- Credentials: Στο .env (OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, OUTLOOK_TENANT_ID, OUTLOOK_USER_EMAIL)
