"""
Memory & Skill CLI helper
==========================
Exposes memory and skill operations as CLI commands so the daemon agent
can call them via Bash (non-streaming mode doesn't support MCP servers).

Usage:
  agelclaw-mem <command> [args...]

Memory commands:
  context                           - Get full context summary
  pending [limit]                   - Get pending tasks
  due                               - Get due tasks (ready now)
  scheduled                         - Get future scheduled tasks
  stats                             - Get task stats
  get_task <id>                     - Get full task details by ID
  completed [limit]                 - Get recent completed tasks
  all_tasks [limit] [status]        - Get all tasks (optionally filtered by status)
  start_task <id>                   - Mark task as in_progress
  complete_task <id> <result>       - Mark task as completed
  fail_task <id> <error>            - Mark task as failed
  delete_task <id>                  - Delete a task permanently
  add_task <title> [desc] [pri] [due_at] [recurring] [assigned_to] - Add a new task
  log <message>                     - Log a message
  add_learning <cat> <content>      - Add a learning
  get_learnings [category]          - Get learnings
  rules                             - List active hard rules
  promote_rule <learning_id>        - Promote a learning to hard rule
  demote_rule <learning_id>         - Demote a hard rule back to learning

Profile commands:
  profile [category]                - Show user profile (all or by category)
  set_profile <cat> <key> "<val>" [confidence] [source] - Set a profile fact
  del_profile <cat> <key>           - Delete a profile fact

Skill commands:
  skills                            - List installed skills
  find_skill <description>          - Find skill matching description
  skill_content <name>              - Get full skill content
  create_skill <name> <desc> <body> - Create a new skill
  add_script <skill> <file> <code>  - Add script to skill
  add_ref <skill> <file> <content>  - Add reference to skill
  update_skill <name> <body>        - Update skill body

Per-subagent task commands:
  assign_task <task_id> <subagent>  - Assign existing task to a subagent
  unassign_task <task_id>           - Remove subagent assignment (make global)
  add_subagent_task <subagent> <title> [desc] [pri] [due] [recur] - Create task for subagent
  subagent_tasks <subagent> [status] [limit] - List tasks for a subagent
  subagent_stats <subagent>         - Task statistics for a subagent

Subagent commands:
  subagents                         - List installed subagent definitions
  subagent_content <name>           - Get full SUBAGENT.md content
  create_subagent <name> <desc> <body> - Create persistent subagent definition

Task folder commands:
  task_folder <id>                  - Get/create task folder path

Daemon control commands:
  running_tasks                     - List currently executing tasks
  cancel_task <id>                  - Cancel a running task/subagent
  update_task <id> "<message>"      - Update running task (cancel + restart with appended instructions)
  run_task <id>                     - Force-execute a pending task immediately
  daemon_status                     - Full daemon status (state, running tasks, last cycle)

Semantic search commands:
  search "<query>" [limit] [--table <name>]  - AI-powered semantic search
  embed_backfill                    - Backfill embeddings for existing data
  embed_stats                       - Show embedding coverage statistics
"""

import sys
import json
import io
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agelclaw.memory import Memory
from agelclaw.project import get_tasks_dir, get_subagents_dir

memory = Memory()

DAEMON_PORT = int(os.getenv("AGENT_DAEMON_PORT", os.getenv("AGENT_API_PORT", "8420")))


