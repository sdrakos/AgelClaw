"""
Version Bump
============
Updates version across all files in the project.

Usage:
    agelclaw bump 3.2.0

Files updated:
  - pyproject.toml           (version = "X.Y.Z")
  - src/agelclaw/__init__.py (__version__ = "X.Y.Z")
  - build_release.py         (VERSION = "X.Y.Z")
  - AgelClaw-v{old}-install.bat -> AgelClaw-v{new}-install.bat (rename)
  - buypage/src/components/DownloadCTA.tsx (URL)
  - buypage/src/components/Hero.tsx        (URL + badge)
  - buypage/src/components/Navbar.tsx      (URLs)
"""

import re
import sys
from pathlib import Path

from agelclaw import __version__ as CURRENT_VERSION
from agelclaw.project import get_project_dir


def _replace_in_file(filepath: Path, old: str, new: str) -> bool:
    """Replace all occurrences of old with new in a file. Returns True if changed."""
    if not filepath.exists():
        return False
    text = filepath.read_text(encoding="utf-8")
    if old not in text:
        return False
    filepath.write_text(text.replace(old, new), encoding="utf-8")
    return True


def bump(new_version: str, old_version: str | None = None):
    """Bump version from old to new across all project files."""
    old = old_version or CURRENT_VERSION
    new = new_version

    if not re.match(r"^\d+\.\d+\.\d+$", new):
        print(f"ERROR: Invalid version format '{new}'. Use X.Y.Z (e.g. 3.2.0)")
        sys.exit(1)

    if old == new:
        print(f"Already at version {old}")
        return

    project = get_project_dir()
    # Major.Minor for badge text (e.g. "v3.1" -> "v3.2")
    old_short = ".".join(old.split(".")[:2])
    new_short = ".".join(new.split(".")[:2])

    print(f"Bumping version: {old} -> {new}")
    print("=" * 40)

    # 1. pyproject.toml
    f = project / "pyproject.toml"
    if _replace_in_file(f, f'version = "{old}"', f'version = "{new}"'):
        print(f"  OK  pyproject.toml")
    else:
        print(f"  SKIP pyproject.toml (not found or no match)")

    # 2. __init__.py
    f = project / "src" / "agelclaw" / "__init__.py"
    if _replace_in_file(f, f'__version__ = "{old}"', f'__version__ = "{new}"'):
        print(f"  OK  src/agelclaw/__init__.py")
    else:
        print(f"  SKIP src/agelclaw/__init__.py")

    # 3. build_release.py
    f = project / "build_release.py"
    if _replace_in_file(f, f'VERSION = "{old}"', f'VERSION = "{new}"'):
        print(f"  OK  build_release.py")
    else:
        print(f"  SKIP build_release.py")

    # 4. Rename installer .bat
    old_bat = project / f"AgelClaw-v{old}-install.bat"
    new_bat = project / f"AgelClaw-v{new}-install.bat"
    if old_bat.exists():
        old_bat.rename(new_bat)
        print(f"  OK  {old_bat.name} -> {new_bat.name}")
    else:
        print(f"  SKIP installer rename ({old_bat.name} not found)")

    # 5. Buypage components — full version in URLs
    buypage = project / "buypage" / "src" / "components"
    for name in ["DownloadCTA.tsx", "Hero.tsx", "Navbar.tsx"]:
        f = buypage / name
        changed = _replace_in_file(f, f"v{old}", f"v{new}")
        # Also update short version badge in Hero.tsx (e.g. "v3.1 —")
        if name == "Hero.tsx" and old_short != new_short:
            _replace_in_file(f, f"v{old_short}", f"v{new_short}")
        if changed:
            print(f"  OK  buypage/src/components/{name}")
        else:
            print(f"  SKIP buypage/src/components/{name}")

    print()
    print(f"Version bumped to {new}")
    print()
    print("Next steps:")
    print(f"  git add -A && git commit -m 'Bump version to {new}'")
    print(f"  git tag v{new} && git push --tags")
    print(f"  agelclaw release")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bump AgelClaw version")
    parser.add_argument("version", help="New version (e.g. 3.2.0)")
    parser.add_argument("--from", dest="old", default=None,
                        help=f"Old version to replace (default: {CURRENT_VERSION})")
    args = parser.parse_args()
    bump(args.version, old_version=args.old)


if __name__ == "__main__":
    main()
