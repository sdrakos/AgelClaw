# Common MCP Server Patterns

## 1. Database Connector

```python
from mcp.server.fastmcp import FastMCP
import asyncpg

mcp = FastMCP("postgres-connector")

# Connection pool (initialize once)
pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            "postgresql://user:pass@localhost/db"
        )
    return pool


@mcp.tool()
async def query_database(sql: str, params: list = None) -> list[dict]:
    """Execute a SQL query and return results.

    Args:
        sql: SQL query to execute
        params: Optional query parameters
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *(params or []))
        return [dict(row) for row in rows]


@mcp.tool()
async def get_table_schema(table_name: str) -> dict:
    """Get schema information for a table.

    Args:
        table_name: Name of the table
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1
        """, table_name)
        return {"table": table_name, "columns": [dict(c) for c in columns]}
```

## 2. REST API Wrapper

```python
from mcp.server.fastmcp import FastMCP
import httpx
from typing import Optional

mcp = FastMCP("api-wrapper")

API_BASE = "https://api.example.com/v1"
API_KEY = "your-api-key"  # Use env vars in production


@mcp.tool()
async def list_resources(
    resource_type: str,
    page: int = 1,
    per_page: int = 20
) -> dict:
    """List resources from the API.

    Args:
        resource_type: Type of resource (users, products, orders)
        page: Page number (default: 1)
        per_page: Items per page (default: 20)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/{resource_type}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            params={"page": page, "per_page": per_page}
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def create_resource(
    resource_type: str,
    data: dict
) -> dict:
    """Create a new resource.

    Args:
        resource_type: Type of resource to create
        data: Resource data
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/{resource_type}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=data
        )
        response.raise_for_status()
        return response.json()
```

## 3. File Processing Server

```python
from mcp.server.fastmcp import FastMCP
from pathlib import Path
import json
import csv

mcp = FastMCP("file-processor")

ALLOWED_DIR = Path("/data")  # Restrict to safe directory


def safe_path(filepath: str) -> Path:
    """Ensure path is within allowed directory."""
    path = (ALLOWED_DIR / filepath).resolve()
    if not str(path).startswith(str(ALLOWED_DIR)):
        raise ValueError("Path outside allowed directory")
    return path


@mcp.tool()
async def read_json(filepath: str) -> dict:
    """Read and parse a JSON file.

    Args:
        filepath: Path to JSON file (relative to data dir)
    """
    path = safe_path(filepath)
    return json.loads(path.read_text())


@mcp.tool()
async def read_csv(filepath: str, limit: int = 100) -> list[dict]:
    """Read a CSV file and return as list of dicts.

    Args:
        filepath: Path to CSV file
        limit: Max rows to return (default: 100)
    """
    path = safe_path(filepath)
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        return [row for i, row in enumerate(reader) if i < limit]


@mcp.tool()
async def write_json(filepath: str, data: dict) -> str:
    """Write data to a JSON file.

    Args:
        filepath: Output path
        data: Data to write
    """
    path = safe_path(filepath)
    path.write_text(json.dumps(data, indent=2))
    return f"Written to {path}"
```

## 4. Web Scraper

```python
from mcp.server.fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup

mcp = FastMCP("web-scraper")


@mcp.tool()
async def scrape_page(url: str, selector: str = None) -> dict:
    """Scrape content from a webpage.

    Args:
        url: URL to scrape
        selector: Optional CSS selector to extract specific content
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    if selector:
        elements = soup.select(selector)
        content = [el.get_text(strip=True) for el in elements]
    else:
        content = soup.get_text(strip=True)

    return {
        "url": str(response.url),
        "title": soup.title.string if soup.title else None,
        "content": content
    }


@mcp.tool()
async def extract_links(url: str) -> list[dict]:
    """Extract all links from a webpage.

    Args:
        url: URL to extract links from
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    links = []

    for a in soup.find_all('a', href=True):
        links.append({
            "text": a.get_text(strip=True),
            "href": a['href']
        })

    return links
```

## 5. Integration Server (Slack Example)

```python
from mcp.server.fastmcp import FastMCP
import httpx
import os

mcp = FastMCP("slack-integration")

SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_API = "https://slack.com/api"


async def slack_request(method: str, **kwargs) -> dict:
    """Make authenticated Slack API request."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API}/{method}",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
            json=kwargs
        )
        return response.json()


@mcp.tool()
async def send_message(channel: str, text: str) -> dict:
    """Send a message to a Slack channel.

    Args:
        channel: Channel ID or name
        text: Message text
    """
    return await slack_request(
        "chat.postMessage",
        channel=channel,
        text=text
    )


@mcp.tool()
async def list_channels() -> list[dict]:
    """List all public channels."""
    result = await slack_request("conversations.list", types="public_channel")
    return result.get("channels", [])


@mcp.tool()
async def get_channel_history(
    channel: str,
    limit: int = 10
) -> list[dict]:
    """Get recent messages from a channel.

    Args:
        channel: Channel ID
        limit: Number of messages (default: 10)
    """
    result = await slack_request(
        "conversations.history",
        channel=channel,
        limit=limit
    )
    return result.get("messages", [])
```

## 6. Utility/Calculation Server

```python
from mcp.server.fastmcp import FastMCP
import math
from datetime import datetime, timedelta

mcp = FastMCP("utilities")


@mcp.tool()
async def calculate(expression: str) -> float:
    """Evaluate a mathematical expression safely.

    Args:
        expression: Math expression (e.g., "2 + 2 * 3")
    """
    # Safe evaluation with limited functions
    allowed_names = {
        "abs": abs, "round": round,
        "min": min, "max": max,
        "sum": sum, "len": len,
        "sqrt": math.sqrt, "pow": pow,
        "sin": math.sin, "cos": math.cos,
        "pi": math.pi, "e": math.e
    }
    return eval(expression, {"__builtins__": {}}, allowed_names)


@mcp.tool()
async def date_calculator(
    start_date: str,
    days: int = 0,
    weeks: int = 0,
    months: int = 0
) -> str:
    """Calculate a date offset.

    Args:
        start_date: Start date (YYYY-MM-DD) or 'today'
        days: Days to add/subtract
        weeks: Weeks to add/subtract
        months: Months to add/subtract (approximate)
    """
    if start_date == "today":
        dt = datetime.now()
    else:
        dt = datetime.strptime(start_date, "%Y-%m-%d")

    dt += timedelta(days=days, weeks=weeks)
    dt += timedelta(days=months * 30)  # Approximate

    return dt.strftime("%Y-%m-%d")


@mcp.tool()
async def unit_converter(
    value: float,
    from_unit: str,
    to_unit: str
) -> dict:
    """Convert between units.

    Args:
        value: Value to convert
        from_unit: Source unit (km, mi, kg, lb, c, f)
        to_unit: Target unit
    """
    conversions = {
        ("km", "mi"): lambda x: x * 0.621371,
        ("mi", "km"): lambda x: x * 1.60934,
        ("kg", "lb"): lambda x: x * 2.20462,
        ("lb", "kg"): lambda x: x * 0.453592,
        ("c", "f"): lambda x: x * 9/5 + 32,
        ("f", "c"): lambda x: (x - 32) * 5/9,
    }

    key = (from_unit.lower(), to_unit.lower())
    if key not in conversions:
        return {"error": f"Unknown conversion: {from_unit} to {to_unit}"}

    result = conversions[key](value)
    return {
        "input": f"{value} {from_unit}",
        "output": f"{result:.4f} {to_unit}"
    }
```
