"""MCP adapters for OpenAI-backed semantic workflow helpers."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..services import ai_workflow
from ..services.ai_workflow import (
    ContentGenerationRequest,
    SessionDecisionRequest,
    WorkflowDecisionRequest,
)
from ._registration import _register_adapter


def decide_skill_workflow(request: WorkflowDecisionRequest) -> dict:
    """根据用户请求和固定优先级选择工作流建议；不会执行所选流程。"""
    return ai_workflow.decide_skill_workflow(request)


def decide_codex_session_action(request: SessionDecisionRequest) -> dict:
    """建议历史事实查询和持久化下一步；不会读取会话或写入 Serena Memory。"""
    return ai_workflow.decide_codex_session_action(request)


def generate_skill_content(request: ContentGenerationRequest) -> dict:
    """生成候选内容供 Agent 审阅；不会执行代码或外部操作。"""
    return ai_workflow.generate_skill_content(request)


def register_ai_workflow_tools(server: MCPServer) -> None:
    """注册只读但会访问外部 OpenAI API 的语义工具。"""
    annotations = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    )
    for service in (decide_skill_workflow, decide_codex_session_action, generate_skill_content):
        _register_adapter(server, service, annotations)
