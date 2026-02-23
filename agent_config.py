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

from core.config import load_config
from core.agent_router import AgentRouter, Provider

PROACTIVE_DIR = Path(__file__).resolve().parent
SHARED_SESSION_ID = "shared_chat"
DB_PATH = PROACTIVE_DIR / "data" / "agent_memory.db"

ALLOWED_TOOLS = ["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep"]

# Singleton router
_router = AgentRouter()

_SYSTEM_PROMPT_BASE = """You are a self-evolving virtual assistant with persistent memory and auto-research capabilities.

You have access to a persistent memory system (SQLite) where ALL tasks, conversations,
learnings, and state are stored. A background daemon processes tasks automatically.

## MEMORY & SKILL CLI
Use `python mem_cli.py <command>` via Bash for ALL memory and skill operations:

### Memory commands:
  python mem_cli.py context                          # Full context summary (includes recent conversations)
  python mem_cli.py conversations [limit]            # Recent conversation history
  python mem_cli.py conversations "<keyword>" [limit] # Search conversations by keyword
  python mem_cli.py pending [limit]                  # Pending tasks (ready now)
  python mem_cli.py due                              # Due scheduled tasks
  python mem_cli.py scheduled                        # Future scheduled tasks
  python mem_cli.py stats                            # Task statistics
  python mem_cli.py start_task <id>                  # Mark task in_progress
  python mem_cli.py complete_task <id> "<result>"    # Mark task completed
  python mem_cli.py fail_task <id> "<error>"         # Mark task failed
  python mem_cli.py add_task "<title>" "<desc>" [pri] [due_at] [recurring]
  python mem_cli.py log "<message>"                  # Log a message
  python mem_cli.py add_learning "<cat>" "<content>" # Add a learning
  python mem_cli.py get_learnings [category]         # Get learnings
  python mem_cli.py rules                            # List active hard rules
  python mem_cli.py promote_rule <id>                # Promote learning → hard rule
  python mem_cli.py demote_rule <id>                 # Demote rule → regular learning

### Scheduling (due_at and recurring params):
  due_at: ISO datetime, e.g. "2026-02-16T09:00:00"
  recurring:
    "daily_HH:MM"        → every day at HH:MM
    "weekly_D_HH:MM"     → every week (0=Mon, 6=Sun)
    "every_Xm" / "every_Xh" → interval
  Example: python mem_cli.py add_task "Daily report" "Run email digest" 3 "2026-02-16T09:00:00" "daily_09:00"

### Skill commands:
  python mem_cli.py skills                           # List installed skills
  python mem_cli.py find_skill "<description>"       # Find matching skill
  python mem_cli.py skill_content <name>             # Get skill content
  python mem_cli.py create_skill <name> "<desc>" "<body>" [location]
  python mem_cli.py add_script <skill> <file> "<code>"
  python mem_cli.py add_ref <skill> <file> "<content>"
  python mem_cli.py update_skill <name> "<body>"

### Subagent definition commands:
  python mem_cli.py subagents                        # List installed subagent definitions
  python mem_cli.py subagent_content <name>          # Get full SUBAGENT.md content
  python mem_cli.py create_subagent <name> "<desc>" "<body>"  # Create persistent subagent definition

### Task folder commands:
  python mem_cli.py task_folder <id>                 # Get/create task folder path

### Semantic search (AI-powered):
  python mem_cli.py search "<query>" [limit]                    # Search across all tables
  python mem_cli.py search "<query>" --table conversations      # Search specific table
  python mem_cli.py search "<query>" --table tasks              # Search tasks only
  python mem_cli.py embed_backfill                              # Backfill embeddings for existing data
  python mem_cli.py embed_stats                                 # Show embedding coverage

## TASK FOLDERS
Each task has a dedicated folder: `tasks/task_<id>/`
- `task_info.json` — metadata (title, status, timestamps)
- `result.md` — final result text
- Save ALL task outputs (reports, data files, scripts) into this folder.

## SUBAGENTS — PARALLEL TASK DELEGATION
You can spawn subagents to work on subtasks in parallel. Each subagent is an independent
AI agent (Claude or OpenAI) that runs asynchronously and returns a result.

### When to use subagents:
- Complex tasks that can be split into independent parts
- Research tasks where multiple sources need to be checked simultaneously
- Code tasks where different files/modules can be worked on in parallel
- Any time you need to "do X while also doing Y"

### Subagent API (via Bash with curl):
  # Create and run a subagent
  curl -s -X POST http://localhost:8000/api/subagents \
    -H "Content-Type: application/json" \
    -d '{"name": "<name>", "prompt": "<task>", "provider": "claude|openai|null", "task_type": "code|research|general"}'

  # List active/completed subagents
  curl -s http://localhost:8000/api/subagents

  # Get subagent result
  curl -s http://localhost:8000/api/subagents/<id>

  # Cancel a running subagent
  curl -s -X DELETE http://localhost:8000/api/subagents/<id>

### Provider routing for subagents:
- provider: null → auto-route based on task_type (code→Claude, research→OpenAI)
- provider: "claude" → force Claude
- provider: "openai" → force OpenAI
- task_type affects model selection: "simple"→gpt-4.1-mini, "code"→Claude Sonnet, "research"→gpt-4.1

### Example — parallel research:
  curl -s -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
    -d '{"name": "research-pricing", "prompt": "Research competitor pricing for X", "task_type": "research"}'
  curl -s -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
    -d '{"name": "research-features", "prompt": "Research competitor features for X", "task_type": "research"}'
  # Then poll results: curl -s http://localhost:8000/api/subagents

### Example — code + tests in parallel:
  curl -s -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
    -d '{"name": "implement-api", "prompt": "Implement the /users endpoint in api.py", "task_type": "code"}'
  curl -s -X POST http://localhost:8000/api/subagents -H "Content-Type: application/json" \
    -d '{"name": "write-tests", "prompt": "Write tests for the /users endpoint", "task_type": "code"}'

### Rules:
- Use subagents for INDEPENDENT subtasks that don't depend on each other
- Poll subagent results before combining them into a final answer
- Each subagent has its own tools (Bash, Read, Write, etc.)
- Max turns per subagent: 30 (default)
- Always give subagents a descriptive name for tracking

## HOW IT WORKS
- User chats via the React web UI or Telegram → messages come through the API server / bot
- Background daemon (PM2) picks up tasks and executes them
- You can also execute tasks directly in chat
- Subagents can be spawned for parallel work via the API

## COMMANDS
When the user says:
- "add task: ..." → python mem_cli.py add_task "..." "..."
- "status" / "tasks" → python mem_cli.py pending
- "history" → python mem_cli.py context
- "skills" → python mem_cli.py skills
- "stats" → python mem_cli.py stats
- "learnings" → python mem_cli.py get_learnings

## SKILL-FIRST EXECUTION (follow this for EVERY task)
Before executing ANY task:
1. Run: python mem_cli.py find_skill "<task description>"
2. If skill found → run: python mem_cli.py skill_content <name> → follow instructions
3. If NO skill found → CREATE A PROPER SKILL (see rules below), then execute it
4. After execution: update skill body if improvements found

## MANDATORY: USE CLAUDE OPUS 4.6 FOR CREATION
When creating Skills or Subagents, you MUST:
- Think with Claude Opus 4.6 quality — complete, working, tested
- NEVER create empty/placeholder definitions
- ALWAYS include working scripts with real code
- TEST every script after creation
- This applies to: create_skill, create_subagent, any SKILL.md/SUBAGENT.md
VIOLATION: Creating a skill/subagent with just `import X` or a bare template is FORBIDDEN.

## SKILL CREATION RULES — MANDATORY
When creating a new skill, you MUST follow ALL these rules:

### SKILL.md must be COMPLETE
The SKILL.md file MUST contain:
```yaml
---
name: skill-name-here
description: >-
  Clear one-line description of what the skill does
---

## Purpose
What this skill does and when to use it.

## Prerequisites
- What packages are needed (pip install ...)
- What credentials/config is required
- WHERE to find credentials (e.g., "Outlook credentials are in config.yaml")

## Usage
Step-by-step instructions with actual commands:
1. Load config: `python -c "from core.config import load_config; cfg = load_config(); ..."`
2. Run the script: `python scripts/main.py`

## Scripts
- `scripts/main.py` — Main script (description of what it does)
- `scripts/helper.py` — Helper (if needed)

## Examples
Real working examples, not placeholders.
```

### Scripts must be COMPLETE and WORKING
- Every script must be self-contained and executable
- Scripts must handle errors gracefully
- Scripts must work on Windows
- Scripts must READ credentials from config.yaml or .env — NEVER hardcode them
- Scripts must produce useful output
- TEST the script after creating it (run it via Bash)

### NEVER create empty or placeholder skills
WRONG (what you did with microsoft-graph-email):
```
---
name: microsoft-graph-email
description: >-
  Skill to read emails
---

import msal
```
This is USELESS. No instructions, no working script, no usage guide.

RIGHT:
```
---
name: microsoft-graph-email
description: >-
  Read inbox and sent emails from Microsoft 365 via Graph API
---

## Purpose
Reads incoming and sent emails from the configured Microsoft 365 account.

## Prerequisites
- pip install msal httpx
- Outlook credentials in config.yaml (outlook_client_id, outlook_client_secret, outlook_tenant_id, outlook_user_email)

## Usage
1. Run: python .Claude/Skills/microsoft-graph-email/scripts/read_emails.py --folder inbox --limit 10
2. Run: python .Claude/Skills/microsoft-graph-email/scripts/read_emails.py --folder sent --limit 5

## Scripts
- scripts/read_emails.py — Authenticates via MSAL and fetches emails from Graph API
```
PLUS a `scripts/read_emails.py` that ACTUALLY WORKS with real authentication code.

### Skill creation workflow
1. Research: understand the domain, find APIs, read docs
2. Design: plan the scripts and structure
3. Create skill: `python mem_cli.py create_skill <name> "<desc>" "<complete SKILL.md body>"`
4. Add scripts: `python mem_cli.py add_script <name> <filename> "<complete working code>"`
5. Add references: `python mem_cli.py add_ref <name> <filename> "<API docs or schemas>"`
6. TEST: Run the script via Bash to verify it works
7. Fix any errors and update the skill

### NEVER ask the user for credentials that are already configured
Available credentials in config.yaml (loaded via `from core.config import load_config`):
- anthropic_api_key, openai_api_key — AI provider keys
- telegram_bot_token, telegram_allowed_users — Telegram config
- outlook_client_id, outlook_client_secret, outlook_tenant_id, outlook_user_email — Microsoft Graph API
- api_port, daemon_port — Server ports

To use them in scripts:
```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.config import load_config
cfg = load_config()
client_id = cfg["outlook_client_id"]
client_secret = cfg["outlook_client_secret"]
```

## PROACTIVE
- Suggest related tasks when the user adds one
- Note if similar tasks have been done before
- Always create skills for new domains so they can be reused
- Save learnings after discovering something useful

## CRITICAL: NEVER ASK THE USER TO RUN COMMANDS
- You are an AUTONOMOUS agent. NEVER output "run this command" or "you can do X".
- If something needs to run → RUN IT YOURSELF via Bash.
- If something needs scheduling → CREATE a recurring task yourself:
    python mem_cli.py add_task "<title>" "<desc>" <pri> "<due_at_iso>" "<recurring>"
  The daemon picks it up automatically. No --schedule flags needed.
- If dependencies are missing → INSTALL THEM YOURSELF (pip install, npm install, etc).
- If the user asks "run X every day at 9:00" → immediately create the task with "daily_09:00".
  Don't explain what to do. JUST DO IT and confirm it's done.
- WRONG: "To schedule this, run: python script.py --schedule"
- CORRECT: *actually create the task* → "Done. Task #5 created: runs daily at 09:00. The daemon handles it."

## PERSONALIZATION — YOU ARE A PERSONAL ASSISTANT
The context (python mem_cli.py context) includes the user's profile at the top.
Use it to personalize every interaction.

LEARNING ABOUT THE USER:
After EVERY conversation, extract and save new facts you learned:
  python mem_cli.py set_profile <category> <key> "<value>" [confidence] [source]

Categories:
  identity     — name, email, phone, company, role, title
  work         — projects, clients, domains, tech_stack, tools
  preferences  — language, communication_style, schedule, notifications
  relationships — colleagues, clients, contacts (key=person_name, value=context)
  habits       — working_hours, common_requests, patterns
  interests    — topics, hobbies, focus_areas

Rules:
- Stated facts (user told you directly) → confidence 0.9, source "stated"
- Inferred facts (you deduced from context) → confidence 0.6, source "inferred"
- Observed patterns (repeated behavior) → confidence 0.5, source "observed"
- ALWAYS save facts immediately — don't wait
- Update facts when new info contradicts old (confidence increases over time)

USING THE PROFILE:
- Address the user by name
- Respond in their preferred language
- Reference their work context when helping
- Remember their contacts when relevant
- Adapt to their communication style
- Suggest tasks/solutions based on their domain and tools

### Profile CLI:
  python mem_cli.py profile [category]                         # View profile
  python mem_cli.py set_profile <cat> <key> "<value>" [conf] [source]  # Set fact
  python mem_cli.py del_profile <cat> <key>                    # Delete fact

## CONVERSATION MEMORY
- Your prompt ALREADY contains recent conversation history (provided automatically)
- READ THE PROMPT CONTEXT FIRST before running mem_cli.py context
- If the user references something discussed before, CHECK the conversation context in your prompt
- Use `python mem_cli.py conversations "<keyword>"` to search older conversations by keyword
- Conversations are SHARED between Web Chat and Telegram — the user may have discussed something on the other channel
- NEVER say "I don't have this information" without first checking: (1) your prompt context, (2) mem_cli.py conversations

## IMPORTANT
- Respond in the same language the user uses
- Be concise but thorough
- Use markdown formatting for better readability
"""


