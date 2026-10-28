from __future__ import annotations

import json
import re
import inspect
import subprocess
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase
from importlib.resources import files
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch
from pydantic import create_model

from dev_workflow_standards_tools.services import codex_session_facts as service, validation, workflows
from dev_workflow_standards_tools.services.codex_session_facts import (
    CodexSessionSource,
    get_codex_session_summary_guidance,
    order_codex_session_sources,
    prepare_codex_session_memory,
)
from dev_workflow_standards_tools.server import mcp as complete_server


ROOT = Path(__file__).parents[1]
DOC = ROOT / "references" / "codex-session-facts.md"


def tool_json(result) -> dict:
    return json.loads(result.content[0].text)


def source(
    thread_id: str,
    *,
    created_at: str | None = "2026-01-01T00:00:00Z",
    ended_at: str | None = None,
    title: str | None = "示例 会话",
) -> CodexSessionSource:
    return CodexSessionSource(
        source_link=f"codex://threads/{thread_id}",
        created_at=created_at,
        ended_at=ended_at,
        title=title,
    )


class GuidanceTests(unittest.TestCase):
    def test_resource_questions_and_template_match_reference(self) -> None:
        resource = json.loads(
            files("dev_workflow_standards_tools")
            .joinpath("resources/codex_session_summary.json")
            .read_text(encoding="utf-8")
        )
        document = DOC.read_text(encoding="utf-8")
        section = document.split("## 默认阅读问题\n", 1)[1].split("\n## Serena Memory", 1)[0]
        questions = []
        for line in section.splitlines():
            if not line.startswith("|") or line.startswith("| 摘要主题") or line.startswith("|---"):
                continue
            _, topic, question, _ = line.split("|", 3)
            questions.append(f"{topic.strip()}：{question.strip()}")
        template = re.search(r"```markdown\n(.*?)\n```", document, re.DOTALL)
        self.assertIsNotNone(template)
        self.assertEqual(resource["default_questions"], questions)
        self.assertEqual(resource["default_template"], template.group(1))

    def test_guidance_defaults_include_limits_and_followups(self) -> None:
        result = get_codex_session_summary_guidance()
        self.assertEqual(len(result["questions"]), 7)
        self.assertIn("# <created_at>", result["template"])
        self.assertFalse(result["customized"])
        self.assertFalse(result["reads_history"])
        self.assertFalse(result["writes_memory"])
        self.assertTrue(any("read_thread" in step for step in result["next_steps"]))

    def test_custom_questions_and_template_replace_defaults(self) -> None:
        template = "# user format\n\nraw body"
        result = get_codex_session_summary_guidance(["只核实目标"], template)
        self.assertEqual(result["questions"], ["只核实目标"])
        self.assertEqual(result["template"], template)
        self.assertTrue(result["customized"])

    def test_explicit_empty_custom_values_are_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "custom_questions"):
            get_codex_session_summary_guidance([])
        with self.assertRaisesRegex(ValueError, "custom_questions"):
            get_codex_session_summary_guidance([" "])
        with self.assertRaisesRegex(ValueError, "custom_template"):
            get_codex_session_summary_guidance(custom_template="")

    def test_resource_failure_does_not_fabricate_defaults(self) -> None:
        with patch.object(service, "files", side_effect=FileNotFoundError("missing")):
            with self.assertRaisesRegex(RuntimeError, "包内"):
                get_codex_session_summary_guidance()

    def test_fully_custom_guidance_does_not_need_default_resource(self) -> None:
        with patch.object(service, "files", side_effect=FileNotFoundError("missing")):
            result = get_codex_session_summary_guidance(["only question"], "# custom")
        self.assertEqual(result["questions"], ["only question"])
        self.assertEqual(result["template"], "# custom")


