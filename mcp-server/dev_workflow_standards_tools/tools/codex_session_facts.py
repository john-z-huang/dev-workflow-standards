"""Thin MCP adapters for Codex session fact guidance and preparation."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..services.codex_session_facts import (
    CodexSessionSource,
    get_codex_session_summary_guidance as _get_codex_session_summary_guidance,
    order_codex_session_sources as _order_codex_session_sources,
    prepare_codex_session_memory as _prepare_codex_session_memory,
)
from ._registration import _register_adapter


def get_codex_session_summary_guidance(
    custom_questions: list[str] | None = None,
    custom_template: str | None = None,
) -> dict:
    """返回默认或用户指定的 Codex 会话摘要问题和模板；不读取会话或写入 Memory。"""
    return _get_codex_session_summary_guidance(custom_questions, custom_template)


def order_codex_session_sources(sources: list[CodexSessionSource]) -> dict:
    """校验、去重并按显式 created_at 分组会话来源，不核验宿主元数据。"""
    return _order_codex_session_sources(sources)


def prepare_codex_session_memory(
    repo_path: str,
    source: CodexSessionSource,
    summary: str,
    evidence_refs: list[str],
    topic: str = "codex-sessions",
    persistence_allowed: bool = True,
    existing_memory_name: str | None = None,
) -> dict:
    """准备 Serena write_memory 参数；不读取原文或执行 Memory 写入。"""
    return _prepare_codex_session_memory(
        repo_path=repo_path,
        source=source,
        summary=summary,
        evidence_refs=evidence_refs,
        topic=topic,
        persistence_allowed=persistence_allowed,
        existing_memory_name=existing_memory_name,
    )


def register_codex_session_fact_tools(server: MCPServer) -> None:
    """注册三个只读会话事实助手；它们不连接宿主会话或 Serena。"""
    read_only = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
    for service in (
        get_codex_session_summary_guidance,
        order_codex_session_sources,
        prepare_codex_session_memory,
    ):
        _register_adapter(server, service, read_only)