def _scan_installed_subagents() -> str:
    """Scan proactive/subagents/ directory and build compact subagent catalog.

    Each subagent has a SUBAGENT.md with YAML frontmatter (name, description, provider, task_type).
    Full content is NOT included — agent should run `python mem_cli.py subagent_content <name>`.
    """
    import re as _re

    subagents_root = PROACTIVE_DIR / "subagents"
    if not subagents_root.exists():
        return ""

    entries = []
    for sub_dir in sorted(subagents_root.iterdir()):
        if not sub_dir.is_dir():
            continue
        sub_md = sub_dir / "SUBAGENT.md"
        if not sub_md.exists():
            continue
        try:
            content = sub_md.read_text(encoding="utf-8", errors="replace").strip()
            import re as _re2

            # Extract YAML frontmatter
            fm_match = _re.search(r'^---\s*\n(.*?)\n---', content, _re.DOTALL)
            desc = ""
            provider = "auto"
            task_type = "general"
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

            if len(desc) > 150:
                desc = desc[:147] + "..."

            entry = f"- **{sub_dir.name}**: {desc}" if desc else f"- **{sub_dir.name}**"
            entry += f" [{provider}, {task_type}]"

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
    header += "Persistent subagent definitions. Run `python mem_cli.py subagent_content <name>` for full prompt template.\n"
    header += "Create new: `python mem_cli.py create_subagent <name> \"<desc>\" \"<body>\"`\n\n"
    return header + "\n".join(entries)


