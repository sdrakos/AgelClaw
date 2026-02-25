#!/usr/bin/env python3
"""
Microsoft Graph Email Reader
=============================
Reads emails from sdrakos@agel.ai via Microsoft Graph API.
Credentials loaded from aclaude/proactive/config.yaml automatically.

Usage:
    python read_emails.py                          # Latest 10 inbox emails
    python read_emails.py --folder sent --count 5  # Latest 5 sent emails
    python read_emails.py --search "invoice"       # Search inbox
    python read_emails.py --id AAMkAG...           # Read specific email
    python read_emails.py --unread                 # Unread only
"""

import argparse
import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding (cp1253 can't handle all Unicode)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add proactive dir to path so we can import config
SKILL_DIR = Path(__file__).resolve().parent.parent
PROACTIVE_DIR = SKILL_DIR.parent.parent.parent / "proactive"
sys.path.insert(0, str(PROACTIVE_DIR))

try:
    import msal
    import requests
except ImportError as e:
    print(json.dumps({"error": f"Missing package: {e}. Run: pip install msal requests"}))
    sys.exit(1)


GRAPH_BASE = "https://graph.microsoft.com/v1.0"

FOLDER_MAP = {
    "inbox": "inbox",
    "sent": "sentitems",
    "drafts": "drafts",
    "deleted": "deleteditems",
    "junk": "junkemail",
    "archive": "archive",
}


def load_credentials() -> dict:
    """Load Outlook credentials from config.yaml."""
    try:
        from core.config import load_config
        cfg = load_config()
    except Exception:
        # Fallback: load YAML directly
        import yaml
        config_path = PROACTIVE_DIR / "config.yaml"
        if not config_path.exists():
            print(json.dumps({"error": f"Config not found: {config_path}"}))
            sys.exit(1)
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    client_id = cfg.get("outlook_client_id", "")
    client_secret = cfg.get("outlook_client_secret", "")
    tenant_id = cfg.get("outlook_tenant_id", "")
    user_email = cfg.get("outlook_user_email", "")

    if not all([client_id, client_secret, tenant_id, user_email]):
        missing = []
        if not client_id: missing.append("outlook_client_id")
        if not client_secret: missing.append("outlook_client_secret")
        if not tenant_id: missing.append("outlook_tenant_id")
        if not user_email: missing.append("outlook_user_email")
        print(json.dumps({"error": f"Missing credentials in config.yaml: {', '.join(missing)}"}))
        sys.exit(1)

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "user_email": user_email,
    }


def get_access_token(creds: dict) -> str:
    """Get access token using MSAL client credentials flow."""
    authority = f"https://login.microsoftonline.com/{creds['tenant_id']}"
    app = msal.ConfidentialClientApplication(
        creds["client_id"],
        authority=authority,
        client_credential=creds["client_secret"],
    )

    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" not in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        print(json.dumps({"error": f"Auth failed: {error_desc}"}))
        sys.exit(1)

    return result["access_token"]


def list_emails(token: str, user_email: str, folder: str = "inbox",
                count: int = 10, search: str = None, unread_only: bool = False) -> list:
    """List emails from a folder."""
    folder_id = FOLDER_MAP.get(folder.lower(), folder)
    url = f"{GRAPH_BASE}/users/{user_email}/mailFolders/{folder_id}/messages"

    params = {
        "$top": count,
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead,hasAttachments,importance",
    }

    if search:
        params["$search"] = f'"{search}"'

    if unread_only:
        params["$filter"] = "isRead eq false"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        return [{"error": f"API error {resp.status_code}: {resp.text[:500]}"}]

    data = resp.json()
    messages = data.get("value", [])

    results = []
    for msg in messages:
        from_addr = ""
        if msg.get("from", {}).get("emailAddress"):
            ea = msg["from"]["emailAddress"]
            from_addr = f"{ea.get('name', '')} <{ea.get('address', '')}>"

        to_addrs = []
        for r in msg.get("toRecipients", []):
            ea = r.get("emailAddress", {})
            to_addrs.append(f"{ea.get('name', '')} <{ea.get('address', '')}>")

        results.append({
            "id": msg.get("id", ""),
            "subject": msg.get("subject", "(no subject)"),
            "from": from_addr,
            "to": ", ".join(to_addrs),
            "date": msg.get("receivedDateTime", ""),
            "preview": msg.get("bodyPreview", "")[:200],
            "is_read": msg.get("isRead", False),
            "has_attachments": msg.get("hasAttachments", False),
            "importance": msg.get("importance", "normal"),
        })

    return results


def read_email_by_id(token: str, user_email: str, message_id: str) -> dict:
    """Read a specific email by ID."""
    url = f"{GRAPH_BASE}/users/{user_email}/messages/{message_id}"

    params = {
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,isRead,hasAttachments,importance",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code != 200:
        return {"error": f"API error {resp.status_code}: {resp.text[:500]}"}

    msg = resp.json()

    from_addr = ""
    if msg.get("from", {}).get("emailAddress"):
        ea = msg["from"]["emailAddress"]
        from_addr = f"{ea.get('name', '')} <{ea.get('address', '')}>"

    to_addrs = []
    for r in msg.get("toRecipients", []):
        ea = r.get("emailAddress", {})
        to_addrs.append(f"{ea.get('name', '')} <{ea.get('address', '')}>")

    cc_addrs = []
    for r in msg.get("ccRecipients", []):
        ea = r.get("emailAddress", {})
        cc_addrs.append(f"{ea.get('name', '')} <{ea.get('address', '')}>")

    body = msg.get("body", {})
    body_content = body.get("content", "")
    body_type = body.get("contentType", "text")

    # Strip HTML tags for readability if HTML
    if body_type.lower() == "html":
        import re
        body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL)
        body_content = re.sub(r'<[^>]+>', ' ', body_content)
        body_content = re.sub(r'\s+', ' ', body_content).strip()

    return {
        "id": msg.get("id", ""),
        "subject": msg.get("subject", "(no subject)"),
        "from": from_addr,
        "to": ", ".join(to_addrs),
        "cc": ", ".join(cc_addrs) if cc_addrs else "",
        "date": msg.get("receivedDateTime", ""),
        "body": body_content[:5000],
        "is_read": msg.get("isRead", False),
        "has_attachments": msg.get("hasAttachments", False),
        "importance": msg.get("importance", "normal"),
    }


def main():
    parser = argparse.ArgumentParser(description="Read emails via Microsoft Graph API")
    parser.add_argument("--folder", default="inbox", help="Mail folder: inbox, sent, drafts, deleted, junk, archive")
    parser.add_argument("--count", type=int, default=10, help="Number of emails to fetch (default: 10)")
    parser.add_argument("--search", default=None, help="Search query string")
    parser.add_argument("--id", default=None, help="Read a specific email by message ID")
    parser.add_argument("--unread", action="store_true", help="Show unread emails only")
    args = parser.parse_args()

    creds = load_credentials()
    token = get_access_token(creds)

    if args.id:
        result = read_email_by_id(token, creds["user_email"], args.id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        results = list_emails(
            token, creds["user_email"],
            folder=args.folder,
            count=args.count,
            search=args.search,
            unread_only=args.unread,
        )
        print(json.dumps({
            "folder": args.folder,
            "count": len(results),
            "emails": results,
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
