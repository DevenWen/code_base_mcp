"""FastMCP quickstart example.

Run from the repository root:
    uv run examples/snippets/servers/fastmcp_quickstart.py
"""

from mcp.server.fastmcp import FastMCP

# Import code base tools
from tools.code_base_tools import register_code_base_tools

# Create an MCP server
mcp = FastMCP("code_base_mcp")

# Register code base tools
register_code_base_tools(mcp)


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.resource("resource://greeting")
def get_greeting() -> str:
    """Provides a simple greeting message."""
    return "Hello from FastMCP Resources!"


@mcp.resource("data://{id}/{format}")
def get_data(id: str, format: str = "json") -> str:
    """Retrieve data in specified format."""
    if format == "xml":
        return f"<data id='{id}' />"
    return f'{{"id": "{id}"}}'


# # Dynamic user profile resource
@mcp.resource("user://{name}")
def get_user_profile(name: str) -> str:
    """Gets a mock student profile for a given name."""
    return f"""User Profile:
- Name: {name}
- Age: 18
- Job: Student
- Status: Active"""


# Run the server
if __name__ == "__main__":
    mcp.run()
