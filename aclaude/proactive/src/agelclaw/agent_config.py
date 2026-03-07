"""
Shared Agent Configuration
==========================
System prompt, tool list, and options builder shared between
api_server.py and telegram_bot.py.

Supports multi-provider routing (Claude, OpenAI) via the AgentRouter.
"""

import sqlite3
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from agelclaw.core.config import load_config
from agelclaw.core.agent_router import AgentRouter, Provider

from agelclaw.project import get_project_dir, get_db_path, get_skills_dir, get_subagents_dir, get_persona_dir, get_mcp_servers_dir

PROACTIVE_DIR = get_project_dir()
SHARED_SESSION_ID = "shared_chat"
DB_PATH = get_db_path()

# All agent channels (chat, telegram, daemon) share the same full tool set
AGENT_TOOLS = ["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch"]

# Backward-compat alias
ALLOWED_TOOLS = AGENT_TOOLS

# Singleton router
_router = AgentRouter()

_SYSTEM_PROMPT_BASE = """You are a full-capability AI assistant with direct access to tools, memory, skills, web search, and file operations.
You execute work YOURSELF — reading files, writing code, searching the web, managing tasks and skills.

## YOUR TOOLS
You have: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Skill.
Use them directly. Do NOT tell the user to run commands — run them yourself.

## MCP TOOLS FIRST (ΓΕΝΙΚΟΣ ΚΑΝΟΝΑΣ)
Αν υπάρχει MCP tool (`mcp__<server>__<tool>`) που κάνει αυτό που χρειάζεσαι, ΠΑΝΤΑ χρησιμοποίησέ το πρώτα.
Τα MCP tools είναι πιο γρήγορα (native tool call) από το `Bash("agelclaw-mem ...")` (subprocess spawn).
Χρησιμοποίησε Bash μόνο αν δεν υπάρχει αντίστοιχο MCP tool ή αν αποτύχει.

## MEMORY & SKILL TOOLS
**ALWAYS use MCP tools first** — they are faster (1 tool call vs subprocess spawn):

### MCP tools (PREFERRED — use these):
  mcp__memory-tools__memory_add_task            # Add task (title, desc, priority, due_at, recurring)
  mcp__memory-tools__memory_get_pending_tasks   # Pending tasks
  mcp__memory-tools__memory_get_due_tasks       # Due scheduled tasks
  mcp__memory-tools__memory_get_stats           # Task statistics
  mcp__memory-tools__memory_get_full_context    # Full context summary
  mcp__memory-tools__memory_start_task          # Mark task in_progress
  mcp__memory-tools__memory_complete_task       # Mark task completed (id, result)
  mcp__memory-tools__memory_fail_task           # Mark task failed (id, error)
  mcp__memory-tools__memory_log                 # Log a message
  mcp__memory-tools__memory_add_learning        # Add learning (category, content)
  mcp__memory-tools__memory_get_learnings       # Get learnings (optional category)
  mcp__memory-tools__memory_get_history         # Recent conversation history
  mcp__memory-tools__memory_kv_set              # Store key-value pair
  mcp__memory-tools__memory_kv_get              # Retrieve key-value pair

### Bash fallback (ONLY when MCP tools unavailable or for commands not in MCP):
  agelclaw-mem context | pending | due | scheduled | completed | stats
  agelclaw-mem add_task "<title>" "<desc>" [pri] [due_at] [recurring]
  agelclaw-mem start_task <id> | complete_task <id> "<result>" | fail_task <id> "<error>"
  agelclaw-mem log "<message>" | add_learning "<cat>" "<content>"
  agelclaw-mem rules | promote_rule <id> | demote_rule <id>

### Scheduling:
  due_at format: ISO datetime, e.g. "2026-02-16T09:00:00"
  recurring formats:
    "daily_HH:MM"        → every day at HH:MM (e.g. "daily_09:00")
    "weekly_D_HH:MM"     → every week on day D at HH:MM (0=Mon, 6=Sun)
    "every_Xm"           → every X minutes (e.g. "every_30m")
    "every_Xh"           → every X hours (e.g. "every_2h")
  Priority: 1=critical, 3=high, 5=normal, 7=low

### Skill commands:
  agelclaw-mem skills                           # List installed skills
  agelclaw-mem find_skill "<description>"       # Find matching skill
  agelclaw-mem skill_content <name>             # Get skill content
  agelclaw-mem create_skill <name> "<desc>" "<body>" [location]
  agelclaw-mem add_script <skill> <file> "<code>"
  agelclaw-mem add_ref <skill> <file> "<content>"
  agelclaw-mem update_skill <name> "<body>"

### Per-subagent task commands:
  agelclaw-mem add_subagent_task <subagent> "<title>" "<desc>" [pri] [due_at] [recurring]
  agelclaw-mem assign_task <task_id> <subagent_name>
  agelclaw-mem unassign_task <task_id>
  agelclaw-mem subagent_tasks <subagent_name> [status] [limit]
  agelclaw-mem subagent_stats <subagent_name>

  Tasks assigned to subagents execute with the subagent's specialized prompt and tools.
  Unassigned tasks are executed by the global daemon.

### Subagent definition commands:
  agelclaw-mem subagents                        # List installed subagent definitions
  agelclaw-mem subagent_content <name>          # Get full SUBAGENT.md content
  agelclaw-mem create_subagent <name> "<desc>" "<body>" [provider] [task_type] [tools_csv]
  agelclaw-mem add_subagent_script <name> <file> "<code>"   # Add script to subagent
  agelclaw-mem add_subagent_ref <name> <file> "<content>"   # Add reference to subagent

### Task folder commands:
  agelclaw-mem task_folder <id>                 # Get/create task folder path
  Task output files are in: `tasks/task_<id>/result.md` and `tasks/task_<id>/`

### Semantic search (AI-powered):
  agelclaw-mem search "<query>" [limit]                    # Search across all tables
  agelclaw-mem search "<query>" --table conversations      # Search specific table
  agelclaw-mem search "<query>" --table tasks              # Search tasks only

### Profile CLI:
  agelclaw-mem profile [category]                         # View profile
  agelclaw-mem set_profile <cat> <key> "<value>" [conf] [source]
  agelclaw-mem del_profile <cat> <key>

## SUBAGENT DELEGATION (CRITICAL — READ THIS FIRST)
Before executing ANY non-trivial work (API calls, scripts, email, reports, file generation):
1. Check if a matching subagent exists (you can see the subagent catalog in your prompt)
2. If a subagent matches the task → DELEGATE. Do NOT execute inline.
   ```
   agelclaw-mem add_subagent_task <subagent_name> "<title>" "<description>" 3
   curl -s -X POST http://localhost:8420/wake
   ```
3. Tell the user: "Ανέθεσα στον subagent '<name>' — Task #N. Θα λάβεις ειδοποίηση."
4. DONE. Move on. Do NOT wait for the subagent to finish.

Examples of DELEGATION (correct):
- User: "στείλε μου τη Διαύγεια" → `add_subagent_task diaugeia "Αναφορά Διαύγειας" "..."` ✅
- User: "τρέξε test Διαύγειας" → `add_subagent_task diaugeia "Test run" "... --excel χωρίς email"` ✅
- User: "φέρε αποφάσεις Ρόδου" → `add_subagent_task diaugeia "Αποφάσεις Ρόδου" "... --org ΡΟΔΟΥ"` ✅
- User: "πρόβλεψη καιρού αύριο" → `add_subagent_task weather "Καιρός αύριο" "πρόβλεψη με --date 2026-03-01" 3` ✅ (NO due_at — runs NOW)
- User: "στείλε NAVTEX report στον X" → `add_subagent_task naval "ORACLE Report" "Ναυτική αναφορά --to user@example.com"` ✅
- User: "τρέξε naval χωρίς email" → `add_subagent_task naval "ORACLE Test" "Test run --no-email"` ✅

IMPORTANT for script subagents: CLI flags (--to, --no-email, --source, etc.) in the description
are auto-extracted and appended to the subagent's base command. Recipients are NOT hardcoded —
always include --to in the description when the user wants email delivery.

Examples of INLINE (wrong):
- User: "στείλε μου τη Διαύγεια" → running python tender_monitor.py yourself ❌ FORBIDDEN
- User: "τρέξε test" → executing scripts in the chat session ❌ FORBIDDEN

## IMMEDIATE vs SCHEDULED execution (CRITICAL)
- By default, subagent tasks run IMMEDIATELY. Do NOT pass a `due_at` parameter.
- Date/time references in the user's request are usually the TARGET of the report, NOT when to execute.
  - "πρόβλεψη αύριο στις 22:00" → run NOW, forecast for tomorrow → NO due_at, put date in description
  - "στείλε καιρό για Κυριακή" → run NOW, forecast for Sunday → NO due_at, put date in description
- ONLY set `due_at` when the user explicitly says SCHEDULE/ΠΡΟΓΡΑΜΜΑΤΙΣΕ, e.g.:
  - "προγραμμάτισε τον καιρό κάθε πρωί στις 9" → due_at + recurring ✅
  - "στείλε μου αύριο στις 8 τα νέα" → due_at = tomorrow 08:00 ✅

ONLY do work inline if: (a) no subagent matches, AND (b) the task takes < 30 seconds (simple questions, quick lookups, file reads).

## TASK MANAGEMENT
- Create tasks for background/scheduled work: `agelclaw-mem add_task "<title>" "<desc>" [pri] [due_at] [recurring]`
- The daemon executes background tasks autonomously — you handle interactive requests directly.
- After creating a task, ALWAYS tell the user "Task #N created".
- To wake the daemon immediately: `curl -s -X POST http://localhost:8420/wake`

## DAEMON CONTROL (running tasks & subagents)
  agelclaw-mem running_tasks                        # List currently executing tasks
  agelclaw-mem cancel_task <id>                     # Stop a running task/subagent
  agelclaw-mem update_task <id> "<new instructions>"  # Edit running task (restart with updated desc)
  agelclaw-mem run_task <id>                        # Force-execute a pending task now
  agelclaw-mem daemon_status                        # Daemon state + running tasks + last cycle

When user says "stop task", "σταμάτα", "cancel", "ακύρωσε" → use cancel_task (works for both running AND scheduled tasks)
When user says "delete", "διέγραψε", "σβήσε" → use delete_task
When user says "change the task", "άλλαξε", "update" → use update_task
When user asks "what's running", "τι τρέχει" → use running_tasks
NOTE: cancel_task auto-falls back to delete_task if the task is not currently running.

## SUBAGENT CREATION — MANDATORY RULES
When the user asks to "create a subagent", "δημιούργησε subagent", "φτιάξε subagent", or mentions specialized/parallel agent execution, you MUST follow ALL these steps IN ORDER:

**FIRST**: Run `agelclaw-mem find_skill "subagent"` to load the subagent-creator skill guide.

1. **Create the subagent definition** (SUBAGENT.md with specialized prompt):
   ```
   agelclaw-mem create_subagent <name> "<description>" "<detailed specialist prompt>" [provider] [task_type] [tools_csv]
   ```
   The body MUST be a complete specialist prompt — NOT a placeholder. Write it as if instructing an expert.
   - provider: auto (default), claude, openai
   - task_type: general, code, research, email
   - tools_csv: comma-separated tool restrictions (optional, default=all)

2. **Add scripts if the task involves API calls, data processing, or file generation**:
   ```
   agelclaw-mem add_subagent_script <name> <filename> "<code>"
   ```
   For long scripts, use the Write tool directly to `subagents/<name>/scripts/<filename>`.
   Scripts MUST be self-contained and tested.

3. **Add references if the subagent needs configuration data** (org IDs, API docs, templates):
   ```
   agelclaw-mem add_subagent_ref <name> <filename> "<content>"
   ```

4. **Create the task ASSIGNED to the subagent** (NOT a global task):
   ```
   agelclaw-mem add_subagent_task <name> "<title>" "<detailed description>" [priority] [due_at] [recurring]
   ```
   This creates a task with `assigned_to=<name>`, so the daemon routes it to the subagent.

5. **Wake the daemon**:
   ```
   curl -s -X POST http://localhost:8420/wake
   ```

6. **Tell the user**: "Δημιουργήθηκε ο subagent '<name>' με task #N — ο daemon θα το εκτελέσει."

VIOLATION: Creating a regular `add_task` when the user asked for a subagent is FORBIDDEN.
VIOLATION: Creating a subagent definition WITHOUT an assigned task is FORBIDDEN.
ALWAYS use `add_subagent_task`, NEVER plain `add_task` for subagent work.

### Ad-hoc subagent execution (no persistent definition):
  curl -s -X POST http://localhost:8000/api/subagents \
    -H "Content-Type: application/json" \
    -d '{"name": "<name>", "prompt": "<detailed task>", "task_type": "code|research|general"}'

## FINDING TASK RESULTS (MANDATORY)
When user asks "where is it?", "did it finish?", "show me the result", "πού είναι;", "τελείωσε;":
→ You MUST run bash commands to check. NEVER answer from memory alone.
→ Step 1: `agelclaw-mem completed` (recent completed tasks)
→ Step 2: `agelclaw-mem get_task <id>` (full details + file paths)
→ Step 3: If task has files, tell user the exact path
NEVER say "not found" without checking first.

## CONVERSATION MEMORY
- Your prompt ALREADY contains recent conversation history (provided automatically)
- READ THE PROMPT CONTEXT FIRST before running mem_cli.py context
- Use `agelclaw-mem conversations "<keyword>"` to search older conversations by keyword
- Conversations are SHARED between Web Chat and Telegram

## PERSONALIZATION — YOU ARE A PERSONAL ASSISTANT
The context includes the user's profile. Use it to personalize every interaction.
After learning new facts about the user, save them:
  agelclaw-mem set_profile <category> <key> "<value>" [confidence] [source]

Categories: identity, work, preferences, relationships, habits, interests
- Stated facts → confidence 0.9, source "stated"
- Inferred facts → confidence 0.6, source "inferred"
- Observed patterns → confidence 0.5, source "observed"

## RESPONSE SPEED RULES (CRITICAL)
- For SIMPLE messages (greetings, questions, opinions, chat): respond IMMEDIATELY. Do NOT call any tools first.
- Do NOT run `agelclaw-mem context` or `agelclaw-mem pending` before answering unless the user specifically asks about tasks/memory.
- Your prompt ALREADY contains conversation history and context. USE IT directly.
- Only call mem_cli.py when you need to CREATE/UPDATE/SEARCH something, not to READ context you already have.
- If the user asks "τι tasks έχω;" THEN check tasks. If the user says "γεια σου" just respond.

## CONFIRMATION = EXECUTE (CRITICAL)
When the user says "ναι", "yes", "nai", "go", "ok", "κάνε το", "τρέξτο", "προχώρα", "sure", "do it":
→ This means EXECUTE THE ACTION you just proposed. IMMEDIATELY.
→ Do NOT describe the action again.
→ Do NOT ask for confirmation again.
→ Do NOT summarize what you will do — just DO IT using tools.
→ If you proposed "θέλεις να τρέξω test;" and user says "ναι" → RUN the test command NOW.
→ If you proposed "να στείλω email;" and user says "ναι" → SEND the email NOW.
VIOLATION: Responding to "ναι" with another description instead of executing is FORBIDDEN.

## DIAGNOSIS & DEBUGGING (CRITICAL — EVIDENCE BEFORE CONCLUSIONS)
When investigating bugs, errors, or system behavior:
→ You MUST gather evidence BEFORE making any diagnosis. NEVER guess.
→ Step 1: READ the actual logs (`tail -100 ~/.agelclaw/logs/daemon.log`, error output, etc.)
→ Step 2: CHECK the actual state (database, running processes, config values)
→ Step 3: READ the relevant source code if the behavior is unclear
→ Step 4: ONLY THEN form a conclusion based on what you actually observed

VIOLATIONS:
- Saying "there's a bug" without reading logs or source code ❌ FORBIDDEN
- Saying "X is not working" without checking if X is actually running ❌ FORBIDDEN
- Saying "the daemon does 0 cycles" without reading daemon.log ❌ FORBIDDEN
- Proposing a fix without first confirming the problem exists ❌ FORBIDDEN
- Confusing "no tasks to run" with "scheduler not running" ❌ FORBIDDEN

Evidence commands:
  tail -100 ~/.agelclaw/logs/daemon.log     # Daemon activity
  agelclaw-mem stats                         # Task statistics
  agelclaw-mem scheduled                     # Scheduled tasks
  agelclaw-mem running_tasks                 # Currently executing
  agelclaw-mem daemon_status                 # Daemon state
  curl -s http://localhost:8420/status        # Daemon API status

RULE: If you cannot show the log line or data that proves the problem, you do NOT have a diagnosis.

## CRITICAL RULES (MUST FOLLOW)
- Respond in the same language the user uses
- Be concise and helpful
- NEVER say "you can run this command" — RUN IT YOURSELF or delegate to daemon
- You MUST use the bash tool to run `agelclaw-mem` commands when you need to CREATE/UPDATE data — DO NOT guess or assume
- NEVER claim something doesn't exist without checking first via bash
- When you offer to do something and the user agrees → ACT, don't talk
- Your ONLY available tools are: Skill, Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch. Do NOT attempt to use TodoWrite, Task, TodoRead, or any other tool not in this list — they do not exist and will cause you to freeze.
"""


