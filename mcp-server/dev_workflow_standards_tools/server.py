"""MCP server composition root and stdio entrypoint."""

from mcp.server import MCPServer

from .tools._descriptions import SERVER_DESCRIPTION, SERVER_INSTRUCTIONS
from .tools.github import register_github_tools
from .tools.git import register_git_tools
from .tools.ai_workflow import register_ai_workflow_tools
from .tools.codex_session_facts import register_codex_session_fact_tools
from .tools.repository import register_repository_tools


mcp = MCPServer(
    "dev-workflow-standards-tools",
    description=SERVER_DESCRIPTION,
    instructions=SERVER_INSTRUCTIONS,
)

register_git_tools(mcp)
register_repository_tools(mcp)
register_github_tools(mcp)
register_codex_session_fact_tools(mcp)
register_ai_workflow_tools(mcp)


def main() -> None:
    """Start the local Codex MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
