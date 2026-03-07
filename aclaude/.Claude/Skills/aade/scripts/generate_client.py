#!/usr/bin/env python3
"""
Generate the mydata_client.py module from the skill reference.

Usage:
    python scripts/generate_client.py [output_dir]

This reads the client implementation from references/client_module.md
and extracts the Python code into a standalone module.

If no output_dir is specified, outputs to current directory.
"""

import sys
import re
from pathlib import Path


def extract_python_from_md(md_path: Path) -> str:
    """Extract the main Python code block from the reference markdown."""
    content = md_path.read_text(encoding="utf-8")
    
    # Find the main module code block (the one after "## mydata_client.py")
    pattern = r'## mydata_client\.py\s*\n\s*```python\n(.*?)```'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("ERROR: Could not find mydata_client.py code block in reference")
        sys.exit(1)
    
    return match.group(1)


def main():
    script_dir = Path(__file__).parent
    skill_dir = script_dir.parent
    ref_path = skill_dir / "references" / "client_module.md"
    
    if not ref_path.exists():
        print(f"ERROR: Reference file not found: {ref_path}")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    code = extract_python_from_md(ref_path)
    
    output_path = output_dir / "mydata_client.py"
    output_path.write_text(code, encoding="utf-8")
    
    print(f"✅ Generated: {output_path}")
    print(f"   Install deps: pip install httpx lxml python-dotenv")
    print(f"   Configure:    Create .env with MYDATA_USER_ID, MYDATA_SUBSCRIPTION_KEY")
    print(f"   Test:         MYDATA_ENV=dev python -c 'from mydata_client import MyDataClient; print(\"OK\")'")


if __name__ == "__main__":
    main()