def _scan_installed_subagents() -> str:
    """Scan proactive/subagents/ directory and build compact subagent catalog.

    Each subagent has a SUBAGENT.md with YAML frontmatter (name, description, provider, task_type).
    Full content is NOT included — agent should run `agelclaw-mem subagent_content <name>`.
    """
    import re as _re

    subagents_root = get_subagents_dir()
    if not subagents_root.exists():
        return ""

    # Get memory instance for task counts
    from agelclaw.memory import Memory as _Memory
    _mem = _Memory()

    entries = []
    for sub_dir in sorted(subagents_root.iterdir()):
        if not sub_dir.is_dir():
            continue
        sub_md = sub_dir / "SUBAGENT.md"
        if not sub_md.exists():
            continue
        try:
            content = sub_md.read_text(encoding="utf-8", errors="replace").strip()

            # Extract YAML frontmatter
            fm_match = _re.search(r'^---\s*\n(.*?)\n---', content, _re.DOTALL)
            desc = ""
            provider = "auto"
            task_type = "general"
            tools_list = None
            if fm_match:
                fm = fm_match.group(1)
                # description
                d = _re.search(r'description:\s*>-?\s*\n\s+(.+?)(?:\n\S|\n---|\Z)', fm, _re.DOTALL)
                if d:
                    desc = " ".join(d.group(1).split())
                else:
                    d = _re.search(r'description:\s*(.+)', fm)
                    if d:
                        desc = d.group(1).strip().strip('"\'')
                # provider
                p = _re.search(r'provider:\s*(\S+)', fm)
                if p:
                    provider = p.group(1).strip()
                # task_type
                t = _re.search(r'task_type:\s*(\S+)', fm)
                if t:
                    task_type = t.group(1).strip()
                # tools (YAML list)
                tools_match = _re.search(r'tools:\s*\n((?:\s+-\s+\S+\n?)+)', fm)
                if tools_match:
                    tools_list = [line.strip().lstrip("- ") for line in tools_match.group(1).strip().splitlines() if line.strip()]

            if len(desc) > 150:
                desc = desc[:147] + "..."

            entry = f"- **{sub_dir.name}**: {desc}" if desc else f"- **{sub_dir.name}**"
            entry += f" [{provider}, {task_type}]"

            # Task counts
            sa_stats = _mem.get_subagent_stats(sub_dir.name)
            pending_count = sa_stats.get("pending", 0)
            if sa_stats.get("total", 0) > 0:
                entry += f" | tasks: {pending_count} pending, {sa_stats.get('total', 0)} total"

            # Tools restriction
            if tools_list:
                entry += f"\n  Tools: {', '.join(tools_list)}"

            # List scripts if present
            scripts_dir = sub_dir / "scripts"
            if scripts_dir.exists():
                script_names = [f.name for f in sorted(scripts_dir.iterdir()) if f.is_file()]
                if script_names:
                    entry += f"\n  Scripts: {', '.join(script_names[:5])}"

            entries.append(entry)
        except Exception:
            continue

    if not entries:
        return ""

    header = "\n\n## INSTALLED SUBAGENTS\n"
    header += "Persistent subagent definitions. Run `agelclaw-mem subagent_content <name>` for full prompt template.\n"
    header += "Create new: `agelclaw-mem create_subagent <name> \"<desc>\" \"<body>\"`\n\n"
    return header + "\n".join(entries)


