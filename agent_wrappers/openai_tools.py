"""
OpenAI Agent Tools
==================
Function tool implementations for the OpenAI Agents SDK.
Claude SDK has built-in tools (Bash, Read, Write, etc.) but OpenAI agents
need actual Python implementations.
"""

import os
import subprocess
import glob as glob_module
import re
from pathlib import Path

from agents import function_tool

# Default working directory — set by OpenAIAgent before running
_CWD: str = "."


def set_cwd(cwd: str) -> None:
    """Set the working directory for tool execution."""
    global _CWD
    _CWD = cwd


@function_tool
def bash(command: str) -> str:
    """Execute a shell command and return stdout + stderr.

    Args:
        command: The shell command to execute.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=_CWD,
            env={**os.environ},
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output[:30000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 120 seconds"
    except Exception as e:
        return f"ERROR: {e}"


@function_tool
def read_file(file_path: str) -> str:
    """Read a file and return its contents.

    Args:
        file_path: Absolute or relative path to the file.
    """
    try:
        p = Path(file_path)
        if not p.is_absolute():
            p = Path(_CWD) / p
        if not p.exists():
            return f"ERROR: File not found: {file_path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50000:
            content = content[:50000] + f"\n... [truncated, {len(content)} total chars]"
        return content
    except Exception as e:
        return f"ERROR: {e}"


@function_tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed.

    Args:
        file_path: Path to write to.
        content: File content.
    """
    try:
        p = Path(file_path)
        if not p.is_absolute():
            p = Path(_CWD) / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {file_path}"
    except Exception as e:
        return f"ERROR: {e}"


@function_tool
def grep_search(pattern: str, path: str = ".", file_glob: str = "") -> str:
    """Search file contents using regex pattern.

    Args:
        pattern: Regex pattern to search for.
        path: Directory or file to search in.
        file_glob: Optional glob to filter files (e.g., '*.py').
    """
    try:
        search_path = Path(path)
        if not search_path.is_absolute():
            search_path = Path(_CWD) / search_path

        results = []
        regex = re.compile(pattern, re.IGNORECASE)

        if search_path.is_file():
            files = [search_path]
        else:
            glob_pattern = file_glob or "**/*"
            files = [f for f in search_path.glob(glob_pattern) if f.is_file()]

        for fp in files[:100]:  # Limit files scanned
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{fp}:{i}: {line.strip()}")
                        if len(results) >= 50:
                            break
            except Exception:
                continue
            if len(results) >= 50:
                break

        return "\n".join(results) if results else "No matches found."
    except Exception as e:
        return f"ERROR: {e}"


@function_tool
def glob_search(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., '**/*.py', 'src/**/*.ts').
        path: Base directory to search from.
    """
    try:
        search_path = Path(path)
        if not search_path.is_absolute():
            search_path = Path(_CWD) / search_path

        matches = sorted(search_path.glob(pattern))
        results = [str(m) for m in matches[:100]]
        return "\n".join(results) if results else "No files matched."
    except Exception as e:
        return f"ERROR: {e}"


# All tools for easy import
ALL_OPENAI_TOOLS = [bash, read_file, write_file, grep_search, glob_search]