class SessionSourceTests(unittest.TestCase):
    A = "00000000-0000-4000-8000-000000000001"
    B = "00000000-0000-4000-8000-000000000002"
    C = "00000000-0000-4000-8000-000000000003"

    def test_source_link_validation_and_id_consistency(self) -> None:
        bad_links = [
            f"codex://user@threads/{self.A}",
            f"codex://threads/{self.A}?x=1",
            f"codex://threads/{self.A}#part",
            f"codex://threads/{self.A}/extra",
            f"codex://threads/{self.A}/",
            f" codex://threads/{self.A}",
            f"codex://threads/{self.A} ",
            f"codex://threads/{self.A}\n",
            f"codex://threads/{self.A}\t",
            "codex://threads/not-a-uuid",
            f"https://threads/{self.A}",
        ]
        for link in bad_links:
            with self.subTest(link=link), self.assertRaises(ValueError):
                CodexSessionSource(source_link=link)
        with self.assertRaisesRegex(ValueError, "不一致"):
            CodexSessionSource(source_link=f"codex://threads/{self.A}", thread_id=self.B)
        with self.assertRaisesRegex(ValueError, "标准 UUID"):
            CodexSessionSource(source_link=f"codex://threads/{self.A}", thread_id="bad")

    def test_timestamps_require_timezone_and_ended_not_before_created(self) -> None:
        for bad in (
            "2026-01-01T00:00:00",
            "NaN",
            "2026-13-01T00:00:00Z",
            "2026-01-01T00:00:00.1234567Z",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                source(self.A, created_at=bad)
        with self.assertRaisesRegex(ValueError, "不能早于"):
            source(
                self.A,
                created_at="2026-01-02T00:00:00Z",
                ended_at="2026-01-01T23:59:59Z",
            )

    def test_duplicate_id_merges_missing_metadata_and_timezone_equivalence(self) -> None:
        a_missing = source(self.A, created_at=None, title=None)
        a_complete = source(self.A, created_at="2025-12-31T16:00:00-08:00", title="同一会话")
        b = source(self.B, created_at="2026-01-01T00:00:00Z")
        result = order_codex_session_sources([a_missing, a_complete, b])
        self.assertEqual(result["deduplicated_count"], 2)
        self.assertEqual(result["priority_groups"][0]["created_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(result["priority_groups"][0]["sources"][0]["thread_id"], self.A)
        self.assertFalse(result["ready"])
        self.assertTrue(result["priority_groups"][0]["same_creation_time"])

    def test_later_created_session_wins_without_updated_at_inference(self) -> None:
        older = source(self.A, created_at="2026-01-01T00:00:00Z")
        newer = source(self.B, created_at="2026-01-02T00:00:00Z")
        result = order_codex_session_sources([older, newer])
        self.assertEqual(result["priority_groups"][0]["sources"][0]["thread_id"], self.B)
        self.assertEqual(result["ordering_basis"].count("updatedAt"), 1)
        with self.assertRaises(ValueError):
            CodexSessionSource(
                source_link=f"codex://threads/{self.A}",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2027-01-01T00:00:00Z",
            )

    def test_missing_and_tied_creation_times_require_clarification(self) -> None:
        tied = source(self.A, created_at="2026-01-01T00:00:00Z")
        tied_other = source(self.B, created_at="2025-12-31T19:00:00-05:00")
        missing = source(self.C, created_at=None)
        result = order_codex_session_sources([tied, tied_other, missing])
        self.assertFalse(result["ready"])
        self.assertEqual(len(result["ambiguities"]), 2)
        self.assertTrue(result["priority_groups"][0]["same_creation_time"])
        self.assertIsNone(result["priority_groups"][0]["within_group_order"])
        self.assertEqual(result["missing_created_at"][0]["thread_id"], self.C)

    def test_duplicate_metadata_conflicts_are_errors(self) -> None:
        first = source(self.A, title="旧标题")
        second = source(self.A, title="新标题")
        with self.assertRaisesRegex(ValueError, "title 元数据冲突"):
            order_codex_session_sources([first, second])
        later = source(self.A, created_at="2026-01-02T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "created_at 元数据冲突"):
            order_codex_session_sources([first, later])

    def test_merged_created_and_ended_metadata_is_revalidated(self) -> None:
        created_only = CodexSessionSource(
            source_link=f"codex://threads/{self.A}",
            created_at="2026-01-02T00:00:00Z",
            title="同一会话",
        )
        ended_only = CodexSessionSource(
            source_link=f"codex://threads/{self.A}",
            ended_at="2026-01-01T23:00:00Z",
            title="同一会话",
        )
        with self.assertRaisesRegex(ValueError, "合并后的 ended_at"):
            order_codex_session_sources([created_only, ended_only])


class MemoryPreparationTests(unittest.TestCase):
    THREAD = "00000000-0000-4000-8000-000000000004"
    SUMMARY = "## 用户结构\n\n摘要正文原样保留。"

    def setUp(self) -> None:
        self.source = source(
            self.THREAD,
            created_at="2026-01-02T03:04:05+08:00",
            title="测试 / Safe: 名称",
        )
        self.root = "/tmp/example-repo"

    def test_prepares_safe_payload_unknown_end_and_preserves_summary(self) -> None:
        with patch.object(service, "_validated_repo_path", return_value=(self.root, None)):
            result = prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3", "turn:7"],
            )
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["repo_path"], self.root)
        self.assertEqual(result["metadata"]["memory_project_root"], self.root)
        self.assertNotIn("project_scope", result["metadata"])
        self.assertEqual(result["metadata"]["ended_at"], "unknown")
        self.assertTrue(result["memory_name"].startswith("codex-sessions/20260101T190405Z-unknown-"))
        self.assertTrue(result["memory_name"].endswith(f"-{self.THREAD}"))
        self.assertNotIn("/Safe:", result["memory_name"])
        self.assertTrue(result["payload"]["content"].endswith(self.SUMMARY))
        self.assertEqual(result["payload"]["content"], self.SUMMARY)
        self.assertEqual(result["metadata"]["source_link"], f"codex://threads/{self.THREAD}")
        self.assertTrue(result["requires_source_review"])
        self.assertFalse(result["metadata"]["metadata_verified"])

    def test_persistence_disabled_returns_no_payload(self) -> None:
        with patch.object(service, "_validated_repo_path") as repo_validation:
            result = prepare_codex_session_memory(
                self.root,
                self.source,
                "",
                [],
                persistence_allowed=False,
            )
        repo_validation.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["payload"])
        self.assertFalse(result["persistence_authorization_verified"])
        self.assertNotIn("memory_name", result)

    def test_empty_summary_or_evidence_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "summary"):
            prepare_codex_session_memory(self.root, self.source, "  ", ["turn:3"])
        with self.assertRaisesRegex(ValueError, "evidence_refs"):
            prepare_codex_session_memory(self.root, self.source, self.SUMMARY, [])
        with self.assertRaisesRegex(ValueError, "evidence_refs"):
            prepare_codex_session_memory(self.root, self.source, self.SUMMARY, [" "])

    def test_topic_rejects_absolute_traversal_and_global(self) -> None:
        for topic in ("/tmp", "../escape", "foo/../bar", "global", "global/topic", "foo\\bar", "a//b"):
            with self.subTest(topic=topic), patch.object(
                service, "_validated_repo_path", return_value=(self.root, None)
            ), self.assertRaises(ValueError):
                prepare_codex_session_memory(self.root, self.source, self.SUMMARY, ["turn:3"], topic=topic)

    def test_existing_memory_name_is_stable_for_same_thread(self) -> None:
        existing_name = f"codex-sessions/20251231T190405Z-unknown-old-title-{self.THREAD}"
        with patch.object(service, "_validated_repo_path", return_value=(self.root, None)):
            result = prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                existing_memory_name=existing_name,
            )
        self.assertEqual(result["memory_name"], existing_name)
        with self.assertRaisesRegex(ValueError, "相同 thread_id"):
            prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                existing_memory_name=f"codex-sessions/old-{self.THREAD[:-1]}5",
            )

    def test_repo_root_failure_returns_no_payload(self) -> None:
        with patch.object(service, "_validated_repo_path", return_value=(None, "not a root")):
            result = prepare_codex_session_memory(self.root, self.source, self.SUMMARY, ["turn:3"])
        self.assertFalse(result["ok"])
        self.assertIsNone(result["payload"])
        self.assertEqual(result["error"], "not a root")

    def test_existing_name_cannot_escape_topic(self) -> None:
        for name in (
            f"other/entry-{self.THREAD}",
            f"codex-sessions/../entry-{self.THREAD}",
            f"codex-sessions/nested/entry-{self.THREAD}",
        ):
            with self.subTest(name=name), patch.object(
                service, "_validated_repo_path", return_value=(self.root, None)
            ), self.assertRaises(ValueError):
                prepare_codex_session_memory(
                    self.root,
                    self.source,
                    self.SUMMARY,
                    ["turn:3"],
                    existing_memory_name=name,
                )

    def test_utf8_byte_limits_keep_generated_names_portable(self) -> None:
        long_unicode_source = source(
            self.THREAD,
            title="\U00020000" * 100,
        )
        with patch.object(service, "_validated_repo_path", return_value=(self.root, None)):
            result = prepare_codex_session_memory(
                self.root,
                long_unicode_source,
                self.SUMMARY,
                ["turn:3"],
            )
        basename = result["memory_name"].rsplit("/", 1)[1]
        self.assertLessEqual(len(basename.encode("utf-8")), 255)
        slug = basename.split("-", 2)[2].rsplit(f"-{self.THREAD}", 1)[0]
        self.assertLessEqual(len(slug.encode("utf-8")), 96)

        overlong_topic = "界" * 34
        with self.assertRaisesRegex(ValueError, "UTF-8 字节"):
            prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                topic=overlong_topic,
            )

        long_existing = f"codex-sessions/{'a' * 220}-{self.THREAD}"
        with self.assertRaisesRegex(ValueError, "逻辑条目最多 252"):
            prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                existing_memory_name=long_existing,
            )

        suffix = f"-{self.THREAD}"
        accepted_name = f"codex-sessions/{'a' * (252 - len(suffix))}{suffix}"
        rejected_name = f"codex-sessions/{'a' * (253 - len(suffix))}{suffix}"
        with patch.object(service, "_validated_repo_path", return_value=(self.root, None)):
            accepted = prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                existing_memory_name=accepted_name,
            )
        self.assertEqual(accepted["memory_name"], accepted_name)
        with self.assertRaisesRegex(ValueError, "逻辑条目最多 252"):
            prepare_codex_session_memory(
                self.root,
                self.source,
                self.SUMMARY,
                ["turn:3"],
                existing_memory_name=rejected_name,
            )


