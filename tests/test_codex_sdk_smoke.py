from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_sdk_smoke", Path(__file__).with_name("codex_sdk_smoke.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class CodexSDKContractTests(unittest.TestCase):
    def test_missing_or_blank_config_stops_before_subprocess_or_sdk(self):
        cases = ({}, {"OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": " "},
                 {"OPENAI_API_KEY": "", "OPENAI_BASE_URL": "https://example.invalid/v1"})
        for environment in cases:
            with self.subTest(names=list(environment)), patch.dict(os.environ, environment, clear=True), patch.object(smoke, "execute_sdk") as sdk, patch.object(smoke.subprocess, "run") as process:
                with self.assertRaises(smoke.SmokeFailure):
                    smoke.run(Path("unused.whl"), live=True)
                sdk.assert_not_called()
                process.assert_not_called()

    def test_reads_current_environment_without_fallback(self):
        for value in ("one", "two"):
            environment = {"OPENAI_API_KEY": value, "OPENAI_BASE_URL": f"https://{value}.example.invalid/v1"}
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(smoke.credentials(), environment)

    def test_settings_lock_model_effort_and_explicit_provider(self):
        configuration = {"OPENAI_API_KEY": "fake-test-key", "OPENAI_BASE_URL": "https://example.invalid/v1"}
        with patch.dict(os.environ, {"MODEL": "invalid-model", "REASONING_EFFORT": "high"}, clear=True):
            config, environment = smoke.settings(Path("/synthetic/root"), Path("/synthetic/installed"), configuration)
        self.assertEqual(config["model"], "gpt-6-luna")
        self.assertEqual(config["model_reasoning_effort"], "medium")
        provider = config["model_providers"]["sdk_test"]
        self.assertEqual(provider["base_url"], configuration["OPENAI_BASE_URL"])
        self.assertEqual(provider["env_key"], "OPENAI_API_KEY")
        self.assertFalse(provider["requires_openai_auth"])
        self.assertEqual(provider["request_max_retries"], 0)
        self.assertEqual(environment["OPENAI_API_KEY"], configuration["OPENAI_API_KEY"])
        self.assertEqual(config["mcp_servers"][smoke.SERVER]["enabled_tools"], [smoke.TOOL])
        self.assertNotIn(configuration["OPENAI_API_KEY"], "\n".join(smoke.overrides(config)))
        # SDK 命令行覆盖值必须是合法 TOML，并保留全部受控字段。
        parsed = tomllib.loads("\n".join(smoke.overrides(config)))
        self.assertEqual(parsed, config)

    def test_model_words_without_real_tool_event_cannot_pass(self):
        with self.assertRaisesRegex(smoke.SmokeFailure, "missing_actual_mcp_call"):
            smoke.check_turn({"status": "completed", "items": [{"type": "agentMessage", "text": "MCP is installed and works"}]})

    def test_real_event_result_is_checked_for_tool_arguments_and_output(self):
        item = {"type": "mcpToolCall", "server": smoke.SERVER, "tool": smoke.TOOL,
                "arguments": smoke.ARGUMENTS, "status": "completed", "result": {"structuredContent": {
                    "ok": True, "questions": smoke.ARGUMENTS["custom_questions"], "template": smoke.ARGUMENTS["custom_template"]}}}
        turn = {"status": "completed", "items": [item]}
        self.assertEqual(smoke.check_turn(turn), 1)
        for name, value in (("status", "failed"), ("tool", "other"), ("arguments", {}), ("result", {})):
            invalid = copy.deepcopy(turn)
            invalid["items"][0][name] = value
            with self.subTest(field=name), self.assertRaises(smoke.SmokeFailure):
                smoke.check_turn(invalid)
        turn["items"].append({"type": "commandExecution"})
        with self.assertRaisesRegex(smoke.SmokeFailure, "unexpected_agent_action"):
            smoke.check_turn(turn)

    def test_sdk_model_readback_mismatch_prevents_any_model_or_tool_request(self):
        class FakeClient:
            requests = []
            closed = False
            def __init__(self, config):
                self.config = config
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
            def initialize(self): pass
            def close(self): self.closed = True
            def thread_start(self, params):
                self.requests.append(params)
                return SimpleNamespace(model="unexpected-model", reasoning_effort=SimpleNamespace(value="medium"), model_provider="sdk_test")
            def request(self, *args, **kwargs):
                raise AssertionError("must stop before discovery/tool/model request")
        modules = {
            "openai_codex": SimpleNamespace(CodexConfig=lambda **kwargs: kwargs),
            "openai_codex.client": SimpleNamespace(CodexClient=FakeClient),
            "openai_codex.generated.v2_all": SimpleNamespace(ListMcpServerStatusResponse=object, McpServerToolCallResponse=object),
        }
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(smoke.SmokeFailure, "model_or_effort_mismatch"):
                smoke.execute_sdk(Path(temporary), Path(temporary) / "site", {
                    "OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": "https://example.invalid/v1"}, live=True)
        self.assertEqual(FakeClient.requests[0]["model"], "gpt-6-luna")
        self.assertEqual(FakeClient.requests[0]["config"]["model_reasoning_effort"], "medium")

    def test_cli_is_opt_in_and_never_echoes_raw_sdk_errors(self):
        with patch.object(smoke, "run", side_effect=RuntimeError("synthetic-private-key-and-endpoint")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(smoke.main(["--wheel", "test.whl"]), 1)
            self.assertEqual(json.loads(output.getvalue()), {"ok": False, "error_code": "test_setup_failed"})
        with patch.object(smoke, "run", return_value={"ok": True}) as run, patch("sys.stdout", new_callable=io.StringIO):
            smoke.main(["--wheel", "test.whl"])
            self.assertFalse(run.call_args.kwargs["live"])

    def test_sdk_dependency_is_test_only(self):
        project = tomllib.loads((ROOT / "mcp-server" / "pyproject.toml").read_text())
        self.assertTrue(any(item.startswith("openai-codex") for item in project["dependency-groups"]["codex-test"]))
        self.assertFalse(any("codex" in item for item in project["project"]["dependencies"]))
        for source in (ROOT / "mcp-server" / "dev_workflow_standards_tools").rglob("*.py"):
            self.assertNotIn("openai_codex", source.read_text())


if __name__ == "__main__":
    unittest.main()
