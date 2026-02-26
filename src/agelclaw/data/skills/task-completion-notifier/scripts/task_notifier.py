#!/usr/bin/env python3
"""
Task Completion Notifier - Sends email when tasks complete
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import msal
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install msal requests python-dotenv")
    sys.exit(1)

# Load .env
try:
    from agelclaw.project import get_env_path
    _env_path = get_env_path()
except ImportError:
    _env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET")
TENANT_ID = os.getenv("OUTLOOK_TENANT_ID")
USER_EMAIL = os.getenv("OUTLOOK_USER_EMAIL", "sdrakos@agel.ai")
RECIPIENT = "stefanos.drakos@gmail.com"

def get_access_token():
    """Get OAuth2 token for Microsoft Graph API"""
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET,
    )
    scopes = ["https://graph.microsoft.com/.default"]
    result = app.acquire_token_silent(scopes, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=scopes)
    if "access_token" in result:
        return result["access_token"]
    raise Exception(f"Token error: {result.get('error_description', result)}")

def send_notification(task_id, task_title, status, result, duration=None):
    """Send email notification about task completion"""
    token = get_access_token()
    
    # Create email body
    status_emoji = "✅" if status == "completed" else "❌"
    status_text = "ΟΛΟΚΛΗΡΩΘΗΚΕ" if status == "completed" else "ΑΠΟΤΥΧΙΑ"
    
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
            .task-box {{ background: white; padding: 15px; border-left: 4px solid #667eea; 
                         margin: 15px 0; border-radius: 4px; }}
            .status {{ font-size: 24px; font-weight: bold; }}
            .footer {{ color: #999; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>{status_emoji} Ειδοποίηση Εργασίας</h2>
        </div>
        <div class="content">
            <div class="status" style="color: {'#28a745' if status == 'completed' else '#dc3545'};">
                {status_text}
            </div>
            
            <div class="task-box">
                <h3>📋 {task_title}</h3>
                <p><strong>ID:</strong> #{task_id}</p>
                <p><strong>Κατάσταση:</strong> {status_text}</p>
                {f'<p><strong>Διάρκεια:</strong> {duration}s</p>' if duration else ''}
                <p><strong>Ώρα:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="task-box">
                <h4>Αποτέλεσμα:</h4>
                <p>{result}</p>
            </div>
            
            <div class="footer">
                <p>🤖 Αυτόματη ειδοποίηση από Agent System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Send via Outlook API
    endpoint = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    email_data = {
        "message": {
            "subject": f"{status_emoji} Εργασία: {task_title}",
            "body": {
                "contentType": "HTML",
                "content": html_body
            },
            "toRecipients": [
                {"emailAddress": {"address": RECIPIENT}}
            ]
        }
    }
    
    response = requests.post(endpoint, headers=headers, json=email_data)
    response.raise_for_status()
    print(f"✅ Ειδοποίηση στάλθηκε στο {RECIPIENT}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-title", required=True)
    parser.add_argument("--status", required=True, choices=["completed", "failed"])
    parser.add_argument("--result", required=True)
    parser.add_argument("--duration", type=float, default=None)
    
    args = parser.parse_args()
    send_notification(args.task_id, args.task_title, args.status, args.result, args.duration)
