# MCP (Model Context Protocol)

## Five Transport Types

### 1. Hosted MCP (HostedMCPTool)
OpenAI manages the server. No local process needed.
```python
from agents import Agent, HostedMCPTool

agent = Agent(
    name="Assistant",
    tools=[HostedMCPTool(server_label="deepwiki", server_url="https://mcp.deepwiki.com/mcp")],
)
```

### 2. Streamable HTTP (MCPServerStreamableHttp)
```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="My Server",
    params={"url": "http://localhost:8000/mcp"},
    cache_tools_list=True,
) as server:
    agent = Agent(name="Assistant", mcp_servers=[server])
    result = await Runner.run(agent, "Query")
```

### 3. SSE (MCPServerSse) — deprecated by MCP project
```python
from agents.mcp import MCPServerSse

server = MCPServerSse(name="SSE Server", params={"url": "http://localhost:8000/sse"})
```

### 4. Stdio (MCPServerStdio)
```python
from agents.mcp import MCPServerStdio

server = MCPServerStdio(
    name="Local Server",
    params={"command": "python", "args": ["my_mcp_server.py"]},
)
```

### 5. MCPServerManager
Coordinate multiple servers.

## Agent-Level MCP Config

```python
agent = Agent(
    name="Assistant",
    mcp_servers=[server1, server2],
    mcp_config={
        "convert_schemas_to_strict": True,
        "failure_error_function": my_error_handler,
    },
)
```

## Tool Filtering

```python
# Static: allow/block lists
server = MCPServerStreamableHttp(
    name="Server",
    params={"url": "..."},
    tool_filter={"allow": ["read_file", "list_dir"]},  # or {"block": [...]}
)

# Dynamic: callable
def my_filter(ctx, tools):
    return [t for t in tools if not t.name.startswith("dangerous_")]

server = MCPServerStreamableHttp(..., tool_filter=my_filter)
```

## Human-in-the-Loop Approval

```python
server = MCPServerStreamableHttp(
    name="Server",
    params={"url": "..."},
    require_approval="always",  # or "never"
    # Or per-tool: {"delete_file": "always", "read_file": "never"}
)
```

## MCP Prompts

```python
prompts = await server.list_prompts()
prompt = await server.get_prompt("my_prompt", arguments={...})
```

## Caching
```python
server = MCPServerStreamableHttp(..., cache_tools_list=True)
```
