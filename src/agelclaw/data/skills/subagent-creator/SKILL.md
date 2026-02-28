---
name: subagent-creator
description: Create subagent definitions (SUBAGENT.md + scripts + references). Use when user asks to create a subagent, specialized agent, background worker, or parallel agent. Triggers on "δημιούργησε subagent", "φτιάξε subagent", "create subagent", "background agent".
---

# Subagent Creator

Guide for creating subagent definitions that run as autonomous background workers via the daemon.

## Subagent vs Skill vs Inline

| Use Case | Mechanism |
|----------|-----------|
| Quick one-off task (< 2 min) | Execute inline |
| Reusable procedure/knowledge | Create a **skill** |
| Long-running background work | Create a **subagent** |
| Recurring scheduled work | Create a **subagent** + recurring task |

**Rule**: If the task takes > 2 minutes, involves API calls + file generation + email, or needs to run on schedule — it MUST be a subagent.

## Subagent Structure

```
subagents/<name>/
├── SUBAGENT.md          # Definition (YAML frontmatter + specialist prompt)
├── scripts/             # Executable scripts (Python, Bash)
│   ├── main.py          # Primary execution script
│   └── helpers.py       # Supporting utilities
└── references/          # Documentation, API specs, templates
    └── api_docs.md
```

## Step-by-Step Creation

### 1. Create the definition

```bash
agelclaw-mem create_subagent <name> "<description>" "<body>" [provider] [task_type] [tools]
```

Parameters:
- `name`: lowercase-kebab-case (e.g., `diavgeia-monitor`, `price-tracker`)
- `description`: one-line summary of what the subagent does
- `body`: the specialist prompt (detailed instructions)
- `provider`: `auto` (default), `claude`, or `openai`
- `task_type`: `general` (default), `code`, `research`, `email`
- `tools`: comma-separated tool list (default: all tools)

### 2. Add scripts (if needed)

```bash
agelclaw-mem add_subagent_script <name> <filename> "<code>"
```

For long scripts, use Write tool first, then reference:
```bash
# Write the script file directly
Write tool → subagents/<name>/scripts/main.py

# Or use add_subagent_script for short scripts
agelclaw-mem add_subagent_script diavgeia-monitor fetch.py "import requests..."
```

### 3. Add references (if needed)

```bash
agelclaw-mem add_subagent_ref <name> <filename> "<content>"
```

Use for API documentation, templates, org ID lists, etc.

### 4. Create an assigned task

```bash
agelclaw-mem add_subagent_task <name> "<title>" "<description>" [priority] [due_at] [recurring]
```

**CRITICAL**: Always use `add_subagent_task`, NEVER plain `add_task` for subagent work.

### 5. Wake the daemon

```bash
curl -s -X POST http://localhost:8420/wake
```

### 6. Confirm to user

Tell the user: "Δημιουργήθηκε ο subagent '<name>' με task #N."

## Writing Good SUBAGENT.md Bodies

The body is the specialist prompt injected into the agent's system prompt when executing subagent tasks. It must be:

1. **Self-contained** — don't assume context from the chat conversation
2. **Specific** — exact file paths, API endpoints, org IDs, email addresses
3. **Step-by-step** — numbered execution steps
4. **Script-aware** — reference scripts in `subagents/<name>/scripts/` by path

### Template:

```markdown
You are a specialist in [DOMAIN].

## YOUR MISSION
[One paragraph describing what this subagent does]

## RESOURCES
- Scripts: `subagents/<name>/scripts/`
- References: `subagents/<name>/references/`
- Output folder: use task folder (`agelclaw-mem task_folder <id>`)

## EXECUTION STEPS
1. [Step 1 — be specific]
2. [Step 2]
3. Save results to task folder
4. If email needed: use `agelclaw-mem find_skill "email"` → follow email skill
5. `agelclaw-mem complete_task <id> "<result summary in Greek>"`

## DATA
[Hardcoded data: API endpoints, org IDs, email addresses, etc.]

## RULES
- Execute ONLY the assigned task
- Save all output files to the task folder
- Complete_task result is sent as Telegram notification — write in Greek
```

## Common Patterns

### Data Fetcher + Report (e.g., Diavgeia, price tracker)
- Script: `scripts/fetch_data.py` (API calls, data processing)
- Script: `scripts/generate_report.py` (Excel/HTML generation)
- Reference: `references/org_ids.md` (target organizations)
- Body: orchestrate scripts, send email with results

### Web Scraper + Alert
- Script: `scripts/scrape.py` (BeautifulSoup/requests)
- Script: `scripts/compare.py` (diff with previous run)
- Reference: `references/targets.md` (URLs to monitor)
- Body: scrape, compare, alert on changes

### Document Generator
- Script: `scripts/generate.py` (docx/pdf/xlsx creation)
- Reference: `references/template.md` (document structure)
- Body: gather data, generate document, email

## Frontmatter Fields

```yaml
---
name: my-subagent
description: >-
  What this subagent does (shown in subagent catalog)
provider: auto          # auto | claude | openai
task_type: general      # general | code | research | email
tools:                  # Optional — restrict available tools
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
---
```

## Verification

After creating a subagent, verify:
1. `agelclaw-mem subagent_content <name>` — check SUBAGENT.md is well-formed
2. `ls subagents/<name>/scripts/` — check scripts exist
3. `python subagents/<name>/scripts/main.py --help` — test scripts run
4. `agelclaw-mem subagent_tasks <name>` — check task is assigned
