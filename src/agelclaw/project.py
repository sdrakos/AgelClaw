"""
Project Directory Management
==============================
Resolves the user's project directory (mutable data) vs package directory (immutable code).

Resolution order for project directory:
  1. AGELCLAW_HOME environment variable (explicit)
  2. Current working directory if it contains config.yaml or .agelclaw marker
  3. ~/.agelclaw/ default

Package data (immutable, bundled in the wheel):
  src/agelclaw/data/react_dist/    — Pre-built React UI
  src/agelclaw/data/skills/        — Default skill definitions
  src/agelclaw/data/templates/     — config.yaml.example, .env.example, ecosystem.config.js
"""

import os
import shutil
from functools import lru_cache
from pathlib import Path


# ── Package data (immutable) ──────────────────────────────────

def get_package_data_dir() -> Path:
    """Return the path to bundled package data (inside site-packages)."""
    return Path(__file__).parent / "data"


def get_react_dist_dir() -> Path:
    """Return the path to the bundled React UI build."""
    return get_package_data_dir() / "react_dist"


def get_bundled_skills_dir() -> Path:
    """Return the path to bundled default skills."""
    return get_package_data_dir() / "skills"


def get_templates_dir() -> Path:
    """Return the path to bundled config templates."""
    return get_package_data_dir() / "templates"


# ── Project directory (mutable user data) ─────────────────────

@lru_cache(maxsize=1)
def get_project_dir() -> Path:
    """Resolve the project directory for mutable user data.

    Resolution order:
      1. AGELCLAW_HOME env var
      2. CWD if it contains config.yaml or .agelclaw marker
      3. ~/.agelclaw/
    """
    # 1. Explicit env var
    env_home = os.environ.get("AGELCLAW_HOME")
    if env_home:
        p = Path(env_home).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. CWD markers
    cwd = Path.cwd()
    if (cwd / "config.yaml").exists() or (cwd / ".agelclaw").exists():
        return cwd

    # 3. Default
    default = Path.home() / ".agelclaw"
    default.mkdir(parents=True, exist_ok=True)
    return default


def reset_project_dir():
    """Clear the cached project directory (useful after setting AGELCLAW_HOME)."""
    get_project_dir.cache_clear()


# ── Convenience helpers for common paths ──────────────────────

def get_db_path() -> Path:
    """Path to the SQLite memory database."""
    data_dir = get_project_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "agent_memory.db"


def get_config_path() -> Path:
    """Path to config.yaml."""
    return get_project_dir() / "config.yaml"


def get_env_path() -> Path:
    """Path to .env file."""
    return get_project_dir() / ".env"


def get_log_dir() -> Path:
    """Path to logs directory."""
    d = get_project_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_tasks_dir() -> Path:
    """Path to tasks output directory."""
    d = get_project_dir() / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_subagents_dir() -> Path:
    """Path to subagent definitions directory."""
    d = get_project_dir() / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_skills_dir() -> Path:
    """Path to the project's .Claude/Skills directory."""
    d = get_project_dir() / ".Claude" / "Skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_reports_dir() -> Path:
    """Path to reports directory."""
    d = get_project_dir() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_persona_dir() -> Path:
    """Path to persona directory (SOUL.md, IDENTITY.md, etc.)."""
    d = get_project_dir() / "persona"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Project initialization ────────────────────────────────────

def init_project(path: Path | str | None = None) -> Path:
    """Initialize a new project directory with required structure.

    Creates:
      - data/           (SQLite DB will be created here)
      - logs/
      - tasks/
      - subagents/
      - reports/
      - .Claude/Skills/ (copies bundled default skills)
      - config.yaml     (from template)
      - .env            (from template)
      - .agelclaw       (marker file)
      - ecosystem.config.js (from template)

    Returns the project directory path.
    """
    if path is None:
        project = get_project_dir()
    else:
        project = Path(path).resolve()
        project.mkdir(parents=True, exist_ok=True)

    # Create directories
    for subdir in ("data", "logs", "tasks", "subagents", "reports"):
        (project / subdir).mkdir(parents=True, exist_ok=True)

    skills_dir = project / ".Claude" / "Skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Marker file
    marker = project / ".agelclaw"
    if not marker.exists():
        marker.write_text("# AgelClaw project directory\n", encoding="utf-8")

    # Copy templates
    templates = get_templates_dir()
    for template_name, target_name in [
        ("config.yaml.example", "config.yaml"),
        (".env.example", ".env"),
        ("ecosystem.config.js", "ecosystem.config.js"),
    ]:
        src = templates / template_name
        dst = project / target_name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # Copy bundled skills
    bundled_skills = get_bundled_skills_dir()
    if bundled_skills.exists():
        for skill_src in bundled_skills.iterdir():
            if skill_src.is_dir():
                skill_dst = skills_dir / skill_src.name
                if not skill_dst.exists():
                    shutil.copytree(skill_src, skill_dst)

    # Copy persona templates (SOUL.md, IDENTITY.md, BOOTSTRAP.md, HEARTBEAT.md)
    persona_dir = project / "persona"
    persona_dir.mkdir(parents=True, exist_ok=True)
    for persona_file in ("SOUL.md", "IDENTITY.md", "BOOTSTRAP.md", "HEARTBEAT.md"):
        src = templates / persona_file
        dst = persona_dir / persona_file
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    return project
