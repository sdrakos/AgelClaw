"""
AgelClaw Windows Installer Builder
====================================
Orchestrates the full build pipeline:
  1. Compile with Nuitka -> AgelClaw.dist/AgelClaw.exe
  2. Download & extract Node.js portable into dist/node/
  3. Download & extract Python embeddable into dist/python-embed/
  4. Run Inno Setup -> AgelClaw-Setup-{version}.exe

Prerequisites (developer machine):
  pip install nuitka ordered-set zstandard
  Inno Setup 6 installed (https://jrsoftware.org/isdl.php)

Usage:
  cd proactive
  python build_installer.py
  python build_installer.py --skip-nuitka    # Re-run Inno Setup only
  python build_installer.py --skip-inno      # Nuitka only, no installer
"""

import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

# ── Configuration ──────────────────────────────────────────
VERSION = "3.1.1"
NODE_VERSION = "22.12.0"         # Node.js portable for bundled npm
PYTHON_EMBED_VERSION = "3.12.8"  # Python embeddable zip version

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src" / "agelclaw"
BUILD_DIR = ROOT / "build"
DIST_DIR = BUILD_DIR / "AgelClaw.dist"
ASSETS = ROOT / "assets"
ISS_FILE = ROOT / "installer.iss"

# Inno Setup compiler paths (common locations)
ISCC_PATHS = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def find_iscc() -> Path | None:
    """Find Inno Setup compiler."""
    for p in ISCC_PATHS:
        if p.exists():
            return p
    # Try PATH
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    return Path(iscc) if iscc else None


def step_nuitka():
    """Step 1: Compile with Nuitka."""
    print("=" * 60)
    print("STEP 1: Compiling with Nuitka")
    print("=" * 60)

    entry_point = SRC / "cli_entry.py"
    if not entry_point.exists():
        print(f"ERROR: Entry point not found: {entry_point}")
        sys.exit(1)

    # Excluded packages: heavy deps that AgelClaw doesn't need at runtime
    excluded = ",".join([
        "tkinter", "test", "unittest", "pytest", "pip", "setuptools",
        "agelclaw.data",
        # ML/science — pulled transitively, never used
        "torch", "matplotlib", "numpy", "scipy", "pandas", "PIL", "cv2",
        "IPython", "jupyter", "notebook", "sklearn", "tensorflow",
        # LLM routing bloat
        "litellm", "onnxruntime", "sounddevice", "pyaudio",
        # ASN/crypto bloat
        "pyasn1_modules", "pyasn1",
        # Other heavy unused
        "docutils", "pygments", "sphinx", "babel",
    ])

    nproc = os.cpu_count() or 4

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--zig",
        "--assume-yes-for-downloads",
        f"--jobs={nproc}",
        f"--output-dir={BUILD_DIR}",
        "--output-filename=AgelClaw.exe",
        "--include-package=agelclaw",
        "--include-package-data=agelclaw",
        f"--include-data-dir={SRC / 'data'}=agelclaw/data",
        f"--nofollow-import-to={excluded}",
        "--windows-console-mode=attach",
        f"--company-name=AgelClaw",
        f"--product-name=AgelClaw",
        f"--file-version={VERSION}",
        f"--product-version={VERSION}",
        "--file-description=AgelClaw AI Agent",
    ]

    # Add icon if it exists
    icon = ASSETS / "icon.ico"
    if icon.exists():
        cmd.append(f"--windows-icon-from-ico={icon}")

    cmd.append(str(entry_point))

    print(f"Running: {' '.join(str(c) for c in cmd[:5])} ...")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("ERROR: Nuitka compilation failed!")
        sys.exit(1)

    # Verify output
    exe = DIST_DIR / "AgelClaw.exe"
    if not exe.exists():
        # Nuitka may name the dist folder differently
        possible = list(BUILD_DIR.glob("*.dist"))
        if possible:
            actual_dist = possible[0]
            if actual_dist != DIST_DIR:
                print(f"  Renaming {actual_dist.name} -> AgelClaw.dist")
                actual_dist.rename(DIST_DIR)

    exe = DIST_DIR / "AgelClaw.exe"
    if not exe.exists():
        # Check for cli_entry.exe (Nuitka names after the source file)
        alt_exe = DIST_DIR / "cli_entry.exe"
        if alt_exe.exists():
            print(f"  Renaming cli_entry.exe -> AgelClaw.exe")
            alt_exe.rename(exe)

    if not exe.exists():
        print(f"ERROR: Expected output not found at {exe}")
        print(f"  Contents of {BUILD_DIR}:")
        for p in BUILD_DIR.rglob("*.exe"):
            print(f"    {p}")
        sys.exit(1)

    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"  AgelClaw.exe: {size_mb:.1f} MB")


