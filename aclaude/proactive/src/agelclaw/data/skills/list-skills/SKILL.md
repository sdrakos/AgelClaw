---
name: list-skills
description: List all available Claude skills dynamically. Use when user asks "what skills are available", "list skills", "show skills", "/list-skills", "/help skills", or wants to see what capabilities are installed.
---

# List Skills

Dynamically discover and display all available skills in the current project.

## Usage

When user asks about available skills, run:

```bash
python .claude/skills/list-skills/scripts/list_skills.py
```

## Output Format

The script outputs a formatted table with:
- **Name**: Skill name (use with `/skill-name`)
- **Description**: What the skill does and when to use it

## Example Output

```
Available Skills (9 total)
================================================================================
Name                     | Description
--------------------------------------------------------------------------------
docx                     | Work with Word documents (.docx files)...
pdf                      | Process PDF files with Python and CLI tools...
xlsx                     | Create, edit, and analyze Excel spreadsheets...
...
================================================================================

To use a skill, invoke it with: /skill-name
Example: /translation, /pdf, /docx
```

## How It Works

1. Scans `.claude/skills/` directory for subdirectories
2. Reads `SKILL.md` from each skill folder
3. Parses YAML frontmatter to extract `name` and `description`
4. Displays formatted list

## Notes

- Skills without valid YAML frontmatter are skipped
- The script works on Windows, Linux, and macOS
- Run from project root directory
