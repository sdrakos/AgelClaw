---
name: outlook-email-digest
description: >-
  Automated Outlook email reading, AI summarization, and Gmail delivery
---

# Outlook Email Digest Automation

## Purpose
Automatically reads emails from Outlook every morning, creates an AI-powered summary using OpenAI GPT-4.1-mini, and sends it via Outlook to stefanos.drakos@gmail.com.

## Features
✅ Connects to Outlook via Microsoft Graph API
✅ Fetches emails from last 24 hours
✅ Creates AI-powered summary in Greek (categories: ΕΠΕΙΓΟΝ/ΣΗΜΑΝΤΙΚΑ/FYI)
✅ Sends via Outlook (not Gmail - no SMTP needed!)
✅ Scheduled to run daily at 1:15 AM
✅ Beautiful HTML email formatting
✅ Backup HTML files saved locally

## Setup Completed
✅ All dependencies installed (msal, requests, openai, schedule)
✅ Credentials configured
✅ OpenAI API key configured (GPT-4.1-mini)
✅ Email recipient: stefanos.drakos@gmail.com
✅ Schedule time: 1:15 AM daily
✅ Tested and working - email sent successfully!

## Configuration
- CLIENT_ID: 9a5606f8-b532-493c-aa37-3a4ec11378b1
- TENANT_ID: 661ad5b1-4b06-4c63-9bc0-70019b3bee46
- USER_EMAIL: sdrakos@agel.ai (source)
- EMAIL_RECIPIENT: stefanos.drakos@gmail.com
- OPENAI_MODEL: gpt-4.1-mini
- SCHEDULE_TIME: 01:15 (1:15 AM)

## Usage

### Run Once (Test):
```bash
cd C:/Users/Στέφανος/agel_openai/AGENTI_SDK/aclaude/proactive
python outlook_digest.py --once
```

### Run Scheduled Service (Background):
```bash
# Option 1: Run in terminal (keeps running)
python outlook_digest.py --schedule --time 01:15

# Option 2: Use batch file
start_digest_service.bat

# Option 3: Windows Task Scheduler (created)
create_task.bat  # Creates scheduled task
```

## Files Created
- `outlook_digest.py` - Main script
- `run_outlook_digest.bat` - Single run wrapper
- `start_digest_service.bat` - Background service
- `create_task.bat` - Windows Task Scheduler setup
- `setup_scheduled_task.ps1` - PowerShell task setup
- `digest_YYYYMMDD_HHMMSS.html` - Backup files

## Test Results
✅ Tested on 2026-02-15 00:49
✅ Authentication: SUCCESS
✅ Email fetching: SUCCESS (6 emails)
✅ AI Summary: SUCCESS (GPT-4.1-mini in Greek)
✅ Email sending: SUCCESS (via Outlook API)
✅ Backup file: SUCCESS

## How It Works
1. Authenticates with Microsoft Graph API (OAuth2 Client Credentials)
2. Fetches emails from sdrakos@agel.ai (last 24 hours)
3. Sends email data to OpenAI GPT-4.1-mini
4. Creates categorized summary in Greek
5. Formats as beautiful HTML email
6. Sends via Outlook API to stefanos.drakos@gmail.com
7. Saves backup HTML file locally
8. Runs daily at 1:15 AM

## Status
🟢 FULLY OPERATIONAL - Ready for production use!