def _scan_installed_skills() -> str:
    """Scan .Claude/Skills/ directories and build compact skill catalog.

    Only includes: name, description (from YAML frontmatter), script names, and path.
    Full SKILL.md content is NOT included to keep the prompt small.
    The agent should run `agelclaw-mem skill_content <name>` to get full details.
    """
    import re as _re

    skill_dirs = [
        get_skills_dir(),   # project skills
        Path.home() / ".claude" / "skills",             # user skills
    ]
    skills_text = []

    for skills_root in skill_dirs:
        if not skills_root.exists():
            continue
        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace").strip()

                # Extract description from YAML frontmatter
                desc = ""
                fm_match = _re.search(
                    r'^---\s*\n(.*?)\n---', content, _re.DOTALL
                )
                if fm_match:
                    fm = fm_match.group(1)
                    # Get description field
                    desc_match = _re.search(
                        r'description:\s*>-?\s*\n\s+(.+?)(?:\n\S|\n---|\Z)',
                        fm, _re.DOTALL
                    )
                    if desc_match:
                        desc = desc_match.group(1).strip()
                        desc = " ".join(desc.split())  # collapse whitespace
                    else:
                        # Single-line description
                        desc_match = _re.search(r'description:\s*(.+)', fm)
                        if desc_match:
                            desc = desc_match.group(1).strip().strip('"\'')

                # List available scripts
                scripts_dir = skill_dir / "scripts"
                script_names = []
                if scripts_dir.exists():
                    script_names = [f.name for f in sorted(scripts_dir.iterdir()) if f.is_file()]

                # Build compact entry
                skill_entry = f"- **{skill_dir.name}**"
                if desc:
                    # Truncate long descriptions
                    if len(desc) > 150:
                        desc = desc[:147] + "..."
                    skill_entry += f": {desc}"
                if script_names:
                    scripts_str = ", ".join(script_names[:5])
                    if len(script_names) > 5:
                        scripts_str += f" (+{len(script_names)-5} more)"
                    skill_entry += f"\n  Scripts: {scripts_str}"
                    skill_entry += f"\n  Path: {skill_dir}"

                skills_text.append(skill_entry)
            except Exception:
                continue

    if not skills_text:
        return ""

    header = "\n\n## INSTALLED SKILLS\n"
    header += "Use these directly via Bash. Run `agelclaw-mem skill_content <name>` for full usage details.\n"
    header += "Credentials are in config.yaml — NEVER ask the user for them.\n\n"
    return header + "\n".join(skills_text)


