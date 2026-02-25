---
name: mcp-server-creator
description: Create MCP (Model Context Protocol) servers in Python. Use when building custom tools, API integrations, database connectors, or external service wrappers that Claude can use. Triggers on "create MCP server", "MCP tool", "connect to API", "custom tool".
---

# MCP Server Creator

Create Model Context Protocol servers that extend Claude's capabilities with custom tools.

## What is MCP?

MCP (Model Context Protocol) is an open protocol for connecting LLMs to external tools and data sources. MCP servers expose:
- **Tools**: Functions the LLM can call (with user approval)
- **Resources**: Data the LLM can read
- **Prompts**: Pre-defined templates

## Quick Start

1. Create a new MCP server using the template
2. Add your tools with `@mcp.tool()` decorator
3. Register in `mcp_servers.json`
4. The orchestrator will load it dynamically

## Python MCP Server Template

```python
"""
MCP Server: [NAME]
Description: [WHAT IT DOES]
"""

from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("[server-name]")


@mcp.tool()
async def my_tool(param1: str, param2: int = 10) -> str:
    """Tool description that Claude will see.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)
    """
    # Tool implementation
    result = f"Processed {param1} with {param2}"
    return result


@mcp.tool()
async def another_tool(data: dict[str, Any]) -> dict:
    """Another tool example.

    Args:
        data: Input data dictionary
    """
    return {"status": "success", "processed": data}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

## Tool Decorator Patterns

### Simple Tool
```python
@mcp.tool()
async def get_weather(city: str) -> str:
    """Get weather for a city."""
    # Implementation
    return f"Weather in {city}: Sunny, 25°C"
```

### Tool with Complex Types
```python
from typing import Optional

@mcp.tool()
async def search_database(
    query: str,
    limit: int = 10,
    filters: Optional[dict] = None
) -> list[dict]:
    """Search the database.

    Args:
        query: Search query string
        limit: Max results (default: 10)
        filters: Optional filters dictionary
    """
    # Implementation
    return [{"id": 1, "result": "..."}]
```

### Tool with HTTP Requests
```python
import httpx

@mcp.tool()
async def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from external API.

    Args:
        endpoint: API endpoint path
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/{endpoint}")
        response.raise_for_status()
        return response.json()
```

## Registration in mcp_servers.json

After creating your server, register it:

```json
{
  "servers": {
    "my-server": {
      "name": "My Custom Server",
      "description": "What this server does",
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {},
      "enabled": true
    }
  }
}
```

## Best Practices

### DO:
- Use async functions for I/O operations
- Write clear docstrings (Claude sees them!)
- Handle errors gracefully
- Return structured data when useful
- Use type hints for parameters

### DON'T:
- Use `print()` in STDIO servers (breaks JSON-RPC)
- Block the event loop with sync I/O
- Expose sensitive data in tool responses
- Create tools with ambiguous names

## Common MCP Server Types

| Type | Use Case | Example |
|------|----------|---------|
| API Wrapper | Connect to external APIs | Weather, stocks, news |
| Database | Query databases | PostgreSQL, MongoDB |
| File System | Extended file operations | Search, index, convert |
| Integration | Connect services | Slack, GitHub, Jira |
| Utility | Helper functions | Calculations, formatting |

## Error Handling

```python
@mcp.tool()
async def safe_operation(data: str) -> str:
    """Operation with error handling."""
    try:
        result = process(data)
        return result
    except ValueError as e:
        return f"Invalid input: {e}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
```

## Testing Your Server

```bash
# Test server starts correctly
python my_server.py

# Test with MCP inspector (if installed)
npx @anthropic/mcp-inspector python my_server.py
```

## Resources

- [references/python-template.py](references/python-template.py) - Full Python template
- [references/common-patterns.md](references/common-patterns.md) - Common implementation patterns
- [Official MCP Docs](https://modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
