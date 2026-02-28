---
name: task-completion-notifier
description: >-
  Sends email notifications when scheduled tasks complete
---

# Task Completion Notifier

## Purpose
Automatically sends email notification to stefanos.drakos@gmail.com when any scheduled task completes (success or failure).

## Features
✅ Monitors task completion via daemon hooks
✅ Sends email with task details (title, result, duration)
✅ Uses Outlook API for sending
✅ Greek language notifications
✅ Success/Failure status indicators
✅ Integrated into daemon_v2.py

## Integration Status
🟢 **FULLY INTEGRATED** - Daemon sends notifications automatically

## How It Works
1. daemon_v2.py calls send_task_notification() after each task
2. Notification script runs in background (non-blocking)
3. Uses Microsoft Graph API (Outlook) to send email
4. Beautiful HTML email with task details
5. Status emoji (✅ success / ❌ failure)

## Configuration
- **Recipient:** stefanos.drakos@gmail.com
- **Sender:** sdrakos@agel.ai (via Outlook API)
- **Language:** Greek
- **Trigger:** Every completed or failed scheduled task

## Email Format
- Subject: [emoji] Εργασία: [task title]
- Contains: task ID, title, status, duration, result
- Styled HTML with gradient header
- Auto-sent from daemon (no manual action needed)

## Status
🟢 ACTIVE - Notifications enabled for all scheduled tasks

