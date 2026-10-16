"""Thin MCP adapters for GitHub-backed workflow use cases."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..services import validation, workflows
from ._registration import _register_adapter


def register_github_tools(server: MCPServer) -> None:
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=True)
    write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)
    destructive_write = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)
    idempotent_write = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True)
    tools = (
        (validation.audit_issue_pr_policy, read_only),
        (validation.cleanup_merged_pr_local_branch, destructive_write),
        (workflows.audit_repository_state, read_only),
        (workflows.list_github_issue_labels, read_only),
        (workflows.create_github_issue, write),
        (workflows.push_issue_branch_to_origin, write),
        (workflows.create_github_pull_request, write),
        (workflows.merge_github_pull_request, destructive_write),
        (workflows.push_fork_main_fast_forward, idempotent_write),
    )
    for service, annotations in tools:
        _register_adapter(server, service, annotations)
