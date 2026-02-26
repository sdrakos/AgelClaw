---
name: mcp-installer
description: Install and configure MCP servers. Use when user asks to "install MCP", "add Playwright", "setup browser automation", "add MCP server", or wants to extend agent capabilities with external tools.
---

# MCP Server Installer

Εγκατάσταση και ρύθμιση MCP (Model Context Protocol) servers για επέκταση των δυνατοτήτων του agent.

## Πώς να εγκαταστήσεις MCP Server

### Βήμα 0: Βρες το σωστό package name

Αν δεν ξέρεις το ακριβές package name, **ψάξε πρώτα στο npm**:

```bash
# Ψάξε για MCP packages
npm search mcp <keyword> --long

# Παραδείγματα:
npm search mcp playwright --long
npm search mcp postgres --long
npm search mcp github --long
```

Διάλεξε το package με τα περισσότερα downloads και πρόσφατο update.

### Βήμα 1: Εγκατάσταση με npm/npx

Τρέξε την κατάλληλη εντολή με το **Bash tool**:

```bash
# Για Playwright (browser automation)
npm install -g @playwright/mcp

# Ή με npx (χωρίς global install)
npx -y @playwright/mcp
```

### Βήμα 2: Πρόσθεσε στο .mcp.json

Χρησιμοποίησε το **Edit tool** για να προσθέσεις τον server στο `.mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"],
      "env": {}
    }
  }
}
```

### Βήμα 3: Ενημέρωσε τον χρήστη

Πες στον χρήστη να κάνει `/refresh` ή restart για να φορτωθεί ο νέος server.

---

## Διαθέσιμοι MCP Servers

### 🎭 Playwright (Browser Automation)
```json
{
  "playwright": {
    "command": "npx",
    "args": ["-y", "@playwright/mcp"],
    "env": {}
  }
}
```
**Χρήση**: Web scraping, browser testing, screenshots, PDF generation
**Tools**: `browser_navigate`, `browser_click`, `browser_screenshot`, `browser_pdf`, etc.

### 🗄️ PostgreSQL Database
```json
{
  "postgres": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-postgres"],
    "env": {
      "DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"
    }
  }
}
```
**Χρήση**: Database queries, schema exploration
**Tools**: `query`, `list_tables`, `describe_table`

### 📁 Filesystem Extended
```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/path/to/allowed/dir"],
    "env": {}
  }
}
```
**Χρήση**: Extended file operations με sandboxing
**Tools**: `read_file`, `write_file`, `list_directory`, `search_files`

### 🔍 Brave Search
```json
{
  "brave-search": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
    "env": {
      "BRAVE_API_KEY": "your-api-key"
    }
  }
}
```
**Χρήση**: Web search
**Tools**: `brave_web_search`, `brave_local_search`

### 📊 Google Sheets
```json
{
  "google-sheets": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-google-sheets"],
    "env": {
      "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
    }
  }
}
```
**Χρήση**: Read/write Google Sheets
**Tools**: `read_sheet`, `write_sheet`, `create_sheet`

### 🐙 GitHub
```json
{
  "github": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-github"],
    "env": {
      "GITHUB_TOKEN": "ghp_xxxx"
    }
  }
}
```
**Χρήση**: GitHub operations
**Tools**: `create_issue`, `list_repos`, `create_pr`, `search_code`

### 💬 Slack
```json
{
  "slack": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-slack"],
    "env": {
      "SLACK_BOT_TOKEN": "xoxb-xxxx"
    }
  }
}
```
**Χρήση**: Slack messaging
**Tools**: `send_message`, `list_channels`, `read_messages`

### 🧠 Memory (Persistent Storage)
```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@anthropic-ai/mcp-server-memory"],
    "env": {}
  }
}
```
**Χρήση**: Persistent key-value storage
**Tools**: `store`, `retrieve`, `list_keys`, `delete`

---

## Οδηγίες Εγκατάστασης

### Prerequisites
```bash
# Βεβαιώσου ότι υπάρχει Node.js
node --version
npm --version

# Αν δεν υπάρχει, εγκατάστησε:
# Ubuntu/Debian
sudo apt update && sudo apt install -y nodejs npm

# CentOS/RHEL
sudo yum install -y nodejs npm

# Windows (με chocolatey)
choco install nodejs
```

### Εγκατάσταση Server
```bash
# Global installation (recommended για VPS)
npm install -g @playwright/mcp

# Ή project-local
npm install @playwright/mcp
```

### Ρύθμιση .mcp.json

Το αρχείο `.mcp.json` πρέπει να είναι στο working directory του agent:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@package/name"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

---

## Παράδειγμα: Εγκατάσταση Playwright

Όταν ο χρήστης ζητήσει "εγκατάστησε Playwright MCP":

1. **Έλεγξε Node.js**:
```bash
node --version
```

2. **Εγκατάστησε το package**:
```bash
npm install -g @playwright/mcp
```

3. **Διάβασε το τρέχον .mcp.json**:
```
Read .mcp.json
```

4. **Πρόσθεσε τον Playwright server**:
```
Edit .mcp.json - προσθήκη "playwright" entry
```

5. **Ενημέρωσε τον χρήστη**:
```
"Ο Playwright MCP server εγκαταστάθηκε! Κάνε /refresh για να φορτωθεί."
```

---

## Troubleshooting

### Error: npm not found
```bash
# Install Node.js first
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Error: Permission denied
```bash
# Use sudo for global install
sudo npm install -g @playwright/mcp

# Or fix npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Server not loading
- Βεβαιώσου ότι το `.mcp.json` είναι valid JSON
- Έλεγξε τα paths και environment variables
- Κάνε restart τον agent

---

## Custom MCP Server (Python)

Αν θέλεις custom server σε Python:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description."""
    return f"Result: {param}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Και στο `.mcp.json`:
```json
{
  "my-server": {
    "command": "python",
    "args": ["path/to/server.py"],
    "env": {}
  }
}
```
