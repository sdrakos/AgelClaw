#!/usr/bin/env python3
"""
Dynamically list all available Claude skills by scanning the .claude/skills/ directory.
"""

import os
import sys
from pathlib import Path
import re


def parse_yaml_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    # Match content between --- markers
    pattern = r'^---\s*\n(.*?)\n---'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        return {}

    frontmatter = match.group(1)
    result = {}

    # Simple YAML parsing for name and description
    for line in frontmatter.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in ('name', 'description'):
                result[key] = value

    return result


def find_skills_directory() -> Path:
    """Find the .claude/skills directory."""
    # Try current directory first
    cwd = Path.cwd()

    # Check common locations
    possible_paths = [
        cwd / '.claude' / 'skills',
        cwd / '.Claude' / 'skills',
        Path(__file__).parent.parent.parent,  # Relative to this script
    ]

    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path

    return None


def list_skills(skills_dir: Path) -> list:
    """Scan skills directory and return list of skill info."""
    skills = []

    for item in skills_dir.iterdir():
        if not item.is_dir():
            continue

        skill_md = item / 'SKILL.md'
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding='utf-8')
            metadata = parse_yaml_frontmatter(content)

            if metadata.get('name'):
                skills.append({
                    'name': metadata['name'],
                    'description': metadata.get('description', 'No description'),
                    'path': str(item)
                })
        except Exception as e:
            # Skip skills that can't be parsed
            continue

    # Sort by name
    skills.sort(key=lambda x: x['name'])
    return skills


def format_output(skills: list) -> str:
    """Format skills list for display."""
    if not skills:
        return "No skills found in .claude/skills/ directory."

    lines = []
    lines.append(f"\nAvailable Skills ({len(skills)} total)")
    lines.append("=" * 80)
    lines.append(f"{'Name':<25} | Description")
    lines.append("-" * 80)

    for skill in skills:
        name = skill['name']
        desc = skill['description']
        # Truncate description if too long
        if len(desc) > 50:
            desc = desc[:47] + "..."
        lines.append(f"{name:<25} | {desc}")

    lines.append("=" * 80)
    lines.append("\nTo use a skill, invoke it with: /skill-name")
    lines.append("Example: /translation, /pdf, /docx")

    return '\n'.join(lines)


def main():
    skills_dir = find_skills_directory()

    if not skills_dir:
        print("Error: Could not find .claude/skills/ directory.")
        print("Make sure you're running from the project root.")
        sys.exit(1)

    skills = list_skills(skills_dir)
    print(format_output(skills))

    # Return JSON for programmatic use if --json flag
    if '--json' in sys.argv:
        import json
        print("\n--- JSON Output ---")
        print(json.dumps(skills, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
