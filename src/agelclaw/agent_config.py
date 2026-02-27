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

from agelclaw.project import get_project_dir, get_db_path, get_skills_dir, get_subagents_dir

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

## MEMORY & SKILL CLI
Use `agelclaw-mem <command>` via Bash for ALL memory and skill operations:

### Memory commands:
  agelclaw-mem context                          # Full context summary
  agelclaw-mem pending [limit]                  # Pending tasks (ready now)
  agelclaw-mem due                              # Due scheduled tasks
  agelclaw-mem scheduled                        # Future scheduled tasks
  agelclaw-mem completed                        # Recently completed tasks
  agelclaw-mem all_tasks [limit]                # All recent tasks (any status)
  agelclaw-mem get_task <id>                    # Full task details + result + files
  agelclaw-mem stats                            # Task statistics
  agelclaw-mem start_task <id>                  # Mark task in_progress
  agelclaw-mem complete_task <id> "<result>"    # Mark task completed
  agelclaw-mem fail_task <id> "<error>"         # Mark task failed
  agelclaw-mem add_task "<title>" "<desc>" [pri] [due_at] [recurring]
  agelclaw-mem log "<message>"                  # Log a message
  agelclaw-mem add_learning "<cat>" "<content>" # Add a learning
  agelclaw-mem get_learnings [category]         # Get learnings
  agelclaw-mem rules                            # List active hard rules
  agelclaw-mem promote_rule <id>                # Promote learning → hard rule
  agelclaw-mem demote_rule <id>                 # Demote rule → regular learning

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
  agelclaw-mem create_subagent <name> "<desc>" "<body>"

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

## TASK MANAGEMENT
- Create tasks for background/scheduled work: `agelclaw-mem add_task "<title>" "<desc>" [pri] [due_at] [recurring]`
- The daemon executes background tasks autonomously — you handle interactive requests directly.
- After creating a task, ALWAYS tell the user "Task #N created".
- To wake the daemon immediately: `curl -s -X POST http://localhost:8420/wake`

## SUBAGENT CREATION — MANDATORY RULES
When the user asks to "create a subagent", "δημιούργησε subagent", "φτιάξε subagent", or mentions specialized/parallel agent execution, you MUST follow ALL these steps IN ORDER:

1. **Create the subagent definition** (SUBAGENT.md with specialized prompt):
   ```
   agelclaw-mem create_subagent <name> "<description>" "<detailed specialist prompt>"
   ```
   The body MUST be a complete specialist prompt — NOT a placeholder. Write it as if instructing an expert.

2. **Create the task ASSIGNED to the subagent** (NOT a global task):
   ```
   agelclaw-mem add_subagent_task <name> "<title>" "<detailed description>" [priority]
   ```
   This creates a task with `assigned_to=<name>`, so the daemon routes it to the subagent.

3. **Wake the daemon**:
   ```
   curl -s -X POST http://localhost:8420/wake
   ```

4. **Tell the user**: "Δημιουργήθηκε ο subagent '<name>' με task #N — ο daemon θα το εκτελέσει."

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

## CRITICAL RULES (MUST FOLLOW)
- Respond in the same language the user uses
- Be concise and helpful
- NEVER say "you can run this command" — RUN IT YOURSELF or delegate to daemon
- You MUST use the bash tool to run `agelclaw-mem` commands when you need to CREATE/UPDATE data — DO NOT guess or assume
- NEVER claim something doesn't exist without checking first via bash
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


import time as _time
_prompt_cache = {"text": None, "ts": 0}
_PROMPT_CACHE_TTL = 120  # seconds — rebuild every 2 min


def get_system_prompt() -> str:
    """Build the full system prompt with dynamically scanned skills, subagents, and hard rules.
    Cached for 120s to avoid filesystem scanning on every message."""
    now = _time.time()
    if _prompt_cache["text"] and (now - _prompt_cache["ts"]) < _PROMPT_CACHE_TTL:
        return _prompt_cache["text"]

    from agelclaw.memory import Memory
    mem = Memory()
    result = _SYSTEM_PROMPT_BASE + _scan_installed_skills() + _scan_installed_subagents() + mem.build_rules_prompt()
    _prompt_cache["text"] = result
    _prompt_cache["ts"] = now
    return result


# SYSTEM_PROMPT is now dynamic — use get_system_prompt() instead
# This static alias is kept for backwards compatibility at import time
SYSTEM_PROMPT = get_system_prompt()


def build_prompt_with_history(user_text: str, memory) -> str:
    """Build prompt with recent conversation history + fast keyword recall.

    Shared between api_server.py and telegram_bot.py so both channels
    see the same unified conversation memory.

    Performance: uses only SQLite queries (no external API calls).
    Semantic search is available on-demand via `agelclaw-mem search "..."`.
    """
    session_id = SHARED_SESSION_ID

    # Recent messages (last 10 pairs = 20 messages) — instant SQLite query
    recent = memory.get_conversation_history(session_id=session_id, limit=20)

    if not recent:
        return user_text

    # Fast keyword recall from older conversations — SQLite LIKE only, no embedding API
    relevant_older = _find_relevant_history_fast(user_text, session_id, recent)

    context_parts = []

    if relevant_older:
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
        if msg["role"] == "assistant" and len(content) > 500:
            content = content[:500] + "..."
        context_parts.append(f"{prefix}: {content}")

    context_parts.append(f"\nUser (latest): {user_text}")

    return (
        "Previous conversation context (from memory):\n"
        + "\n\n".join(context_parts)
        + "\n\nRespond to the latest user message. You have full context of what was discussed before."
        + "\n\nREMINDER: You have ALL tools available (Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch). "
        + "Use `agelclaw-mem` via Bash for memory/skill/task operations. "
        + "For deeper memory recall, run `agelclaw-mem search \"query\"` (semantic search). "
        + "Execute work directly — don't just delegate unless it's a background/scheduled task."
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


def build_agent_options(max_turns: int = 30) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for chat/telegram agents (full tool set)."""
    return ClaudeAgentOptions(
        system_prompt=get_system_prompt(),
        allowed_tools=AGENT_TOOLS,
        setting_sources=["user", "project"],
        permission_mode="bypassPermissions",
        cwd=str(PROACTIVE_DIR),
        max_turns=max_turns,
    )


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