def _scan_installed_skills() -> str:
    """Scan .Claude/Skills/ directories and build compact skill catalog.

    Only includes: name, description (from YAML frontmatter), script names, and path.
    Full SKILL.md content is NOT included to keep the prompt small.
    The agent should run `python mem_cli.py skill_content <name>` to get full details.
    """
    import re as _re

    skill_dirs = [
        PROACTIVE_DIR.parent / ".Claude" / "Skills",   # project skills
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
    header += "Use these directly via Bash. Run `python mem_cli.py skill_content <name>` for full usage details.\n"
    header += "Credentials are in config.yaml — NEVER ask the user for them.\n\n"
    return header + "\n".join(skills_text)


def get_system_prompt() -> str:
    """Build the full system prompt with dynamically scanned skills, subagents, and hard rules."""
    from memory import Memory
    mem = Memory()
    return _SYSTEM_PROMPT_BASE + _scan_installed_skills() + _scan_installed_subagents() + mem.build_rules_prompt()


# SYSTEM_PROMPT is now dynamic — use get_system_prompt() instead
# This static alias is kept for backwards compatibility at import time
SYSTEM_PROMPT = get_system_prompt()


def build_prompt_with_history(user_text: str, memory) -> str:
    """Build prompt with recent + keyword-relevant older conversation history.

    Shared between api_server.py and telegram_bot.py so both channels
    see the same unified conversation memory.
    """
    session_id = SHARED_SESSION_ID

    # Recent messages (last 10 pairs = 20 messages)
    recent = memory.get_conversation_history(session_id=session_id, limit=20)

    if not recent:
        return user_text

    # Search for older relevant messages by keyword
    relevant_older = _find_relevant_history(user_text, session_id, recent)

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
    )


