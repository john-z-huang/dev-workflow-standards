"""Shared mechanism for creating transparent, schema-preserving MCP adapters."""

import inspect
from functools import wraps
from typing import Annotated, Any, Callable, get_type_hints

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ._descriptions import PARAMETER_DESCRIPTIONS, TOOL_DESCRIPTIONS


def _register_adapter(server: MCPServer, service: Callable[..., Any], annotations: ToolAnnotations) -> None:
    service_name = service.__name__
    descriptions = PARAMETER_DESCRIPTIONS[service_name]
    signature = inspect.signature(service, follow_wrapped=False)
    type_hints = get_type_hints(service, include_extras=True)
    if set(descriptions) != set(signature.parameters):
        raise ValueError(f"MCP parameter descriptions do not match {service_name} signature")
    parameters = [
        parameter.replace(
            annotation=Annotated[type_hints[parameter.name], Field(description=descriptions[parameter.name])]
        )
        for parameter in signature.parameters.values()
    ]

    @wraps(service)
    def adapter(*args: Any, **kwargs: Any) -> Any:
        return service(*args, **kwargs)

    adapter.__signature__ = signature.replace(parameters=parameters, return_annotation=type_hints.get("return", signature.return_annotation))
    server.tool(description=TOOL_DESCRIPTIONS[service_name], annotations=annotations)(adapter)