import sys as _sys
import time as _time
_prompt_cache = {"text": None, "ts": 0}
_PROMPT_CACHE_TTL = 120  # seconds — rebuild every 2 min

# MCP server config cache (rebuilt with prompt cache)
_mcp_cache: dict = {"configs": {}, "prompt": "", "ts": 0}


def _scan_mcp_servers() -> tuple[dict, str]:
    """Scan mcp_servers/ directories and return (mcp_configs, prompt_text).

    Returns:
        mcp_configs: Dict of {server_name: McpStdioServerConfig} for ClaudeAgentOptions.
                     Only servers with auto_load: true are included.
        prompt_text: Text block listing available MCP servers for system prompt.
    """
    import re as _re

    now = _time.time()
    if _mcp_cache["configs"] and (now - _mcp_cache["ts"]) < _PROMPT_CACHE_TTL:
        return dict(_mcp_cache["configs"]), _mcp_cache["prompt"]

    mcp_root = get_mcp_servers_dir()
    if not mcp_root.exists():
        return {}, ""

    configs = {}
    entries = []

    for server_dir in sorted(mcp_root.iterdir()):
        if not server_dir.is_dir():
            continue
        server_md = server_dir / "SERVER.md"
        if not server_md.exists():
            continue

        try:
            content = server_md.read_text(encoding="utf-8", errors="replace").strip()

            # Parse YAML frontmatter
            fm_match = _re.search(r'^---\s*\n(.*?)\n---', content, _re.DOTALL)
            if not fm_match:
                continue
            fm = fm_match.group(1)

            name = server_dir.name
            desc = ""
            command = ""
            args = []
            env = {}
            auto_load = False
            tools_list = []

            # Extract fields
            n = _re.search(r'name:\s*(\S+)', fm)
            if n:
                name = n.group(1).strip()

            d = _re.search(r'description:\s*(.+)', fm)
            if d:
                desc = d.group(1).strip().strip('"\'')

            c = _re.search(r'command:\s*(.+)', fm)
            if c:
                command = c.group(1).strip()

            # args as YAML list
            a_match = _re.search(r'args:\s*\[([^\]]*)\]', fm)
            if a_match:
                args = [x.strip().strip('"\'') for x in a_match.group(1).split(",") if x.strip()]

            # auto_load
            al = _re.search(r'auto_load:\s*(true|false)', fm, _re.IGNORECASE)
            if al:
                auto_load = al.group(1).lower() == "true"

            # tools list
            tools_block = _re.search(r'tools:\s*\n((?:\s+-\s+.+\n?)+)', fm)
            if tools_block:
                tools_list = [
                    line.strip().lstrip("- ").strip()
                    for line in tools_block.group(1).strip().split("\n")
                    if line.strip().startswith("-")
                ]

            # env vars — simple key: value pairs
            env_block = _re.search(r'env:\s*\n((?:\s+\S+:\s+.+\n?)+)', fm)
            if env_block:
                for line in env_block.group(1).strip().split("\n"):
                    kv = line.strip().split(":", 1)
                    if len(kv) == 2:
                        val = kv[1].strip().strip('"\'')
                        # Resolve ${VAR} references from os.environ
                        import os
                        if val.startswith("${") and val.endswith("}"):
                            val = os.environ.get(val[2:-1], "")
                        env[kv[0].strip()] = val

            if not command:
                continue

            # Resolve relative paths for server script
            resolved_args = []
            for arg in args:
                arg_path = server_dir / arg
                if arg_path.exists():
                    resolved_args.append(str(arg_path))
                else:
                    resolved_args.append(arg)

            # Resolve 'python' → real Python interpreter for reliability
            if command in ("python", "python3"):
                from agelclaw._nuitka_compat import get_python_exe
                command = get_python_exe()

            # Build McpStdioServerConfig dict
            server_config = {"command": command, "args": resolved_args}
            if env:
                server_config["env"] = env

            if auto_load:
                configs[name] = server_config

            # Build prompt entry
            tool_names = [f"`mcp__{name}__{t}`" for t in tools_list] if tools_list else []
            entry = f"- **{name}**"
            if desc:
                entry += f": {desc[:120]}"
            if auto_load:
                entry += " (auto-loaded)"
            if tool_names:
                entry += f"\n  Tools: {', '.join(tool_names[:8])}"
                if len(tool_names) > 8:
                    entry += f" (+{len(tool_names)-8} more)"
            entries.append(entry)

        except Exception:
            continue

    prompt = ""
    if entries:
        prompt = "\n\n## INSTALLED MCP SERVERS\n"
        prompt += "Native tool servers loaded automatically. Use `mcp__{server}__{tool}` tool names.\n"
        prompt += "Run `agelclaw-mem mcp_servers` for full list.\n\n"
        prompt += "\n".join(entries)

    _mcp_cache["configs"] = configs
    _mcp_cache["prompt"] = prompt
    _mcp_cache["ts"] = now

    return dict(configs), prompt  # Return copy to prevent mutation of cache


