"""
MCP Server Template
===================

A complete template for creating MCP servers in Python.

Usage:
1. Copy this template
2. Rename and customize
3. Add your tools
4. Register in mcp_servers.json

Requirements:
    pip install mcp httpx
"""

from typing import Any, Optional
import logging

# Use stderr for logging (NEVER use print() in STDIO servers!)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Goes to stderr by default
)
logger = logging.getLogger(__name__)

# Import MCP SDK
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with a unique name
mcp = FastMCP("my-server-name")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Add any configuration constants here
API_BASE_URL = "https://api.example.com"
DEFAULT_TIMEOUT = 30.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def make_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None
) -> dict[str, Any]:
    """Helper function to make API requests."""
    import httpx

    url = f"{API_BASE_URL}/{endpoint}"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()


# =============================================================================
# TOOLS
# =============================================================================

@mcp.tool()
async def example_simple_tool(message: str) -> str:
    """A simple example tool that echoes a message.

    Args:
        message: The message to echo back
    """
    logger.info(f"example_simple_tool called with: {message}")
    return f"Echo: {message}"


@mcp.tool()
async def example_tool_with_options(
    query: str,
    limit: int = 10,
    include_metadata: bool = False
) -> dict[str, Any]:
    """An example tool with optional parameters.

    Args:
        query: The search query
        limit: Maximum number of results (default: 10)
        include_metadata: Whether to include metadata (default: False)
    """
    logger.info(f"Searching for: {query}, limit={limit}")

    # Simulated results
    results = [
        {"id": i, "title": f"Result {i} for '{query}'"}
        for i in range(min(limit, 5))
    ]

    response = {"results": results, "count": len(results)}

    if include_metadata:
        response["metadata"] = {
            "query": query,
            "limit": limit,
            "total_available": 100
        }

    return response


@mcp.tool()
async def example_api_tool(resource_id: str) -> dict[str, Any]:
    """Fetch a resource from an external API.

    Args:
        resource_id: The ID of the resource to fetch
    """
    try:
        # In a real implementation, this would call the API
        # result = await make_api_request(f"resources/{resource_id}")

        # Simulated response
        result = {
            "id": resource_id,
            "name": f"Resource {resource_id}",
            "status": "active"
        }
        return result
    except Exception as e:
        logger.error(f"API error: {e}")
        return {"error": str(e)}


@mcp.tool()
async def example_data_processing_tool(
    data: list[dict[str, Any]],
    operation: str = "summarize"
) -> dict[str, Any]:
    """Process a list of data items.

    Args:
        data: List of data items to process
        operation: Operation to perform (summarize, filter, transform)
    """
    if operation == "summarize":
        return {
            "total_items": len(data),
            "fields": list(data[0].keys()) if data else [],
            "sample": data[:3] if data else []
        }
    elif operation == "filter":
        # Example: filter items with 'active' status
        filtered = [item for item in data if item.get("status") == "active"]
        return {"filtered_items": filtered, "count": len(filtered)}
    elif operation == "transform":
        # Example: extract specific fields
        transformed = [
            {"id": item.get("id"), "name": item.get("name")}
            for item in data
        ]
        return {"transformed": transformed}
    else:
        return {"error": f"Unknown operation: {operation}"}


# =============================================================================
# RESOURCES (Optional - for exposing data)
# =============================================================================

# Uncomment to add resources
# @mcp.resource("config://settings")
# def get_settings() -> str:
#     """Expose server settings as a resource."""
#     import json
#     return json.dumps({
#         "api_url": API_BASE_URL,
#         "timeout": DEFAULT_TIMEOUT
#     })


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the MCP server."""
    logger.info("Starting MCP server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
