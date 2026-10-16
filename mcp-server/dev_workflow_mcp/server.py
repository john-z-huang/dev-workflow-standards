"""MCP server composition root and stdio entrypoint."""

from mcp.server import MCPServer

from .tools.github import register_github_tools
from .tools.git import register_git_tools
from .tools.repository import register_repository_tools


mcp = MCPServer(
    "dev-workflow-standards-mcp",
    instructions=(
        "Tools act on the explicitly supplied repo_path and run only fixed, domain-specific Git/GitHub operations. "
        "Check applicable user authorization before every write and rely on Codex writes approval. "
        "If an operation is not covered, do not substitute a generic command runner."
    ),
)

register_git_tools(mcp)
register_repository_tools(mcp)
register_github_tools(mcp)


def main() -> None:
    """Start the local Codex MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