def _build_mcp_tool_wildcards(mcp_configs: dict) -> list[str]:
    """Build wildcard allowed_tools entries for MCP servers.

    Returns e.g. ["mcp__memory-tools__*", "mcp__weather-api__*"]
    """
    return [f"mcp__{name}__*" for name in mcp_configs]


def load_mcp_server_config(name: str) -> dict | None:
    """Load a specific MCP server config by name. Used by daemon for per-subagent loading."""
    import re as _re

    mcp_root = get_mcp_servers_dir()
    server_dir = mcp_root / name
    server_md = server_dir / "SERVER.md"
    if not server_md.exists():
        return None

    try:
        content = server_md.read_text(encoding="utf-8", errors="replace").strip()
        fm_match = _re.search(r'^---\s*\n(.*?)\n---', content, _re.DOTALL)
        if not fm_match:
            return None
        fm = fm_match.group(1)

        command = ""
        args = []
        env = {}

        c = _re.search(r'command:\s*(.+)', fm)
        if c:
            command = c.group(1).strip()

        a_match = _re.search(r'args:\s*\[([^\]]*)\]', fm)
        if a_match:
            args = [x.strip().strip('"\'') for x in a_match.group(1).split(",") if x.strip()]

        env_block = _re.search(r'env:\s*\n((?:\s+\S+:\s+.+\n?)+)', fm)
        if env_block:
            import os
            for line in env_block.group(1).strip().split("\n"):
                kv = line.strip().split(":", 1)
                if len(kv) == 2:
                    val = kv[1].strip().strip('"\'')
                    if val.startswith("${") and val.endswith("}"):
                        val = os.environ.get(val[2:-1], "")
                    env[kv[0].strip()] = val

        if not command:
            return None

        # Resolve args
        resolved_args = []
        for arg in args:
            arg_path = server_dir / arg
            if arg_path.exists():
                resolved_args.append(str(arg_path))
            else:
                resolved_args.append(arg)

        if command in ("python", "python3"):
            from agelclaw._nuitka_compat import get_python_exe
            command = get_python_exe()

        config = {"command": command, "args": resolved_args}
        if env:
            config["env"] = env
        return config

    except Exception:
        return None


