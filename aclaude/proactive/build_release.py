"""
Build Release Script
====================
Creates a pre-built zip for distribution via GitHub Releases.
Packages the agent with the built React UI, ready to extract and run.

Usage:
    python build_release.py
    python build_release.py --version 2.1
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

PROACTIVE_DIR = Path(__file__).parent
VERSION = "2.1"

# Files/dirs to include in the release
INCLUDE = [
    # Core Python
    "agent_config.py",
    "api_server.py",
    "cli.py",
    "daemon_v2.py",
    "embeddings.py",
    "install.py",
    "launcher.py",
    "mem_cli.py",
    "memory.py",
    "memory_tools.py",
    "outlook_digest.py",
    "skill_tools.py",
    "telegram_bot.py",
    "ecosystem.config.js",
    # Config
    "config.yaml.example",
    "requirements.txt",
    # Launchers
    "start.bat",
    "start.sh",
    # Docs
    "README.md",
    "MANUAL.md",
    # Directories (will be copied recursively)
    "core/",
    "agent_wrappers/",
    "skills/",
    "scripts/",
    "subagents/",
    # Pre-built React UI
    "react-claude-chat/dist/",
    "react-claude-chat/package.json",
]

# Patterns to exclude even inside included dirs
EXCLUDE_PATTERNS = [
    "__pycache__",
    "node_modules",
    ".git",
    ".env",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    "nul",
]


def should_exclude(path: Path) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.name.endswith(pattern[1:]):
                return True
        elif pattern in path.parts or path.name == pattern:
            return True
    return False


def build_react():
    """Build the React chat UI if not already built."""
    dist = PROACTIVE_DIR / "react-claude-chat" / "dist"
    if dist.exists() and (dist / "index.html").exists():
        print(f"  React build found at {dist}")
        return True

    print("  Building React UI...")
    react_dir = PROACTIVE_DIR / "react-claude-chat"
    if not (react_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=str(react_dir), check=True)
    subprocess.run(["npm", "run", "build"], cwd=str(react_dir), check=True)
    return True


def create_zip(version: str):
    """Create the release zip."""
    zip_name = f"AgelClaw-v{version}-win64.zip"
    zip_path = PROACTIVE_DIR / "dist" / zip_name
    zip_path.parent.mkdir(exist_ok=True)

    # Remove old zip
    if zip_path.exists():
        zip_path.unlink()

    root_in_zip = f"AgelClaw-v{version}"
    file_count = 0

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for entry in INCLUDE:
            src = PROACTIVE_DIR / entry

            if not src.exists():
                print(f"  SKIP (not found): {entry}")
                continue

            if src.is_file():
                arcname = f"{root_in_zip}/{entry}"
                if not should_exclude(src):
                    zf.write(src, arcname)
                    file_count += 1
            elif src.is_dir():
                for root, dirs, files in os.walk(src):
                    root_path = Path(root)
                    # Filter excluded dirs in-place
                    dirs[:] = [d for d in dirs if not should_exclude(root_path / d)]
                    for fname in files:
                        fpath = root_path / fname
                        if should_exclude(fpath):
                            continue
                        rel = fpath.relative_to(PROACTIVE_DIR)
                        arcname = f"{root_in_zip}/{rel}"
                        zf.write(fpath, arcname)
                        file_count += 1

        # Add empty data/ directory marker
        zf.writestr(f"{root_in_zip}/data/.gitkeep", "")
        zf.writestr(f"{root_in_zip}/logs/.gitkeep", "")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n  Created: {zip_path}")
    print(f"  Files: {file_count}")
    print(f"  Size: {size_mb:.1f} MB")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build AgelClaw release zip")
    parser.add_argument("--version", default=VERSION, help=f"Version string (default: {VERSION})")
    args = parser.parse_args()

    print(f"Building AgelClaw v{args.version} release...")
    print()

    print("[1/2] Checking React build...")
    build_react()
    print()

    print("[2/2] Creating zip...")
    zip_path = create_zip(args.version)
    print()

    print("Done! Upload this file to GitHub Releases:")
    print(f"  {zip_path}")
    print()
    print("GitHub Release URL will be:")
    print(f"  https://github.com/sdrakos/AgelClaw/releases/download/v{args.version}/{zip_path.name}")


if __name__ == "__main__":
    main()
