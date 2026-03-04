"""
AgelClaw Linux Installer Builder
====================================
Orchestrates the Linux build pipeline:
  1. Compile with Nuitka -> AgelClaw.dist/agelclaw (ELF binary)
  2. Download & extract Node.js portable into dist/node/
  3. Create tarball: agelclaw-{version}-linux-x86_64.tar.gz

Prerequisites:
  pip install nuitka ordered-set zstandard
  # On Ubuntu: sudo apt install patchelf ccache

Usage:
  cd proactive
  python build_installer_linux.py
  python build_installer_linux.py --skip-nuitka    # Reuse existing dist
  python build_installer_linux.py --skip-node       # Skip Node.js download
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.request import urlopen

# ── Configuration ──────────────────────────────────────────
VERSION = "3.1.1"
NODE_VERSION = "22.12.0"

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src" / "agelclaw"
BUILD_DIR = ROOT / "build"
DIST_DIR = BUILD_DIR / "AgelClaw.dist"
TARBALL_NAME = f"agelclaw-{VERSION}-linux-x86_64.tar.gz"


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
        "--assume-yes-for-downloads",
        f"--jobs={nproc}",
        f"--output-dir={BUILD_DIR}",
        "--output-filename=agelclaw",
        "--include-package=agelclaw",
        "--include-package-data=agelclaw",
        f"--include-data-dir={SRC / 'data'}=agelclaw/data",
        f"--nofollow-import-to={excluded}",
        f"--company-name=AgelClaw",
        f"--product-name=AgelClaw",
        f"--file-version={VERSION}",
        f"--product-version={VERSION}",
        "--file-description=AgelClaw AI Agent",
        str(entry_point),
    ]

    print(f"Running: {' '.join(str(c) for c in cmd[:5])} ...")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("ERROR: Nuitka compilation failed!")
        sys.exit(1)

    # Verify output — Nuitka may name the dist folder after the source file
    if not DIST_DIR.exists():
        possible = list(BUILD_DIR.glob("*.dist"))
        if possible:
            actual_dist = possible[0]
            if actual_dist != DIST_DIR:
                print(f"  Renaming {actual_dist.name} -> AgelClaw.dist")
                actual_dist.rename(DIST_DIR)

    # Find the binary (may be named cli_entry or agelclaw)
    binary = DIST_DIR / "agelclaw"
    if not binary.exists():
        alt_binary = DIST_DIR / "cli_entry.bin"
        if alt_binary.exists():
            print("  Renaming cli_entry.bin -> agelclaw")
            alt_binary.rename(binary)

    if not binary.exists():
        # Try without extension
        alt_binary = DIST_DIR / "cli_entry"
        if alt_binary.exists():
            print("  Renaming cli_entry -> agelclaw")
            alt_binary.rename(binary)

    if not binary.exists():
        print(f"ERROR: Expected output not found at {binary}")
        print(f"  Contents of {DIST_DIR}:")
        for p in DIST_DIR.iterdir():
            print(f"    {p.name}")
        sys.exit(1)

    # Make executable
    binary.chmod(0o755)

    size_mb = binary.stat().st_size / (1024 * 1024)
    print(f"  agelclaw binary: {size_mb:.1f} MB")


def step_node_embed():
    """Step 2: Download and extract Node.js for Linux."""
    print()
    print("=" * 60)
    print("STEP 2: Bundling Node.js")
    print("=" * 60)

    node_dir = DIST_DIR / "node"

    if node_dir.exists() and (node_dir / "bin" / "node").exists():
        print(f"  Already exists at {node_dir}")
        return

    url = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-x64.tar.xz"
    archive_path = BUILD_DIR / f"node-v{NODE_VERSION}-linux-x64.tar.xz"

    if not archive_path.exists():
        print(f"  Downloading {url} ...")
        data = urlopen(url).read()
        archive_path.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        print(f"  Downloaded: {size_mb:.1f} MB")
    else:
        print(f"  Using cached {archive_path.name}")

    # Extract to temp dir first (tar has top-level folder node-vX.X.X-linux-x64/)
    temp_extract = BUILD_DIR / "node_extract_tmp"
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True)

    import lzma
    with lzma.open(archive_path) as xz:
        with tarfile.open(fileobj=xz) as tf:
            tf.extractall(temp_extract)

    # Move contents up one level (strip the top-level folder)
    top_folder = temp_extract / f"node-v{NODE_VERSION}-linux-x64"
    if not top_folder.exists():
        subdirs = [d for d in temp_extract.iterdir() if d.is_dir()]
        if subdirs:
            top_folder = subdirs[0]
        else:
            print(f"ERROR: Unexpected archive structure in {archive_path}")
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
    node_bin = node_dir / "bin" / "node"
    if not node_bin.exists():
        print(f"ERROR: node binary not found in {node_dir}")
        sys.exit(1)

    print(f"  Extracted to {node_dir}")
    node_size = sum(f.stat().st_size for f in node_dir.rglob("*") if f.is_file())
    print(f"  Node.js size: {node_size / (1024 * 1024):.0f} MB")


def step_create_symlinks():
    """Step 3: Create agelclaw-mem symlink for filename-based dispatch."""
    print()
    print("=" * 60)
    print("STEP 3: Creating symlinks")
    print("=" * 60)

    binary = DIST_DIR / "agelclaw"
    mem_link = DIST_DIR / "agelclaw-mem"

    if mem_link.exists() or mem_link.is_symlink():
        mem_link.unlink()

    mem_link.symlink_to("agelclaw")
    print(f"  Created: agelclaw-mem -> agelclaw")


def step_create_tarball():
    """Step 4: Package everything into a tarball."""
    print()
    print("=" * 60)
    print("STEP 4: Creating tarball")
    print("=" * 60)

    tarball_path = BUILD_DIR / TARBALL_NAME

    if tarball_path.exists():
        tarball_path.unlink()

    # Copy install script into the dist dir
    install_src = ROOT / "install-linux.sh"
    if install_src.exists():
        install_dst = DIST_DIR / "install.sh"
        shutil.copy2(install_src, install_dst)
        install_dst.chmod(0o755)
        print("  Included install.sh")

    with tarfile.open(tarball_path, "w:gz") as tar:
        # Add everything in DIST_DIR under the "agelclaw/" prefix
        for item in sorted(DIST_DIR.rglob("*")):
            arcname = "agelclaw" / item.relative_to(DIST_DIR)
            tar.add(item, arcname=str(arcname))

    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    print(f"  Tarball: {tarball_path.name} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Build AgelClaw Linux release")
    parser.add_argument("--skip-nuitka", action="store_true",
                        help="Skip Nuitka compilation (reuse existing dist)")
    parser.add_argument("--skip-node", action="store_true",
                        help="Skip Node.js download")
    args = parser.parse_args()

    print(f"AgelClaw Linux Builder v{VERSION}")
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

    step_create_symlinks()
    step_create_tarball()

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    if DIST_DIR.exists():
        total = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file())
        print(f"  Dist folder: {DIST_DIR}")
        print(f"  Total size: {total / (1024 * 1024):.0f} MB")
        print(f"  Tarball: {BUILD_DIR / TARBALL_NAME}")


if __name__ == "__main__":
    main()