def _load_persona_files() -> str:
    """Load persona/SOUL.md, IDENTITY.md, GUARDRAIL.md.
    GUARDRAIL.md is the security rules file — editable at persona/GUARDRAIL.md.
    Since the system prompt is offloaded to a file (SYSTEM_PROMPT.md) on Windows,
    there is no command line size limit and the guardrail can be as long as needed."""
    persona_dir = get_persona_dir()
    parts = []

    for filename in ("SOUL.md", "IDENTITY.md", "GUARDRAIL.md"):
        filepath = persona_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    parts.append(content)
            except Exception:
                pass

    return "\n\n".join(parts) + "\n\n---\n\n"


def _check_bootstrap() -> str:
    """Check if persona/BOOTSTRAP.md exists (first-run onboarding).
    If it does, return its content with instructions to complete onboarding."""
    persona_dir = get_persona_dir()
    bootstrap = persona_dir / "BOOTSTRAP.md"
    if not bootstrap.exists():
        return ""

    try:
        content = bootstrap.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return ""
        return (
            "\n\n## ONBOARDING MODE (FIRST RUN)\n"
            "The file persona/BOOTSTRAP.md exists, which means this is the first conversation.\n"
            "Follow the onboarding instructions below. After completing onboarding, DELETE persona/BOOTSTRAP.md.\n\n"
            f"{content}\n\n---\n\n"
        )
    except Exception:
        return ""


