"""Thin MCP adapters for local Git validation and repository workflows."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..services import validation, workflows
from ._registration import _register_adapter


def register_git_tools(server: MCPServer) -> None:
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    local_write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
    destructive_write = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)
    tools = (
        (validation.check_branch_names, read_only),
        (validation.check_commit_message, read_only),
        (validation.check_staged_changes, read_only),
        (validation.rewrite_legacy_commit_message, read_only),
        (workflows.stage_repository_paths, local_write),
        (workflows.commit_repository_changes, destructive_write),
    )
    for service, annotations in tools:
        _register_adapter(server, service, annotations)
