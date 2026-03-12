"""Send emails via Microsoft Graph API."""
import base64
import json
from pathlib import Path
import msal
import requests
from config import OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, OUTLOOK_TENANT_ID, OUTLOOK_USER_EMAIL

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_access_token() -> str:
    app = msal.ConfidentialClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
        client_credential=OUTLOOK_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")
    return result["access_token"]


def send_email(to_addresses: list[str], subject: str, body: str,
               attachments: list[str] | None = None,
               content_type: str = "HTML") -> dict:
    token = get_access_token()
    message = {
        "subject": subject,
        "body": {"contentType": content_type, "content": body},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to_addresses],
    }
    if attachments:
        message["attachments"] = []
        for fpath in attachments:
            p = Path(fpath)
            with open(p, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            message["attachments"].append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": p.name,
                "contentBytes": content,
            })
    resp = requests.post(
        f"{GRAPH_BASE}/users/{OUTLOOK_USER_EMAIL}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"message": message, "saveToSentItems": True},
    )
    if resp.status_code == 202:
        return {"success": True, "message": f"Email sent to {', '.join(to_addresses)}"}
    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
