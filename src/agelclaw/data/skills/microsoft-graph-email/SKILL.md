---
name: microsoft-graph-email
description: >-
  Read incoming and sent emails from Microsoft Graph API for sdrakos@agel.ai.
  Credentials are loaded automatically from config.yaml (outlook_client_id,
  outlook_client_secret, outlook_tenant_id, outlook_user_email).
---

## Purpose

Read, search, and list emails from the sdrakos@agel.ai Microsoft 365 mailbox
using the Microsoft Graph API with application (client_credentials) auth flow.

## Prerequisites

- `msal` and `requests` Python packages (already in requirements.txt)
- Outlook credentials configured in `aclaude/proactive/config.yaml`
- Azure AD app registration with `Mail.Read` application permission granted

## Available Scripts

### `read_emails.py`

Read emails from Inbox or Sent Items.

```bash
# Latest 10 inbox emails (default)
python scripts/read_emails.py

# Latest 5 sent emails
python scripts/read_emails.py --folder sent --count 5

# Search inbox for keyword
python scripts/read_emails.py --search "invoice"

# Read a specific email by ID
python scripts/read_emails.py --id AAMkAG...

# Show unread only
python scripts/read_emails.py --unread
```

**Output**: JSON with subject, from, to, date, body preview, and read status.

## Usage from Agent

When the user asks to check email, read messages, or search mail:

```bash
python "C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\.Claude\Skills\microsoft-graph-email\scripts\read_emails.py" --count 10
```

## Credentials

All credentials are loaded automatically from `aclaude/proactive/config.yaml`.
Do NOT ask the user for credentials — they are already configured.
