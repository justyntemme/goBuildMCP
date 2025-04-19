"""
FastMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

from pathlib import Path
from typing import Tuple
from mcp.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("go-builder")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool()
def build(project_dir: str) -> Tuple[str, bool]:
    """Build go Project in project_dir param and reply with success/fail"""

    return "", False