def get_system_prompt() -> str:
    """Build the full system prompt with persona, skills, subagents, MCP servers, and hard rules.
    Cached for 120s to avoid filesystem scanning on every message."""
    now = _time.time()
    if _prompt_cache["text"] and (now - _prompt_cache["ts"]) < _PROMPT_CACHE_TTL:
        return _prompt_cache["text"]

    from agelclaw.memory import Memory
    mem = Memory()
    _, mcp_prompt = _scan_mcp_servers()
    result = (
        _load_persona_files()
        + _check_bootstrap()
        + _SYSTEM_PROMPT_BASE
        + _scan_installed_skills()
        + _scan_installed_subagents()
        + mcp_prompt
        + mem.build_rules_prompt()
    )
    _prompt_cache["text"] = result
    _prompt_cache["ts"] = now
    return result


# SYSTEM_PROMPT is now dynamic — use get_system_prompt() instead
# This static alias is kept for backwards compatibility at import time
SYSTEM_PROMPT = get_system_prompt()


def build_prompt_with_history(user_text: str, memory, channel_type: str = "private") -> str:
    """Build prompt with recent conversation history + fast keyword recall.

    Shared between api_server.py and telegram_bot.py so both channels
    see the same unified conversation memory.

    Args:
        user_text: The user's message.
        memory: Memory instance.
        channel_type: "private", "web", "group", or "daemon".
            - "private"/"web"/"daemon": full context (profile, persona, conversations)
            - "group": no profile, no private conversations, only group-relevant history

    Performance: uses only SQLite queries (no external API calls).
    Semantic search is available on-demand via `agelclaw-mem search "..."`.
    """
    session_id = SHARED_SESSION_ID

    # In group mode, only show group conversations, not private ones
    if channel_type == "group":
        recent = memory.get_conversation_history(session_id="group_chat", limit=20)
    else:
        recent = memory.get_conversation_history(session_id=session_id, limit=20)

    if not recent:
        return user_text

    # Fast keyword recall from older conversations — SQLite LIKE only, no embedding API
    relevant_older = _find_relevant_history_fast(user_text, session_id, recent)

    context_parts = []

    if relevant_older and channel_type != "group":
        context_parts.append("=== Relevant earlier conversation ===")
        for msg in relevant_older:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            if len(content) > 800:
                content = content[:800] + "..."
            context_parts.append(f"{prefix}: {content}")
        context_parts.append("\n=== Recent conversation ===")

    for msg in recent:
        prefix = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        if msg["role"] == "assistant" and len(content) > 1500:
            content = content[:1500] + "..."
        context_parts.append(f"{prefix}: {content}")

    context_parts.append(f"\nUser (latest): {user_text}")

    return (
        "Previous conversation context (from memory):\n"
        + "\n\n".join(context_parts)
        + "\n\nRespond to the latest user message. You have full context of what was discussed before."
        + "\n\nREMINDER: You have ALL tools available (Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch). "
        + "Use MCP tools (mcp__memory-tools__*) for memory/task operations — faster than Bash. Use agelclaw-mem via Bash only as fallback. "
        + "For deeper memory recall, run `agelclaw-mem search \"query\"` (semantic search). "
        + "If a subagent exists for this type of work, DELEGATE via add_subagent_task — do NOT run scripts inline. "
        + "If the user says 'ναι'/'yes'/'nai' to something you proposed — EXECUTE IT NOW using tools, do not describe it again."
    )


