"""Thin MCP adapters for local repository and worktree workflows."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..services import workflows
from ._registration import _register_adapter


def register_repository_tools(server: MCPServer) -> None:
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    local_write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
    destructive_write = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)
    idempotent_write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    tools = (
        (workflows.list_repository_worktrees, read_only),
        (workflows.switch_repository_branch, local_write),
        (workflows.pull_origin_branch_fast_forward, ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)),
        (workflows.fetch_upstream_branch, ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)),
        (workflows.merge_upstream_branch_fast_forward, local_write),
        (workflows.rebase_repository_branch, destructive_write),
        (workflows.remove_repository_worktree, destructive_write),
        (workflows.create_repository_worktree, local_write),
        (workflows.capture_untracked_file_manifest, read_only),
        (workflows.copy_untracked_files_to_worktree, local_write),
        (workflows.configure_project_hooks_path, idempotent_write),
    )
    for service, annotations in tools:
        _register_adapter(server, service, annotations)
