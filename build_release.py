"""
Build Release Script
====================
Creates zip distribution for GitHub Releases (standalone installer).

  python build_release.py                Build zip
  python build_release.py --version 3.2  Override version

For pip package development:
  Edit src/agelclaw/ directly, then: pip install -e ".[all]"
"""

import argparse
import os
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

PROACTIVE_DIR = Path(__file__).parent
VERSION = "3.1.0"

# ─────────────────────────────────────────────────────────
# Build zip (standalone installer for GitHub Releases)
# ─────────────────────────────────────────────────────────

ZIP_INCLUDE = [
    "agent_config.py", "api_server.py", "cli.py", "daemon_v2.py",
    "embeddings.py", "install.py", "launcher.py", "mem_cli.py",
    "memory.py", "memory_tools.py", "outlook_digest.py", "skill_tools.py",
    "telegram_bot.py", "ecosystem.config.js", "config.yaml.example",
    "requirements.txt", "start.bat", "start.sh", "README.md", "MANUAL.md",
    "core/", "agent_wrappers/", "skills/", "scripts/", "subagents/",
    "react-claude-chat/dist/", "react-claude-chat/package.json",
]

EXCLUDE_PATTERNS = [
    "__pycache__", "node_modules", ".git", ".env",
    "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db", "nul",
]


def _should_exclude(path: Path) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.name.endswith(pattern[1:]):
                return True
        elif pattern in path.parts or path.name == pattern:
            return True
    return False


def build_zip(version: str):
    """Create the release zip."""
    print(f"[zip] Building AgelClaw-v{version} zip...")

    # Build React if needed
    dist = PROACTIVE_DIR / "react-claude-chat" / "dist"
    if dist.exists() and (dist / "index.html").exists():
        print("  React build found")
    else:
        print("  Building React UI...")
        react_dir = PROACTIVE_DIR / "react-claude-chat"
        if not (react_dir / "node_modules").exists():
            subprocess.run(["npm", "install"], cwd=str(react_dir), check=True)
        subprocess.run(["npm", "run", "build"], cwd=str(react_dir), check=True)

    zip_name = f"AgelClaw-v{version}-win64.zip"
    zip_path = PROACTIVE_DIR / "dist" / zip_name
    zip_path.parent.mkdir(exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    root_in_zip = f"AgelClaw-v{version}"
    file_count = 0

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for entry in ZIP_INCLUDE:
            src = PROACTIVE_DIR / entry
            if not src.exists():
                print(f"  SKIP (not found): {entry}")
                continue
            if src.is_file():
                arcname = f"{root_in_zip}/{entry}"
                if not _should_exclude(src):
                    zf.write(src, arcname)
                    file_count += 1
            elif src.is_dir():
                for root, dirs, files in os.walk(src):
                    root_path = Path(root)
                    dirs[:] = [d for d in dirs if not _should_exclude(root_path / d)]
                    for fname in files:
                        fpath = root_path / fname
                        if _should_exclude(fpath):
                            continue
                        rel = fpath.relative_to(PROACTIVE_DIR)
                        arcname = f"{root_in_zip}/{rel}"
                        zf.write(fpath, arcname)
                        file_count += 1
        zf.writestr(f"{root_in_zip}/data/.gitkeep", "")
        zf.writestr(f"{root_in_zip}/logs/.gitkeep", "")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Created: {zip_path}")
    print(f"  Files: {file_count}, Size: {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description="Build AgelClaw release zip")
    parser.add_argument("--version", default=VERSION, help=f"Version (default: {VERSION})")
    args = parser.parse_args()

    print(f"AgelClaw v{args.version} build")
    print("=" * 40)
    print()

    build_zip(args.version)

    print()
    print("Done!")
    print(f"  Upload dist/AgelClaw-v{args.version}-win64.zip to GitHub Releases")


if __name__ == "__main__":
    main()
