#!/usr/bin/env python3
"""
Microsoft Graph Email Sender
=============================
Sends emails from sdrakos@agel.ai via Microsoft Graph API.
Credentials loaded from aclaude/proactive/config.yaml automatically.

Usage:
    python send_email.py --to "email@example.com" --subject "Subject" --body "Body text"
    python send_email.py --to "email@example.com" --subject "Subject" --html-file "report.html"
    python send_email.py --to "a@x.com,b@y.com" --subject "Subject" --body "Body" --cc "c@z.com"
"""

import argparse
import base64
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


def send_email(token: str, user_email: str, to_addresses: list, subject: str,
               body: str, content_type: str = "HTML", cc_addresses: list = None,
               bcc_addresses: list = None, importance: str = "normal", attachments: list = None) -> dict:
    """Send an email via Microsoft Graph API."""
    url = f"{GRAPH_BASE}/users/{user_email}/sendMail"

    # Build recipient lists
    to_recipients = [{"emailAddress": {"address": addr.strip()}} for addr in to_addresses]
    cc_recipients = [{"emailAddress": {"address": addr.strip()}} for addr in (cc_addresses or [])] if cc_addresses else []
    bcc_recipients = [{"emailAddress": {"address": addr.strip()}} for addr in (bcc_addresses or [])] if bcc_addresses else []

    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": content_type,
                "content": body,
            },
            "toRecipients": to_recipients,
            "importance": importance,
        },
        "saveToSentItems": True,
    }

    if cc_recipients:
        message["message"]["ccRecipients"] = cc_recipients
    if bcc_recipients:
        message["message"]["bccRecipients"] = bcc_recipients

    # Add attachments if provided
    if attachments:
        attachment_list = []
        for file_path in attachments:
            path = Path(file_path)
            if not path.exists():
                print(json.dumps({"error": f"Attachment not found: {file_path}"}))
                sys.exit(1)

            with open(path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")

            attachment_list.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": path.name,
                "contentBytes": content,
            })

        message["message"]["attachments"] = attachment_list

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, headers=headers, json=message, timeout=30)

    if resp.status_code == 202:
        return {
            "success": True,
            "message": f"Email sent successfully to {', '.join(to_addresses)}",
            "subject": subject,
            "from": user_email,
            "to": to_addresses,
            "cc": cc_addresses or [],
        }
    else:
        return {
            "success": False,
            "error": f"API error {resp.status_code}: {resp.text[:500]}",
        }


def main():
    parser = argparse.ArgumentParser(description="Send emails via Microsoft Graph API")
    parser.add_argument("--to", required=True, help="Recipient email(s), comma-separated")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", default=None, help="Email body (plain text or HTML)")
    parser.add_argument("--html-file", default=None, help="Read HTML body from file")
    parser.add_argument("--text-file", default=None, help="Read plain text body from file")
    parser.add_argument("--cc", default=None, help="CC recipient(s), comma-separated")
    parser.add_argument("--bcc", default=None, help="BCC recipient(s), comma-separated")
    parser.add_argument("--importance", default="normal", choices=["low", "normal", "high"], help="Email importance")
    parser.add_argument("--attachment", dest="attachments", action="append", help="Attachment file path (can be used multiple times)")
    args = parser.parse_args()

    # Determine body content and type
    if args.html_file:
        html_path = Path(args.html_file)
        if not html_path.is_absolute():
            html_path = PROACTIVE_DIR / args.html_file
        if not html_path.exists():
            print(json.dumps({"error": f"HTML file not found: {html_path}"}))
            sys.exit(1)
        with open(html_path, "r", encoding="utf-8") as f:
            body = f.read()
        content_type = "HTML"
    elif args.text_file:
        text_path = Path(args.text_file)
        if not text_path.is_absolute():
            text_path = PROACTIVE_DIR / args.text_file
        if not text_path.exists():
            print(json.dumps({"error": f"Text file not found: {text_path}"}))
            sys.exit(1)
        with open(text_path, "r", encoding="utf-8") as f:
            body = f.read()
        content_type = "Text"
    elif args.body:
        body = args.body
        # Detect if body looks like HTML
        content_type = "HTML" if "<" in body and ">" in body else "Text"
    else:
        print(json.dumps({"error": "Must provide --body, --html-file, or --text-file"}))
        sys.exit(1)

    # Parse addresses
    to_addresses = [addr.strip() for addr in args.to.split(",")]
    cc_addresses = [addr.strip() for addr in args.cc.split(",")] if args.cc else None
    bcc_addresses = [addr.strip() for addr in args.bcc.split(",")] if args.bcc else None

    creds = load_credentials()
    token = get_access_token(creds)

    result = send_email(
        token, creds["user_email"],
        to_addresses=to_addresses,
        subject=args.subject,
        body=body,
        content_type=content_type,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        importance=args.importance,
        attachments=args.attachments,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