def step_node_embed():
    """Step 2: Download and extract Node.js portable."""
    print()
    print("=" * 60)
    print("STEP 2: Bundling Node.js portable")
    print("=" * 60)

    node_dir = DIST_DIR / "node"

    if node_dir.exists() and (node_dir / "node.exe").exists():
        print(f"  Already exists at {node_dir}")
        return

    url = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip"
    zip_path = BUILD_DIR / f"node-v{NODE_VERSION}-win-x64.zip"

    if not zip_path.exists():
        print(f"  Downloading {url} ...")
        data = urlopen(url).read()
        zip_path.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        print(f"  Downloaded: {size_mb:.1f} MB")
    else:
        print(f"  Using cached {zip_path.name}")

    # Extract to temp dir first (zip has top-level folder node-vX.X.X-win-x64/)
    temp_extract = BUILD_DIR / "node_extract_tmp"
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(temp_extract)

    # Move contents up one level (strip the top-level folder)
    top_folder = temp_extract / f"node-v{NODE_VERSION}-win-x64"
    if not top_folder.exists():
        # Fallback: find whatever top-level dir exists
        subdirs = [d for d in temp_extract.iterdir() if d.is_dir()]
        if subdirs:
            top_folder = subdirs[0]
        else:
            print(f"ERROR: Unexpected zip structure in {zip_path}")
            sys.exit(1)

    node_dir.mkdir(parents=True, exist_ok=True)
    for item in top_folder.iterdir():
        dest = node_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Cleanup temp
    shutil.rmtree(temp_extract)

    # Verify
    if not (node_dir / "node.exe").exists():
        print(f"ERROR: node.exe not found in {node_dir}")
        sys.exit(1)
    if not (node_dir / "npm.cmd").exists():
        print(f"ERROR: npm.cmd not found in {node_dir}")
        sys.exit(1)

    print(f"  Extracted to {node_dir}")
    node_size = sum(f.stat().st_size for f in node_dir.rglob("*") if f.is_file())
    print(f"  Node.js size: {node_size / (1024 * 1024):.0f} MB")


def step_python_embed():
    """Step 3: Download and extract Python embeddable."""
    print()
    print("=" * 60)
    print("STEP 3: Bundling Python embeddable")
    print("=" * 60)

    embed_dir = DIST_DIR / "python-embed"

    if embed_dir.exists() and (embed_dir / "python.exe").exists():
        print(f"  Already exists at {embed_dir}")
        return

    # Determine architecture
    arch = "amd64" if platform.machine().endswith("64") else "win32"
    url = f"https://www.python.org/ftp/python/{PYTHON_EMBED_VERSION}/python-{PYTHON_EMBED_VERSION}-embed-{arch}.zip"
    zip_path = BUILD_DIR / f"python-embed-{PYTHON_EMBED_VERSION}.zip"

    if not zip_path.exists():
        print(f"  Downloading {url} ...")
        data = urlopen(url).read()
        zip_path.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        print(f"  Downloaded: {size_mb:.1f} MB")
    else:
        print(f"  Using cached {zip_path.name}")

    # Extract
    embed_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(embed_dir)

    # Enable pip/site-packages by uncommenting import site in python3XX._pth
    pth_files = list(embed_dir.glob("python*._pth"))
    for pth in pth_files:
        content = pth.read_text(encoding="utf-8")
        content = content.replace("#import site", "import site")
        pth.write_text(content, encoding="utf-8")
        print(f"  Enabled site-packages in {pth.name}")

    print(f"  Extracted to {embed_dir}")


def step_inno_setup():
    """Step 4: Build installer with Inno Setup."""
    print()
    print("=" * 60)
    print("STEP 4: Building installer with Inno Setup")
    print("=" * 60)

    iscc = find_iscc()
    if not iscc:
        print("WARNING: Inno Setup not found! Skipping installer build.")
        print("  Install from: https://jrsoftware.org/isdl.php")
        print(f"  Then run: ISCC.exe {ISS_FILE}")
        return

    if not ISS_FILE.exists():
        print(f"ERROR: {ISS_FILE} not found")
        sys.exit(1)

    cmd = [str(iscc), str(ISS_FILE)]
    print(f"  Running: {cmd[0]}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("ERROR: Inno Setup compilation failed!")
        sys.exit(1)

    # Find output
    output_dir = BUILD_DIR / "installer"
    installers = list(output_dir.glob("*.exe")) if output_dir.exists() else []
    if installers:
        for inst in installers:
            size_mb = inst.stat().st_size / (1024 * 1024)
            print(f"  Installer: {inst.name} ({size_mb:.1f} MB)")
    else:
        print("  Installer output not found in expected location")


def main():
    parser = argparse.ArgumentParser(description="Build AgelClaw Windows installer")
    parser.add_argument("--skip-nuitka", action="store_true",
                        help="Skip Nuitka compilation (reuse existing dist)")
    parser.add_argument("--skip-inno", action="store_true",
                        help="Skip Inno Setup (compile only)")
    parser.add_argument("--skip-node", action="store_true",
                        help="Skip Node.js portable download")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Skip Python embeddable download")
    args = parser.parse_args()

    print(f"AgelClaw Installer Builder v{VERSION}")
    print(f"Root: {ROOT}")
    print()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_nuitka:
        step_nuitka()
    else:
        print("Skipping Nuitka (--skip-nuitka)")

    if not args.skip_node:
        step_node_embed()
    else:
        print("Skipping Node.js (--skip-node)")

    if not args.skip_embed:
        step_python_embed()
    else:
        print("Skipping Python embeddable (--skip-embed)")

    if not args.skip_inno:
        step_inno_setup()
    else:
        print("Skipping Inno Setup (--skip-inno)")

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    if DIST_DIR.exists():
        exe_count = len(list(DIST_DIR.glob("*.exe")))
        print(f"  Dist folder: {DIST_DIR}")
        print(f"  Executables: {exe_count}")
        total = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file())
        print(f"  Total size: {total / (1024 * 1024):.0f} MB")


if __name__ == "__main__":
    main()