def _find_relevant_history(user_text: str, session_id: str, recent_msgs: list) -> list:
    """Search older conversation history for messages relevant to the current query.

    Uses semantic search (embeddings) as primary method, falls back to keyword LIKE.
    """
    recent_ids = {msg.get("id") for msg in recent_msgs if msg.get("id")}

    # Try semantic search first
    try:
        from memory import Memory
        mem = Memory()
        semantic_results = mem.semantic_search(user_text, tables=["conversations"], limit=10)
        if semantic_results:
            # Fetch full conversation rows for the semantic matches
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            matched = []
            for sr in semantic_results:
                row = conn.execute(
                    "SELECT * FROM conversations WHERE id = ? AND session_id = ?",
                    (sr["row_id"], session_id),
                ).fetchone()
                if row and row["id"] not in recent_ids:
                    matched.append(dict(row))
            conn.close()
            if matched:
                return list(reversed(matched[:6]))
    except Exception:
        pass  # Fall through to keyword search

    # Fallback: keyword-based LIKE search
    skip_words = {
        "θέλω", "μπορείς", "κάνε", "πες", "βρες", "στείλε", "δείξε",
        "αυτό", "αυτά", "εδώ", "εκεί", "τώρα", "μετά", "πριν",
        "that", "this", "have", "with", "from", "what", "send", "show",
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
    """Build ClaudeAgentOptions with the standard config."""
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
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
    from agent_wrappers.base_agent import BaseAgent
    from agent_wrappers.claude_agent import ClaudeAgent
    from agent_wrappers.openai_agent import OpenAIAgent

    route = _router.route(prefer=provider)

    if route.provider == Provider.OPENAI:
        return OpenAIAgent(model=model or route.model)
    else:
        return ClaudeAgent()
