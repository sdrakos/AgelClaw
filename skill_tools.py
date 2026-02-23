"""
Skill Management Tools
======================
MCP tools for creating, finding, and managing Agent Skills.

Skills follow the official Claude Code format:
  skill-name/
  ├── SKILL.md       # YAML frontmatter + markdown body (<500 lines)
  ├── scripts/       # Executable Python/Bash scripts
  ├── references/    # Reference docs loaded as needed
  └── assets/        # Templates, icons (optional)

Tools:
  list_installed_skills  - List all skills with resource counts
  find_skill_for_task    - Check if a skill matches a task description
  get_skill_content      - Load full SKILL.md + list resources
  create_full_skill      - Create skill dir + SKILL.md + scripts/ + references/
  add_skill_script       - Add executable script to skill's scripts/
  add_skill_reference    - Add reference doc to skill's references/
  update_skill_body      - Update SKILL.md body preserving frontmatter
"""

import os
import re
from pathlib import Path
from claude_agent_sdk import tool
from memory import Memory

memory = Memory()

# ─────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_SKILLS_DIR = PROJECT_ROOT / ".Claude" / "Skills"
USER_SKILLS_DIR = Path.home() / ".claude" / "skills"
ALL_SKILL_DIRS = [PROJECT_SKILLS_DIR, USER_SKILLS_DIR]

# Valid skill name: lowercase, digits, hyphens, max 64 chars
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$|^[a-z0-9]$")


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _parse_frontmatter(content: str):
    """Parse YAML frontmatter from SKILL.md. Returns (name, description)."""
    if not content.startswith("---"):
        return None, None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, None
    name = desc = None
    for line in parts[1].strip().split("\n"):
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip("'\"")
    return name, desc


def _find_skill_dir(skill_name: str) -> Path | None:
    """Find a skill directory by name across all skill dirs."""
    for base in ALL_SKILL_DIRS:
        candidate = base / skill_name
        if candidate.is_dir() and (candidate / "SKILL.md").exists():
            return candidate
    return None


def _count_resources(skill_dir: Path) -> dict:
    """Count scripts, references, and assets in a skill dir."""
    counts = {}
    for subdir in ("scripts", "references", "assets"):
        d = skill_dir / subdir
        if d.is_dir():
            counts[subdir] = len([f for f in d.iterdir() if f.is_file()])
        else:
            counts[subdir] = 0
    return counts