class MCPRegistrationTests(IsolatedAsyncioTestCase):
    A = "00000000-0000-4000-8000-000000000005"

    async def test_all_32_tools_registered_with_described_schemas(self) -> None:
        self.assertIn("本地开发工作流 MCP 服务", complete_server.description)
        tools = await complete_server.list_tools()
        self.assertEqual(len(tools), 32)
        by_name = {tool.name: tool for tool in tools}
        self.assertEqual(len(by_name), 32)
        for tool in tools:
            self.assertTrue(tool.description, tool.name)

            def assert_described_properties(schema: dict) -> None:
                for property_schema in schema.get("properties", {}).values():
                    self.assertTrue(property_schema.get("description"), (tool.name, property_schema))
                for value in schema.values():
                    if isinstance(value, dict):
                        assert_described_properties(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                assert_described_properties(item)

            assert_described_properties(tool.input_schema)
        deterministic_names = {
            "get_codex_session_summary_guidance",
            "order_codex_session_sources",
            "prepare_codex_session_memory",
        }
        ai_names = {
            "decide_skill_workflow",
            "decide_codex_session_action",
            "generate_skill_content",
        }
        names = deterministic_names | ai_names
        self.assertTrue(names.issubset(by_name))
        for name in deterministic_names:
            tool = by_name[name]
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertTrue(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            self.assertEqual(tool.input_schema["type"], "object")
        self.assertIn("custom_questions", by_name["get_codex_session_summary_guidance"].input_schema["properties"])
        self.assertIn("sources", by_name["order_codex_session_sources"].input_schema["properties"])
        self.assertIn("source", by_name["prepare_codex_session_memory"].input_schema["properties"])
        for name in ai_names:
            tool = by_name[name]
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertFalse(tool.annotations.idempotent_hint)
            self.assertTrue(tool.annotations.open_world_hint)

    async def test_network_git_annotations_and_discovery_examples_are_explicit(self) -> None:
        tools = {tool.name: tool for tool in await complete_server.list_tools()}
        for name in ("pull_origin_branch_fast_forward", "fetch_upstream_branch"):
            self.assertTrue(tools[name].annotations.open_world_hint)

        branch_tool = tools["create_repository_branch"]
        self.assertFalse(branch_tool.annotations.read_only_hint)
        self.assertFalse(branch_tool.annotations.destructive_hint)
        self.assertFalse(branch_tool.annotations.idempotent_hint)
        self.assertFalse(branch_tool.annotations.open_world_hint)
        self.assertIn("expected_head_oid", branch_tool.input_schema["properties"])
        self.assertIn("null", str(branch_tool.input_schema["properties"]["expected_head_oid"]))
        self.assertTrue(branch_tool.input_schema["properties"]["expected_head_oid"].get("description"))
        self.assertIn("OID是唯一并发条件", branch_tool.description)

        descriptions = {
            "copy_untracked_files_to_worktree": ("结构示例：",),
            "create_github_issue": ("示例：",),
            "cleanup_merged_pr_local_branch": ("示例：",),
            "prepare_codex_session_memory": ("示例：",),
        }
        for name, markers in descriptions.items():
            description = tools[name].description
            marker = next(marker for marker in markers if marker in description)
            example_text = description.split(marker, 1)[1]
            example, _ = json.JSONDecoder().raw_decode(example_text.lstrip())
            self.assertIsInstance(example, dict)

        copy_example, _ = json.JSONDecoder().raw_decode(
            tools["copy_untracked_files_to_worktree"].description.split("结构示例：", 1)[1].lstrip()
        )
        self.assertEqual(len(copy_example["manifest"][0]["sha256"]), 64)
        self.assertEqual(set(copy_example["manifest"][0]), {"path", "sha256", "size"})
        issue_example, _ = json.JSONDecoder().raw_decode(
            tools["create_github_issue"].description.split("示例：", 1)[1].lstrip()
        )
        self.assertEqual(set(issue_example), {"repo_path", "repo", "title", "body", "labels"})
        prepare_example, _ = json.JSONDecoder().raw_decode(
            tools["prepare_codex_session_memory"].description.split("示例：", 1)[1].lstrip()
        )
        CodexSessionSource.model_validate(prepare_example["source"])
        self.assertEqual(
            set(prepare_example), {"repo_path", "source", "summary", "evidence_refs"}
        )

        example_services = {
            "copy_untracked_files_to_worktree": workflows.copy_untracked_files_to_worktree,
            "create_github_issue": workflows.create_github_issue,
            "cleanup_merged_pr_local_branch": validation.cleanup_merged_pr_local_branch,
            "prepare_codex_session_memory": service.prepare_codex_session_memory,
        }
        for name, target in example_services.items():
            marker = "结构示例：" if name == "copy_untracked_files_to_worktree" else "示例："
            text = tools[name].description.split(marker, 1)[1].lstrip()
            example, _ = json.JSONDecoder().raw_decode(text)
            signature = inspect.signature(target)
            hints = get_type_hints(target)
            fields = {
                param_name: (
                    hints[param_name],
                    ... if parameter.default is inspect.Parameter.empty else parameter.default,
                )
                for param_name, parameter in signature.parameters.items()
            }
            input_model = create_model(f"{target.__name__}Input", **fields)
            input_model.model_validate(example)

    async def test_create_repository_branch_via_mcp_call_tool(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcp branch tool 日本語 ") as temp:
            repo = Path(temp) / "repo with spaces"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Synthetic"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repo, check=True)
            (repo / "tracked").write_bytes(b"baseline\n")
            subprocess.run(["git", "add", "tracked"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
            head_oid = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
            raw = await complete_server.call_tool(
                "create_repository_branch",
                {"repo_path": str(repo), "branch_name": "feat/mcp-call", "expected_head_oid": head_oid},
            )
            self.assertFalse(raw.is_error)
            data = raw.structured_content or json.loads(raw.content[0].text)
            self.assertTrue(data["ok"], data)
            self.assertTrue(data["created"])
            self.assertEqual(data["start_head_oid"], head_oid)

    async def test_real_tool_calls_return_expected_guidance_order_and_memory_payload(self) -> None:
        guidance_result = await complete_server.call_tool("get_codex_session_summary_guidance", {})
        guidance = tool_json(guidance_result)
        self.assertEqual(guidance["ok"], True)
        self.assertEqual(len(guidance["questions"]), 7)

        source_input = {
            "source_link": f"codex://threads/{self.A}",
            "created_at": "2026-01-01T00:00:00Z",
            "title": "测试会话",
        }
        order_result = await complete_server.call_tool(
            "order_codex_session_sources", {"sources": [source_input]}
        )
        ordered = tool_json(order_result)
        self.assertEqual(ordered["deduplicated_count"], 1)
        self.assertTrue(ordered["ready"])

        with patch.object(service, "_validated_repo_path", return_value=("/tmp/fixture", None)):
            prepare_result = await complete_server.call_tool(
                "prepare_codex_session_memory",
                {
                    "repo_path": "/tmp/fixture",
                    "source": source_input,
                    "summary": "## User format\nRaw summary.",
                    "evidence_refs": ["turn:2"],
                },
            )
        prepared = tool_json(prepare_result)
        self.assertEqual(prepared["status"], "prepared")
        self.assertTrue(prepared["payload"]["content"].endswith("## User format\nRaw summary."))


if __name__ == "__main__":
    unittest.main()