def _wake_daemon():
    """Notify the daemon to recalculate its sleep timeout (fire-and-forget)."""
    try:
        req = Request(f"http://localhost:{DAEMON_PORT}/wake", method="POST")
        urlopen(req, timeout=2)
    except (URLError, OSError):
        pass  # Daemon not running — that's fine


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    # ── Memory commands ──────────────────────────────────────

    if cmd == "context":
        print(memory.build_context_summary())

    elif cmd == "conversations":
        # Show recent conversations or search by keyword
        keyword = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        if keyword:
            # Search conversations by keyword
            import sqlite3
            conn = sqlite3.connect(str(memory.db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, role, content, created_at FROM conversations
                   WHERE content LIKE ? AND session_id = 'shared_chat'
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{keyword}%", limit),
            ).fetchall()
            conn.close()
            if rows:
                print(f"Found {len(rows)} messages matching '{keyword}':")
                for r in reversed(list(rows)):
                    content = r["content"][:300] + "..." if len(r["content"]) > 300 else r["content"]
                    print(f"\n[{r['created_at']}] {r['role'].upper()}:\n{content}")
            else:
                print(f"No conversations found matching '{keyword}'")
        else:
            convos = memory.get_conversation_history(session_id="shared_chat", limit=limit)
            for c in convos:
                content = c["content"][:300] + "..." if len(c["content"]) > 300 else c["content"]
                print(f"\n[{c.get('created_at', '')}] {c['role'].upper()}:\n{content}")

    elif cmd == "pending":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        tasks = memory.get_pending_tasks(limit=limit)
        print(json.dumps(tasks, indent=2, default=str))

    elif cmd == "due":
        tasks = memory.get_due_tasks()
        print(json.dumps(tasks, indent=2, default=str))

    elif cmd == "scheduled":
        tasks = memory.get_scheduled_tasks()
        if not tasks:
            print("No scheduled tasks.")
        else:
            for t in tasks:
                print(f"  #{t['id']} [{t['next_run_at']}] {t['title']}"
                      + (f"  (recurring: {t['recurring_cron']})" if t.get('recurring_cron') else ""))


    elif cmd == "stats":
        print(json.dumps(memory.get_task_stats(), indent=2))

    elif cmd == "get_task":
        task_id = int(sys.argv[2])
        task = memory.get_task(task_id)
        if task:
            print(json.dumps(task, indent=2, default=str))
            # Also show task folder contents if exists
            folder = get_tasks_dir() / f"task_{task_id}"
            if folder.exists():
                files = [f.name for f in folder.iterdir() if f.is_file()]
                print(f"\nTask folder: {folder}")
                print(f"Files: {', '.join(files)}")
                # Show result.md if exists
                result_file = folder / "result.md"
                if result_file.exists():
                    content = result_file.read_text(encoding="utf-8", errors="replace")
                    print(f"\n--- result.md ---\n{content[:3000]}")
        else:
            print(f"Task #{task_id} not found")

    elif cmd == "completed":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        tasks = memory.get_recent_completed(limit=limit)
        if not tasks:
            print("No completed tasks.")
        else:
            print(f"Last {len(tasks)} completed tasks:")
            for t in tasks:
                result_preview = (t.get("result") or "")[:200]
                print(f"\n  #{t['id']} [{t.get('completed_at', '?')}] {t['title']}")
                if result_preview:
                    print(f"    Result: {result_preview}")

    elif cmd == "all_tasks":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        status_filter = sys.argv[3] if len(sys.argv) > 3 else None
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(memory.db_path))
        conn.row_factory = _sqlite3.Row
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        tasks = [dict(r) for r in rows]
        if not tasks:
            print("No tasks found.")
        else:
            for t in tasks:
                status_icon = {"completed": "OK", "failed": "FAIL", "pending": "...", "in_progress": ">>", "cancelled": "X"}.get(t["status"], "?")
                print(f"  #{t['id']} [{status_icon}] {t['title']}  (status={t['status']}, pri={t['priority']})")

    elif cmd == "start_task":
        task_id = int(sys.argv[2])
        memory.start_task(task_id)
        folder = memory.get_task_folder(task_id)
        print(f"Task #{task_id} marked as in_progress (folder: {folder})")

    elif cmd == "complete_task":
        task_id = int(sys.argv[2])
        result = sys.argv[3] if len(sys.argv) > 3 else "Done"
        memory.complete_task(task_id, result)
        print(f"Task #{task_id} completed: {result}")

    elif cmd == "fail_task":
        task_id = int(sys.argv[2])
        error = sys.argv[3] if len(sys.argv) > 3 else "Unknown error"
        memory.fail_task(task_id, error)
        print(f"Task #{task_id} failed: {error}")

    elif cmd == "delete_task":
        task_id = int(sys.argv[2])
        if memory.delete_task(task_id):
            print(f"Task #{task_id} deleted successfully")
        else:
            print(f"Task #{task_id} not found")
            sys.exit(1)

    elif cmd == "add_task":
        title = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        pri = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        due = sys.argv[5] if len(sys.argv) > 5 else None
        recur = sys.argv[6] if len(sys.argv) > 6 else None
        assigned = sys.argv[7] if len(sys.argv) > 7 else None
        task_id = memory.add_task(
            title=title, description=desc, priority=pri,
            due_at=due, recurring_cron=recur, assigned_to=assigned,
        )
        info = f"Task #{task_id} created: {title}"
        if due:
            info += f" (due: {due})"
        if recur:
            info += f" (recurring: {recur})"
        if assigned:
            info += f" (assigned: {assigned})"
        print(info)
        _wake_daemon()  # Notify daemon to recalculate sleep for new task

    elif cmd == "log":
        msg = " ".join(sys.argv[2:])
        memory.log_conversation(role="system", content=msg)
        print(f"Logged: {msg}")

    elif cmd == "add_learning":
        cat = sys.argv[2]
        content = " ".join(sys.argv[3:])
        memory.add_learning(category=cat, insight=content)
        print(f"Learning added [{cat}]: {content[:100]}")

    elif cmd == "get_learnings":
        cat = sys.argv[2] if len(sys.argv) > 2 else None
        learnings = memory.get_learnings(category=cat)
        print(json.dumps(learnings, indent=2, default=str))

    # ── Hard Rules commands ───────────────────────────────────

    elif cmd == "rules":
        rules = memory.get_rules()
        if not rules:
            print("No active hard rules.")
        else:
            print(f"Active hard rules ({len(rules)}):")
            for r in rules:
                print(f"  #{r['id']} [{r['category']}] {r['insight']}")

    elif cmd == "promote_rule":
        learning_id = int(sys.argv[2])
        if memory.promote_rule(learning_id):
            print(f"Learning #{learning_id} promoted to hard rule.")
        else:
            print(f"Learning #{learning_id} not found or already a rule.")

    elif cmd == "demote_rule":
        learning_id = int(sys.argv[2])
        if memory.demote_rule(learning_id):
            print(f"Rule #{learning_id} demoted back to regular learning.")
        else:
            print(f"Learning #{learning_id} not found or not a rule.")

    # ── Profile commands ──────────────────────────────────────

    elif cmd == "profile":
        cat = sys.argv[2] if len(sys.argv) > 2 else None
        facts = memory.get_profile(category=cat)
        if not facts:
            print("No profile data." + (f" (category: {cat})" if cat else ""))
        else:
            current_cat = None
            for f in facts:
                if f["category"] != current_cat:
                    current_cat = f["category"]
                    print(f"\n[{current_cat.upper()}]")
                conf = f"(conf:{f['confidence']}, {f['source']})"
                print(f"  {f['key']} = {f['value']}  {conf}")

    elif cmd == "set_profile":
        cat = sys.argv[2]
        key = sys.argv[3]
        value = sys.argv[4]
        conf = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
        source = sys.argv[6] if len(sys.argv) > 6 else "stated"
        memory.set_profile(cat, key, value, conf, source)
        print(f"Profile: {cat}/{key} = {value}  (conf:{conf}, {source})")

    elif cmd == "del_profile":
        cat = sys.argv[2]
        key = sys.argv[3]
        deleted = memory.delete_profile(cat, key)
        if deleted:
            print(f"Deleted profile: {cat}/{key}")
        else:
            print(f"Not found: {cat}/{key}")

    # ── Skill commands ───────────────────────────────────────
    # Skill tools are SdkMcpTool objects — call .handler() for the async fn

    elif cmd == "skills":
        from agelclaw.skill_tools import list_installed_skills
        import asyncio
        result = asyncio.run(list_installed_skills.handler({}))
        print(result["content"][0]["text"])

    elif cmd == "find_skill":
        desc = " ".join(sys.argv[2:])
        from agelclaw.skill_tools import find_skill_for_task
        import asyncio
        result = asyncio.run(find_skill_for_task.handler({"task_description": desc}))
        print(result["content"][0]["text"])

    elif cmd == "skill_content":
        name = sys.argv[2]
        from agelclaw.skill_tools import get_skill_content
        import asyncio
        result = asyncio.run(get_skill_content.handler({"skill_name": name}))
        print(result["content"][0]["text"])

    elif cmd == "create_skill":
        name = sys.argv[2]
        desc = sys.argv[3]
        body = sys.argv[4]
        loc = sys.argv[5] if len(sys.argv) > 5 else "project"
        from agelclaw.skill_tools import create_full_skill
        import asyncio
        result = asyncio.run(create_full_skill.handler({
            "name": name, "description": desc, "body": body, "location": loc
        }))
        print(result["content"][0]["text"])

    elif cmd == "add_script":
        skill = sys.argv[2]
        filename = sys.argv[3]
        content = sys.argv[4]
        from agelclaw.skill_tools import add_skill_script
        import asyncio
        result = asyncio.run(add_skill_script.handler({
            "skill_name": skill, "filename": filename, "content": content
        }))
        print(result["content"][0]["text"])

    elif cmd == "add_ref":
        skill = sys.argv[2]
        filename = sys.argv[3]
        content = sys.argv[4]
        from agelclaw.skill_tools import add_skill_reference
        import asyncio
        result = asyncio.run(add_skill_reference.handler({
            "skill_name": skill, "filename": filename, "content": content
        }))
        print(result["content"][0]["text"])

    elif cmd == "update_skill":
        name = sys.argv[2]
        body = sys.argv[3]
        from agelclaw.skill_tools import update_skill_body
        import asyncio
        result = asyncio.run(update_skill_body.handler({
            "skill_name": name, "new_body": body
        }))
        print(result["content"][0]["text"])

    # ── Per-subagent task commands ────────────────────────────

    elif cmd == "assign_task":
        task_id = int(sys.argv[2])
        subagent = sys.argv[3]
        if memory.assign_task(task_id, subagent):
            print(f"Task #{task_id} assigned to subagent '{subagent}'")
        else:
            print(f"Task #{task_id} not found")
            sys.exit(1)

    elif cmd == "unassign_task":
        task_id = int(sys.argv[2])
        if memory.unassign_task(task_id):
            print(f"Task #{task_id} unassigned (now global)")
        else:
            print(f"Task #{task_id} not found")
            sys.exit(1)

    elif cmd == "add_subagent_task":
        subagent = sys.argv[2]
        title = sys.argv[3]
        desc = sys.argv[4] if len(sys.argv) > 4 else ""
        pri = int(sys.argv[5]) if len(sys.argv) > 5 else 5
        due = sys.argv[6] if len(sys.argv) > 6 else None
        recur = sys.argv[7] if len(sys.argv) > 7 else None
        task_id = memory.add_task(
            title=title, description=desc, priority=pri,
            due_at=due, recurring_cron=recur, assigned_to=subagent,
        )
        info = f"Task #{task_id} created for subagent '{subagent}': {title}"
        if due:
            info += f" (due: {due})"
        if recur:
            info += f" (recurring: {recur})"
        print(info)
        _wake_daemon()

    elif cmd == "subagent_tasks":
        subagent = sys.argv[2]
        status_filter = sys.argv[3] if len(sys.argv) > 3 else None
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        tasks = memory.get_subagent_tasks(subagent, status=status_filter, limit=limit)
        if not tasks:
            print(f"No tasks for subagent '{subagent}'" + (f" (status={status_filter})" if status_filter else ""))
        else:
            print(f"Tasks for subagent '{subagent}' ({len(tasks)}):")
            for t in tasks:
                status_icon = {"completed": "OK", "failed": "FAIL", "pending": "...", "in_progress": ">>", "cancelled": "X"}.get(t["status"], "?")
                print(f"  #{t['id']} [{status_icon}] {t['title']}  (status={t['status']}, pri={t['priority']})")

    elif cmd == "subagent_stats":
        subagent = sys.argv[2]
        stats = memory.get_subagent_stats(subagent)
        print(json.dumps(stats, indent=2))

    # ── Subagent commands ────────────────────────────────────

    elif cmd == "subagents":
        subagents_root = get_subagents_dir()
        if not subagents_root.exists():
            print("No subagent definitions found.")
        else:
            found = False
            for sub_dir in sorted(subagents_root.iterdir()):
                if not sub_dir.is_dir():
                    continue
                sub_md = sub_dir / "SUBAGENT.md"
                if not sub_md.exists():
                    continue
                found = True
                content = sub_md.read_text(encoding="utf-8", errors="replace")
                # Extract description from frontmatter
                import re
                fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                desc = ""
                provider = "auto"
                task_type = "general"
                if fm:
                    d = re.search(r'description:\s*(.+)', fm.group(1))
                    if d:
                        desc = d.group(1).strip().strip('"\'')
                    p = re.search(r'provider:\s*(\S+)', fm.group(1))
                    if p:
                        provider = p.group(1)
                    t = re.search(r'task_type:\s*(\S+)', fm.group(1))
                    if t:
                        task_type = t.group(1)
                print(f"  {sub_dir.name}: {desc} [{provider}, {task_type}]")
            if not found:
                print("No subagent definitions found.")

    elif cmd == "subagent_content":
        name = sys.argv[2]
        subagents_root = get_subagents_dir()
        sub_md = subagents_root / name / "SUBAGENT.md"
        if sub_md.exists():
            print(sub_md.read_text(encoding="utf-8", errors="replace"))
        else:
            print(f"Subagent '{name}' not found at {sub_md}")

    elif cmd == "create_subagent":
        name = sys.argv[2]
        desc = sys.argv[3]
        body = sys.argv[4]
        subagents_root = get_subagents_dir()
        sub_dir = subagents_root / name
        sub_dir.mkdir(parents=True, exist_ok=True)
        (sub_dir / "scripts").mkdir(exist_ok=True)
        sub_md = sub_dir / "SUBAGENT.md"
        # Build SUBAGENT.md with frontmatter
        content = f"---\nname: {name}\ndescription: >-\n  {desc}\nprovider: auto\ntask_type: general\n---\n\n{body}"
        sub_md.write_text(content, encoding="utf-8")
        print(f"Subagent '{name}' created at {sub_dir}")

    # ── Embedding / Semantic search commands ─────────────────

    elif cmd == "search":
        query_text = sys.argv[2] if len(sys.argv) > 2 else ""
        if not query_text:
            print("Usage: agelclaw-mem search \"<query>\" [limit] [--table <name>]")
            sys.exit(1)

        limit = 5
        table_filter = None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--table" and i + 1 < len(sys.argv):
                table_filter = sys.argv[i + 1]
                i += 2
            else:
                try:
                    limit = int(sys.argv[i])
                except ValueError:
                    pass
                i += 1

        tables = [table_filter] if table_filter else None
        results = memory.semantic_search(query_text, tables=tables, limit=limit)
        if results:
            print(f"Found {len(results)} semantic matches for '{query_text}':\n")
            for r in results:
                print(f"  [{r['table']}] #{r['row_id']} (distance: {r['distance']})")
                print(f"    {r['preview']}")
                print()
        else:
            print(f"No semantic matches for '{query_text}' (embeddings may not be available)")

    elif cmd == "embed_backfill":
        store = memory.embeddings
        if store is None:
            print("Embeddings not available (check OpenAI API key and sqlite-vec installation)")
            sys.exit(1)
        print("Backfilling embeddings for existing data...")
        stats = store.backfill()
        print(f"Backfill complete:")
        print(f"  Conversations: {stats.get('conversations', 0)} newly embedded")
        print(f"  Tasks: {stats.get('tasks', 0)} newly embedded")
        print(f"  Learnings: {stats.get('learnings', 0)} newly embedded")
        if stats.get("error"):
            print(f"  Error: {stats['error']}")

    elif cmd == "embed_stats":
        store = memory.embeddings
        if store is None:
            print("Embeddings not available (check OpenAI API key and sqlite-vec installation)")
            sys.exit(1)
        stats = store.get_stats()
        if not stats.get("available"):
            print("Embeddings not available")
        else:
            print("Embedding coverage:")
            for tbl in ("conversations", "tasks", "learnings"):
                info = stats.get(tbl, {})
                embedded = info.get("embedded", 0)
                total = info.get("total", 0)
                pct = (embedded / total * 100) if total > 0 else 0
                print(f"  {tbl}: {embedded}/{total} ({pct:.0f}%)")

    # ── Daemon control commands ──────────────────────────────

    elif cmd == "running_tasks":
        try:
            data = json.loads(urlopen(f"http://localhost:{DAEMON_PORT}/running", timeout=5).read())
            tasks = data.get("running_tasks", [])
            if not tasks:
                print("No tasks currently running.")
            else:
                print(f"Currently running ({len(tasks)}):")
                for t in tasks:
                    print(f"  #{t.get('task_id', '?')} [{t.get('subagent', 'global')}] {t.get('title', '')}  (started: {t.get('started_at', '?')})")
        except (URLError, OSError):
            print("Daemon not running or not reachable.")

    elif cmd == "cancel_task":
        task_id = sys.argv[2]
        try:
            req = Request(f"http://localhost:{DAEMON_PORT}/tasks/{task_id}/cancel", method="POST")
            data = json.loads(urlopen(req, timeout=10).read())
            print(json.dumps(data, indent=2, default=str))
        except (URLError, OSError) as e:
            print(f"Failed to cancel task #{task_id}: {e}")

    elif cmd == "update_task":
        task_id = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        try:
            payload = json.dumps({"message": message}).encode()
            req = Request(
                f"http://localhost:{DAEMON_PORT}/tasks/{task_id}/update",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            data = json.loads(urlopen(req, timeout=10).read())
            print(json.dumps(data, indent=2, default=str))
        except (URLError, OSError) as e:
            print(f"Failed to update task #{task_id}: {e}")

    elif cmd == "run_task":
        task_id = sys.argv[2]
        try:
            req = Request(f"http://localhost:{DAEMON_PORT}/execute_task/{task_id}", method="POST")
            data = json.loads(urlopen(req, timeout=10).read())
            print(json.dumps(data, indent=2, default=str))
        except (URLError, OSError) as e:
            print(f"Failed to execute task #{task_id}: {e}")

    elif cmd == "daemon_status":
        try:
            data = json.loads(urlopen(f"http://localhost:{DAEMON_PORT}/status", timeout=5).read())
            print(json.dumps(data, indent=2, default=str))
        except (URLError, OSError):
            print("Daemon not running or not reachable.")

    # ── Task folder commands ──────────────────────────────────

    elif cmd == "task_folder":
        task_id = int(sys.argv[2])
        folder = memory.get_task_folder(task_id)
        print(str(folder))

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'agelclaw-mem' for help")
        sys.exit(1)


if __name__ == "__main__":
    main()
