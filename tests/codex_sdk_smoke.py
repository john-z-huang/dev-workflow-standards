"""测试专用 Codex SDK 驱动；默认仅协议检查，--live 显式启用一次模型测试。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import urlsplit


MODEL = "gpt-6-luna"
EFFORT = "medium"
SERVER = "dev-workflow-standards-tools"
TOOL = "get_codex_session_summary_guidance"
ARGUMENTS = {"custom_questions": ["SDK smoke test question"], "custom_template": "SDK_SMOKE_TEMPLATE"}


class SmokeFailure(Exception):
    """仅包含安全错误分类，不转发 SDK/HTTP/子进程原始异常。"""


def credentials() -> dict[str, str]:
    result = {}
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        value = os.environ.get(name, "")
        if not value.strip():
            raise SmokeFailure("missing_" + name.lower())
        result[name] = value
    try:
        url = urlsplit(result["OPENAI_BASE_URL"])
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError
    except ValueError:
        raise SmokeFailure("invalid_base_url") from None
    return result


def settings(root: Path, site: Path, configuration: dict[str, str]) -> tuple[dict, dict[str, str]]:
    """SDK provider 仅使用显式环境配置，MCP 子进程不继承 API 配置。"""
    launcher = (
        "import sys;sys.path.insert(0," + repr(str(site)) + ");"
        "import dev_workflow_standards_tools as package;"
        "assert package.__file__.startswith(" + repr(str(site) + os.sep) + ");"
        "from dev_workflow_standards_tools.server import main;main()"
    )
    config = {
        "model": MODEL,
        "model_reasoning_effort": EFFORT,
        "model_provider": "sdk_test",
        "model_providers": {"sdk_test": {
            "name": "SDK test provider",
            "base_url": configuration["OPENAI_BASE_URL"],
            "env_key": "OPENAI_API_KEY",
            "wire_api": "responses",
            "requires_openai_auth": False,
            "supports_websockets": False,
            "request_max_retries": 0,
            "stream_max_retries": 0,
        }},
        "mcp_servers": {SERVER: {
            "command": sys.executable,
            "args": ["-I", "-c", launcher],
            "enabled_tools": [TOOL],
            "env_vars": [],
            "env": {"OPENAI_API_KEY": "", "OPENAI_BASE_URL": ""},
            "startup_timeout_sec": 30,
        }},
    }
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "CODEX_HOME": str(root / "codex-state"),
        "RUST_LOG": "off",
        **configuration,
    }
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "all_proxy", "no_proxy", "SSL_CERT_FILE"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return config, environment


def overrides(config: dict, prefix: str = "") -> tuple[str, ...]:
    """将受控结构变为 SDK 支持的 TOML 叶值覆盖，不向磁盘保存配置。"""
    result = []
    for key, value in config.items():
        name = prefix + key
        if isinstance(value, dict):
            result.extend(overrides(value, name + "."))
        else:
            result.append(name + "=" + json.dumps(value))
    return tuple(result)


def guidance_result(value: dict) -> None:
    if value.get("isError") or value.get("error"):
        raise SmokeFailure("mcp_tool_failed")
    body = value.get("structuredContent")
    if not isinstance(body, dict):
        for item in value.get("content", []):
            if item.get("type") == "text":
                try:
                    body = json.loads(item["text"])
                except (ValueError, KeyError):
                    continue
                break
    if not isinstance(body, dict) or body.get("ok") is not True or body.get("questions") != ARGUMENTS["custom_questions"] or body.get("template") != ARGUMENTS["custom_template"]:
        raise SmokeFailure("unexpected_mcp_result")


def check_turn(turn: dict) -> int:
    if turn.get("status") != "completed" or turn.get("error") is not None:
        raise SmokeFailure("model_turn_failed")
    calls = []
    for item in turn.get("items", []):
        if item.get("type") in {"commandExecution", "fileChange", "collabAgentToolCall"}:
            raise SmokeFailure("unexpected_agent_action")
        if item.get("type") == "mcpToolCall":
            if item.get("server") != SERVER or item.get("tool") != TOOL or item.get("arguments") != ARGUMENTS:
                raise SmokeFailure("unexpected_mcp_call")
            if item.get("status") != "completed" or item.get("error") is not None:
                raise SmokeFailure("mcp_tool_failed")
            guidance_result(item.get("result") or {})
            calls.append(item)
    if not calls:
        raise SmokeFailure("missing_actual_mcp_call")
    if len(calls) != 1:
        raise SmokeFailure("unexpected_mcp_call_count")
    return len(calls)


def execute_sdk(root: Path, site: Path, configuration: dict[str, str], *, live: bool = False) -> dict:
    # 延迟导入：普通离线测试及运行时包均不要求安装 SDK。
    try:
        from openai_codex import CodexConfig
        from openai_codex.client import CodexClient
        from openai_codex.generated.v2_all import ListMcpServerStatusResponse, McpServerToolCallResponse
    except ImportError:
        raise SmokeFailure("sdk_dependency_missing") from None

    config, environment = settings(root, site, configuration)
    (root / "codex-state").mkdir()
    workspace = root / "workspace"
    workspace.mkdir()
    timed_out = threading.Event()
    # SDK 启动时自身会合并环境；清空继承防止其他凭据、配置路径或 provider 覆盖混入。
    with patch.dict(os.environ, environment, clear=True):
        client = CodexClient(CodexConfig(
            cwd=str(workspace), env=environment,
            config_overrides=overrides(config),
        ))
        def expire():
            timed_out.set()
            client.close()
        timer = threading.Timer(120, expire)
        timer.daemon = True
        timer.start()
        try:
            with client:
                client.initialize()
                started = client.thread_start({
                    "model": MODEL, "modelProvider": "sdk_test", "config": {"model_reasoning_effort": EFFORT},
                    "cwd": str(workspace), "sandbox": "read-only", "approvalPolicy": "never",
                    "ephemeral": True,
                    "baseInstructions": "You are a test subject. Use only the specified read-only MCP tool with the exact synthetic arguments. Do not inspect files, use shell, write, or delegate.",
                })
                if started.model != MODEL or started.reasoning_effort is None or started.reasoning_effort.value != EFFORT or started.model_provider != "sdk_test":
                    raise SmokeFailure("model_or_effort_mismatch")
                thread_id = started.thread.id
                status = client.request("mcpServerStatus/list", {
                    "threadId": thread_id, "serverName": SERVER, "detail": "toolsAndAuthOnly",
                }, response_model=ListMcpServerStatusResponse)
                servers = [entry for entry in status.data if entry.name == SERVER]
                if len(servers) != 1 or servers[0].tools_error or TOOL not in servers[0].tools or servers[0].server_capabilities is None:
                    raise SmokeFailure("mcp_discovery_failed")
                direct = client.request("mcpServer/tool/call", {
                    "threadId": thread_id, "server": SERVER, "tool": TOOL, "arguments": ARGUMENTS,
                }, response_model=McpServerToolCallResponse)
                guidance_result(direct.model_dump(mode="json", by_alias=True))
                calls = 0
                if live:
                    prompt = "Call " + TOOL + " exactly once with these arguments: " + json.dumps(ARGUMENTS) + ". Then reply OK. Do not answer without calling the tool."
                    turn = client.turn_start(thread_id, prompt, params={"model": MODEL, "effort": EFFORT})
                    client.register_turn_notifications(turn.turn.id)
                    items = []
                    try:
                        while True:
                            notification = client.next_turn_notification(turn.turn.id)
                            value = notification.payload.model_dump(mode="json", by_alias=True)
                            if notification.method == "item/completed":
                                items.append(value["item"])
                            if notification.method == "turn/completed":
                                calls = check_turn({**value["turn"], "items": items})
                                break
                    finally:
                        client.unregister_turn_notifications(turn.turn.id)
                return {"ok": True, "model": MODEL, "effort": EFFORT, "mcp_discovery": "passed",
                        "direct_tool_call": "passed", "model_test": "passed" if live else "not_run",
                        "actual_model_tool_calls": calls}
        except SmokeFailure:
            raise
        except Exception:
            raise SmokeFailure("sdk_timeout" if timed_out.is_set() else "sdk_request_failed") from None
        finally:
            timer.cancel()
            client.close()


def run(wheel: Path, *, live: bool = False) -> dict:
    configuration = credentials()  # 缺配置时在 SDK 启动/安装前停止。
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise SmokeFailure("wheel_required")
    with tempfile.TemporaryDirectory(prefix="codex-sdk-test-") as temporary:
        root = Path(temporary).resolve()
        site = root / "installed"
        result = subprocess.run(["uv", "pip", "install", "--offline", "--no-deps", "--target", str(site), str(wheel.resolve())],
                                text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise SmokeFailure("wheel_install_failed")
        return execute_sdk(root, site, configuration, live=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="测试专用 Codex SDK：固定 gpt-6-luna/medium，无配置或模型回退")
    parser.add_argument("--wheel", type=Path, required=True, help="待测完整 wheel")
    parser.add_argument("--live", action="store_true", help="显式发起一次真实模型测试；默认只检查 SDK/MCP 协议")
    args = parser.parse_args(argv)
    try:
        result = run(args.wheel, live=args.live)
    except SmokeFailure as error:
        print(json.dumps({"ok": False, "error_code": str(error)}))
        return 1
    except Exception:
        print(json.dumps({"ok": False, "error_code": "test_setup_failed"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