def _tokenize(text: str) -> set[str]:
    """Simple tokenizer for keyword matching."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _ok(text: str) -> dict:
    """Return a standard MCP text response."""
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    """Return a standard MCP error response."""
    return {"content": [{"type": "text", "text": f"Error: {text}"}], "isError": True}


# ─────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────

@tool("list_installed_skills", "List all installed Agent Skills with resource counts (scripts, references, assets).", {})
async def list_installed_skills(args):
    skills = []
    for base in ALL_SKILL_DIRS:
        if not base.exists():
            continue
        for sd in sorted(base.iterdir()):
            sm = sd / "SKILL.md"
            if sd.is_dir() and sm.exists():
                name, desc = _parse_frontmatter(sm.read_text(encoding="utf-8"))
                counts = _count_resources(sd)
                location = "project" if base == PROJECT_SKILLS_DIR else "user"
                skills.append({
                    "name": name or sd.name,
                    "description": desc or "",
                    "location": location,
                    "path": str(sd),
                    **counts,
                })

    if not skills:
        return _ok("No skills installed.")

    lines = []
    for s in skills:
        res_parts = []
        if s["scripts"]:
            res_parts.append(f"{s['scripts']} scripts")
        if s["references"]:
            res_parts.append(f"{s['references']} refs")
        if s["assets"]:
            res_parts.append(f"{s['assets']} assets")
        res_str = f" ({', '.join(res_parts)})" if res_parts else ""
        lines.append(f"- **{s['name']}** [{s['location']}]{res_str}: {s['description'][:100]}")

    return _ok(f"## Installed Skills ({len(skills)})\n\n" + "\n".join(lines))


@tool(
    "find_skill_for_task",
    (
        "Check if an existing skill matches a task description. "
        "Returns the best matching skill with its full content, or 'No matching skill found'. "
        "Call this BEFORE executing any task to check for reusable skills."
    ),
    {"task_description": str},
)
async def find_skill_for_task(args):
    task_desc = args.get("task_description", "")
    if not task_desc:
        return _err("task_description is required.")

    task_tokens = _tokenize(task_desc)
    if not task_tokens:
        return _ok("No matching skill found.")

    best_match = None
    best_score = 0.0

    for base in ALL_SKILL_DIRS:
        if not base.exists():
            continue
        for sd in base.iterdir():
            sm = sd / "SKILL.md"
            if not (sd.is_dir() and sm.exists()):
                continue
            content = sm.read_text(encoding="utf-8")
            name, desc = _parse_frontmatter(content)
            skill_name = name or sd.name
            skill_desc = desc or ""

            # Build skill tokens from name + description + body
            skill_text = f"{skill_name} {skill_desc} {content}"
            skill_tokens = _tokenize(skill_text)

            if not skill_tokens:
                continue

            # Jaccard-like overlap: intersection / task_tokens size
            overlap = len(task_tokens & skill_tokens)
            score = overlap / len(task_tokens)

            if score > best_score:
                best_score = score
                best_match = {
                    "name": skill_name,
                    "description": skill_desc,
                    "score": round(score, 3),
                    "path": str(sd),
                    "content": content,
                }

    if best_match and best_score > 0.2:
        counts = _count_resources(Path(best_match["path"]))
        # Record usage in memory
        memory.record_skill_use(best_match["name"])
        return _ok(
            f"## Matching Skill Found: {best_match['name']} (score: {best_match['score']})\n\n"
            f"**Path:** {best_match['path']}\n"
            f"**Resources:** {counts.get('scripts', 0)} scripts, "
            f"{counts.get('references', 0)} references, {counts.get('assets', 0)} assets\n\n"
            f"### SKILL.md Content\n\n{best_match['content']}"
        )

    return _ok("No matching skill found.")


@tool(
    "get_skill_content",
    "Load the full SKILL.md content and list all resources (scripts, references, assets) for a skill.",
    {"skill_name": str},
)
async def get_skill_content(args):
    skill_name = args.get("skill_name", "")
    if not skill_name:
        return _err("skill_name is required.")

    skill_dir = _find_skill_dir(skill_name)
    if not skill_dir:
        return _err(f"Skill '{skill_name}' not found.")

    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    counts = _count_resources(skill_dir)

    # List actual files in each subdir
    resources = {}
    for subdir in ("scripts", "references", "assets"):
        d = skill_dir / subdir
        if d.is_dir():
            resources[subdir] = [f.name for f in sorted(d.iterdir()) if f.is_file()]
        else:
            resources[subdir] = []

    res_lines = []
    for subdir, files in resources.items():
        if files:
            res_lines.append(f"\n### {subdir}/")
            for f in files:
                res_lines.append(f"- {f}")

    resources_text = "\n".join(res_lines) if res_lines else "\n(no resources)"

    memory.record_skill_use(skill_name)
    return _ok(
        f"## Skill: {skill_name}\n\n"
        f"**Path:** {skill_dir}\n"
        f"**Resources:** {counts.get('scripts', 0)} scripts, "
        f"{counts.get('references', 0)} references, {counts.get('assets', 0)} assets\n"
        f"\n### SKILL.md\n\n{content}\n"
        f"\n## Resources{resources_text}"
    )


@tool(
    "create_full_skill",
    (
        "Create a new Agent Skill with proper directory structure: "
        "SKILL.md (YAML frontmatter + detailed body), scripts/, references/ dirs. "
        "The body should contain detailed instructions, prerequisites, examples, "
        "and usage patterns. After creating, use add_skill_script and "
        "add_skill_reference to add resources."
    ),
    {
        "name": str,           # lowercase, hyphens, digits, max 64 chars
        "description": str,    # short description for frontmatter (max 1024 chars)
        "body": str,           # markdown body for SKILL.md (detailed instructions)
        "location": str,       # "project" or "user" (default: "project")
    },
)
async def create_full_skill(args):
    name = args.get("name", "")
    description = args.get("description", "")
    body = args.get("body", "")
    location = args.get("location", "project")

    # Validate name
    if not name or not SKILL_NAME_RE.match(name):
        return _err(
            f"Invalid skill name '{name}'. Must be lowercase letters, digits, "
            "and hyphens only, 1-64 chars, start/end with alphanumeric."
        )

    # Validate description
    if not description:
        return _err("description is required.")
    if len(description) > 1024:
        return _err(f"description too long ({len(description)} chars, max 1024).")

    # Check for existing skill
    if _find_skill_dir(name):
        return _err(f"Skill '{name}' already exists. Use update_skill_body to modify it.")

    # Determine target directory
    if location == "user":
        base = USER_SKILLS_DIR
    else:
        base = PROJECT_SKILLS_DIR

    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)

    # Write SKILL.md with YAML frontmatter
    skill_md = f"""---
