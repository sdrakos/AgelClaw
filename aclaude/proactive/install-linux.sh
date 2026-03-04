#!/bin/bash
# AgelClaw Linux Installer
# Usage: curl -sL https://github.com/sdrakos/AgelClaw/releases/download/v3.1.0/install-linux.sh | sudo bash
set -e

VERSION="3.1.1"
INSTALL_DIR="/usr/local/lib/agelclaw"
BIN_DIR="/usr/local/bin"
REPO="sdrakos/AgelClaw"

echo "============================================"
echo "  AgelClaw v${VERSION} — Linux Installer"
echo "============================================"
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

# Download tarball
TARBALL_URL="https://github.com/${REPO}/releases/download/v${VERSION}/agelclaw-${VERSION}-linux-x86_64.tar.gz"
echo "Downloading ${TARBALL_URL} ..."
curl -fSL -o /tmp/agelclaw.tar.gz "$TARBALL_URL"
echo "  Downloaded."

# Clean previous install
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing previous installation at ${INSTALL_DIR} ..."
    rm -rf "$INSTALL_DIR"
fi

# Extract
echo "Extracting to ${INSTALL_DIR} ..."
mkdir -p "$INSTALL_DIR"
tar xzf /tmp/agelclaw.tar.gz -C "$INSTALL_DIR" --strip-components=1
rm -f /tmp/agelclaw.tar.gz

# Ensure binaries are executable
chmod +x "$INSTALL_DIR/agelclaw"
if [ -L "$INSTALL_DIR/agelclaw-mem" ]; then
    : # symlink, ok
elif [ -f "$INSTALL_DIR/agelclaw-mem" ]; then
    chmod +x "$INSTALL_DIR/agelclaw-mem"
fi

# Create symlinks in PATH
echo "Creating symlinks in ${BIN_DIR} ..."
ln -sf "$INSTALL_DIR/agelclaw" "$BIN_DIR/agelclaw"
ln -sf "$INSTALL_DIR/agelclaw-mem" "$BIN_DIR/agelclaw-mem"

# Add bundled node to PATH hint
NODE_BIN="$INSTALL_DIR/node/bin"
if [ -d "$NODE_BIN" ]; then
    echo "Bundled Node.js at ${NODE_BIN}"
    echo "  Add to PATH if needed: export PATH=\"${NODE_BIN}:\$PATH\""
fi

# Install Claude Code CLI via bundled npm (if node exists)
if [ -x "$NODE_BIN/node" ] && [ -x "$NODE_BIN/npm" ]; then
    echo "Installing Claude Code CLI ..."
    export PATH="$NODE_BIN:$PATH"
    npm install -g @anthropic-ai/claude-code 2>/dev/null || echo "  (Claude CLI install skipped — run manually if needed)"
fi

# Copy systemd user service template
SYSTEMD_SRC="$INSTALL_DIR/agelclaw.service"
if [ -f "$SYSTEMD_SRC" ]; then
    # Install for the invoking user (SUDO_USER)
    REAL_USER="${SUDO_USER:-$USER}"
    REAL_HOME=$(eval echo "~$REAL_USER")
    SYSTEMD_DIR="$REAL_HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_DIR"
    cp "$SYSTEMD_SRC" "$SYSTEMD_DIR/agelclaw.service"
    chown -R "$REAL_USER":"$REAL_USER" "$REAL_HOME/.config/systemd" 2>/dev/null || true
    echo "Systemd user service installed at ${SYSTEMD_DIR}/agelclaw.service"
fi

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. agelclaw init       # Initialize project directory"
echo "  2. agelclaw setup      # Configure API keys"
echo "  3. agelclaw            # Start interactive chat"
echo ""
echo "To auto-start the daemon:"
echo "  systemctl --user enable --now agelclaw"
echo ""
