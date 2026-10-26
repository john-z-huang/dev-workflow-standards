"""Shared mechanism for creating transparent, schema-preserving MCP adapters."""

from functools import wraps
from typing import Any, Callable

from mcp.server import MCPServer
from mcp.types import ToolAnnotations


def _register_adapter(server: MCPServer, service: Callable[..., Any], annotations: ToolAnnotations) -> None:
    @wraps(service)
    def adapter(*args: Any, **kwargs: Any) -> Any:
        return service(*args, **kwargs)

    server.tool(annotations=annotations)(adapter)