name: {name}
description: >-
  {description}
---

{body}
"""
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # Register in Memory SQLite
    memory.register_skill(name, description, str(skill_dir), location)

    return _ok(
        f"Skill '{name}' created at {skill_dir}\n\n"
        f"Structure:\n"
        f"  {name}/\n"
        f"  ├── SKILL.md\n"
        f"  ├── scripts/\n"
        f"  └── references/\n\n"
        f"Next: use add_skill_script and add_skill_reference to add resources."
    )


@tool(
    "add_skill_script",
    (
        "Add an executable script to a skill's scripts/ directory. "
        "Scripts should be self-contained Python or Bash files that handle errors "
        "and work cross-platform (especially Windows). "
        "Sets executable permission on Unix systems."
    ),
    {
        "skill_name": str,     # name of existing skill
        "filename": str,       # e.g. "scrape_hotels.py", "setup.sh"
        "content": str,        # full script content
    },
)
async def add_skill_script(args):
    skill_name = args.get("skill_name", "")
    filename = args.get("filename", "")
    content = args.get("content", "")

    if not skill_name:
        return _err("skill_name is required.")
    if not filename:
        return _err("filename is required.")
    if not content:
        return _err("content is required.")

    skill_dir = _find_skill_dir(skill_name)
    if not skill_dir:
        return _err(f"Skill '{skill_name}' not found.")

    # Sanitize filename
    if "/" in filename or "\\" in filename or ".." in filename:
        return _err("Invalid filename. Must not contain path separators or '..'.")

    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    script_path = scripts_dir / filename
    script_path.write_text(content, encoding="utf-8")

    # Set executable on Unix
    if os.name != "nt":
        os.chmod(script_path, 0o755)

    return _ok(f"Script '{filename}' added to {skill_name}/scripts/ ({len(content)} bytes)")


@tool(
    "add_skill_reference",
    (
        "Add a reference document to a skill's references/ directory. "
        "References are loaded as context when the skill is used. "
        "Good for API docs, schemas, configuration examples, etc."
    ),
    {
        "skill_name": str,     # name of existing skill
        "filename": str,       # e.g. "api_docs.md", "schema.json"
        "content": str,        # reference content
    },
)
async def add_skill_reference(args):
    skill_name = args.get("skill_name", "")
    filename = args.get("filename", "")
    content = args.get("content", "")

    if not skill_name:
        return _err("skill_name is required.")
    if not filename:
        return _err("filename is required.")
    if not content:
        return _err("content is required.")

    skill_dir = _find_skill_dir(skill_name)
    if not skill_dir:
        return _err(f"Skill '{skill_name}' not found.")

    # Sanitize filename
    if "/" in filename or "\\" in filename or ".." in filename:
        return _err("Invalid filename. Must not contain path separators or '..'.")

    refs_dir = skill_dir / "references"
    refs_dir.mkdir(exist_ok=True)

    ref_path = refs_dir / filename
    ref_path.write_text(content, encoding="utf-8")

    return _ok(f"Reference '{filename}' added to {skill_name}/references/ ({len(content)} bytes)")


@tool(
    "update_skill_body",
    (
        "Update the SKILL.md body of an existing skill while preserving its YAML frontmatter. "
        "Use this to add learnings, improve instructions, or fix issues after using a skill."
    ),
    {
        "skill_name": str,     # name of existing skill
        "new_body": str,       # new markdown body (replaces everything after frontmatter)
    },
)
async def update_skill_body(args):
    skill_name = args.get("skill_name", "")
    new_body = args.get("new_body", "")

    if not skill_name:
        return _err("skill_name is required.")
    if not new_body:
        return _err("new_body is required.")

    skill_dir = _find_skill_dir(skill_name)
    if not skill_dir:
        return _err(f"Skill '{skill_name}' not found.")

    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    # Extract frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            updated = f"---{frontmatter}---\n\n{new_body}\n"
        else:
            updated = f"{content.rstrip()}\n\n{new_body}\n"
    else:
        updated = f"{new_body}\n"

    skill_md.write_text(updated, encoding="utf-8")

    return _ok(f"SKILL.md body updated for '{skill_name}' ({len(new_body)} chars)")


# ─────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────

ALL_SKILL_TOOLS = [
    list_installed_skills,
    find_skill_for_task,
    get_skill_content,
    create_full_skill,
    add_skill_script,
    add_skill_reference,
    update_skill_body,
]
