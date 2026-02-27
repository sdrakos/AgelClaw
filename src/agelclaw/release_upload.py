"""
Release Upload
==============
Upload installer and assets to a GitHub Release.

Usage:
    agelclaw release                          # Upload installer for current version
    agelclaw release --version 3.2.0          # Override version
    agelclaw release --file dist/extra.zip    # Upload additional file

Reads GitHub token from (in order):
  1. GITHUB_TOKEN env var
  2. config.yaml → github_token
  3. <repo_root>/../token_github.md (legacy)
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from agelclaw import __version__
from agelclaw.project import get_project_dir

REPO = "sdrakos/AgelClaw"
API = "https://api.github.com"
UPLOAD_API = "https://uploads.github.com"


def _find_token() -> str | None:
    """Find GitHub token from env, config, or legacy file."""
    # 1. Environment variable
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token.strip()

    # 2. config.yaml
    try:
        from agelclaw.core.config import load_config
        cfg = load_config()
        token = cfg.get("github_token")
        if token:
            return token.strip()
    except Exception:
        pass

    # 3. Legacy token_github.md (sibling of proactive dir)
    for search_dir in [get_project_dir().parent, get_project_dir()]:
        md_path = search_dir / "token_github.md"
        if md_path.exists():
            for line in md_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("github_pat_") or line.startswith("ghp_"):
                    return line
    return None


def _api(method: str, url: str, token: str, data: bytes | None = None,
         content_type: str = "application/json") -> dict:
    """Make a GitHub API request."""
    req = Request(url, data=data, method=method, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": content_type,
    })
    try:
        resp = urlopen(req, timeout=60)
        body = resp.read()
        return json.loads(body) if body else {}
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  API error {e.code}: {body[:300]}")
        sys.exit(1)


def _get_or_create_release(token: str, version: str) -> int:
    """Get existing release by tag, or create one."""
    tag = f"v{version}"

    # Try to find existing release
    try:
        data = json.loads(urlopen(
            Request(f"{API}/repos/{REPO}/releases/tags/{tag}", headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            }),
            timeout=30,
        ).read())
        print(f"  Found release: {data['name']} (id={data['id']})")
        return data["id"]
    except HTTPError as e:
        if e.code != 404:
            raise

    # Create new release
    print(f"  Creating release {tag}...")
    payload = json.dumps({
        "tag_name": tag,
        "name": f"AgelClaw v{version}",
        "body": f"AgelClaw v{version} release.",
        "draft": False,
        "prerelease": False,
    }).encode()
    data = _api("POST", f"{API}/repos/{REPO}/releases", token, payload)
    print(f"  Created release: {data['name']} (id={data['id']})")
    return data["id"]


def _delete_asset_if_exists(token: str, release_id: int, filename: str):
    """Delete an existing release asset by name."""
    data = _api("GET", f"{API}/repos/{REPO}/releases/{release_id}/assets", token)
    for asset in data if isinstance(data, list) else []:
        if asset["name"] == filename:
            print(f"  Deleting old asset: {filename} (id={asset['id']})")
            req = Request(
                f"{API}/repos/{REPO}/releases/assets/{asset['id']}",
                method="DELETE",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            urlopen(req, timeout=30)
            return


def _upload_asset(token: str, release_id: int, filepath: Path):
    """Upload a file as release asset."""
    filename = filepath.name
    size = filepath.stat().st_size
    print(f"  Uploading: {filename} ({size:,} bytes)...")

    _delete_asset_if_exists(token, release_id, filename)

    with open(filepath, "rb") as f:
        file_data = f.read()

    url = f"{UPLOAD_API}/repos/{REPO}/releases/{release_id}/assets?name={filename}"
    data = _api("POST", url, token, file_data, content_type="application/octet-stream")
    print(f"  OK: {data['browser_download_url']}")
    return data["browser_download_url"]


def upload_release(version: str | None = None, extra_files: list[str] | None = None):
    """Main upload logic."""
    version = version or __version__
    print(f"AgelClaw v{version} — Release Upload")
    print("=" * 40)

    # Find token
    token = _find_token()
    if not token:
        print("ERROR: GitHub token not found.")
        print("  Set GITHUB_TOKEN env var, or add github_token to config.yaml")
        sys.exit(1)
    print(f"  Token: ...{token[-8:]}")

    # Find or create release
    release_id = _get_or_create_release(token, version)

    # Upload installer
    project_dir = get_project_dir()
    installer = project_dir / f"AgelClaw-v{version}-install.bat"
    if installer.exists():
        _upload_asset(token, release_id, installer)
    else:
        print(f"  SKIP: {installer.name} not found")

    # Upload extra files
    for fpath in (extra_files or []):
        p = Path(fpath)
        if p.exists():
            _upload_asset(token, release_id, p)
        else:
            print(f"  SKIP: {fpath} not found")

    print()
    print("Done!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload AgelClaw release assets to GitHub")
    parser.add_argument("--version", default=None, help=f"Version (default: {__version__})")
    parser.add_argument("--file", action="append", dest="files", help="Extra file to upload")
    args = parser.parse_args()
    upload_release(version=args.version, extra_files=args.files)


if __name__ == "__main__":
    main()