def _find_relevant_history_fast(user_text: str, session_id: str, recent_msgs: list) -> list:
    """Fast keyword-based recall from older conversation history.

    Uses SQLite LIKE queries only — no external API calls, <5ms.
    For deeper semantic search the agent can run `agelclaw-mem search` on-demand.
    """
    recent_ids = {msg.get("id") for msg in recent_msgs if msg.get("id")}

    skip_words = {
        "θέλω", "μπορείς", "κάνε", "πες", "βρες", "στείλε", "δείξε",
        "αυτό", "αυτά", "εδώ", "εκεί", "τώρα", "μετά", "πριν",
        "that", "this", "have", "with", "from", "what", "send", "show",
        "please", "can", "the", "and", "for", "you", "are", "was",
    }
    words = [w.lower().strip(".,;:!?\"'()") for w in user_text.split() if len(w) > 3]
    keywords = [w for w in words if w not in skip_words]

    if not keywords:
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        like_clauses = " OR ".join(["content LIKE ?"] * len(keywords))
        params = [f"%{kw}%" for kw in keywords]
        params.append(session_id)

        rows = conn.execute(
            f"""SELECT * FROM conversations
                WHERE ({like_clauses})
                AND session_id = ?
                ORDER BY created_at DESC
                LIMIT 20""",
            params,
        ).fetchall()
        conn.close()

        older = [dict(r) for r in rows if r["id"] not in recent_ids]
        return list(reversed(older[:6]))
    except Exception:
        return []


def get_system_prompt_for_channel(channel_type: str = "private") -> str:
    """Build system prompt appropriate for the channel type.

    In group mode: skip persona files and user profile to avoid leaking private data.
    In private/web/daemon mode: full system prompt with persona.
    """
    if channel_type == "group":
        # Group mode: base prompt + skills + subagents + MCP + rules, but NO persona files
        from agelclaw.memory import Memory
        mem = Memory()
        _, mcp_prompt = _scan_mcp_servers()
        return (
            _SYSTEM_PROMPT_BASE
            + _scan_installed_skills()
            + _scan_installed_subagents()
            + mcp_prompt
            + mem.build_rules_prompt()
        )
    return get_system_prompt()


# Windows command line limit: 32,767 chars total
# Reserve ~4000 for MCP config, tools, flags, etc.
_MAX_SYSTEM_PROMPT_CHARS = 28_000


def safe_system_prompt(prompt: str) -> str:
    """On Windows, offload large system prompts to a file to avoid CLI length limits.
    Used by all Claude SDK call sites: telegram, web, CLI, daemon, subagents, heartbeat.
    On non-Windows or short prompts, returns the prompt unchanged.
    """
    import sys as _sys
    if _sys.platform == "win32" and len(prompt) > _MAX_SYSTEM_PROMPT_CHARS:
        prompt_file = get_persona_dir() / "SYSTEM_PROMPT.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        return (
            f"Your full system prompt is in: {prompt_file}\n"
            f"CRITICAL: Before doing ANYTHING, read that file with the Read tool to load your instructions.\n"
            f"It contains your persona, available skills, subagents, MCP tools, rules, and context.\n"
            f"Do NOT respond until you have read and understood the full system prompt.\n"
        )
    return prompt


def build_agent_options(max_turns: int = 30, channel_type: str = "private",
                        extra_mcp_servers: dict | None = None) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for chat/telegram agents (full tool set).

    Args:
        max_turns: Maximum agent loop iterations.
        channel_type: "private", "web", "group", or "daemon".
        extra_mcp_servers: Additional MCP server configs to merge (e.g. per-subagent).
    """
    mcp_configs, _ = _scan_mcp_servers()
    if extra_mcp_servers:
        mcp_configs = {**mcp_configs, **extra_mcp_servers}

    allowed = list(AGENT_TOOLS)
    if mcp_configs:
        allowed += _build_mcp_tool_wildcards(mcp_configs)

    system_prompt = safe_system_prompt(get_system_prompt_for_channel(channel_type))

    opts = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed,
        setting_sources=["user", "project"],
        permission_mode="bypassPermissions",
        cwd=str(PROACTIVE_DIR),
        max_turns=max_turns,
    )
    if mcp_configs:
        opts.mcp_servers = mcp_configs
    return opts


def get_router() -> AgentRouter:
    """Get the singleton AgentRouter."""
    return _router


def get_agent(provider: str | Provider | None = None, model: str | None = None):
    """Factory: get the right agent wrapper based on provider.

    Args:
        provider: "claude", "openai", "auto", or None (uses config default).
        model: Override model (e.g., "gpt-4.1-mini").

    Returns:
        BaseAgent instance (ClaudeAgent or OpenAIAgent).
    """
    from agelclaw.agent_wrappers.base_agent import BaseAgent
    from agelclaw.agent_wrappers.claude_agent import ClaudeAgent
    from agelclaw.agent_wrappers.openai_agent import OpenAIAgent

    route = _router.route(prefer=provider)

    if route.provider == Provider.OPENAI:
        return OpenAIAgent(model=model or route.model)
    else:
        return ClaudeAgent()
