from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import tomlkit

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "setup-codex-mcp.py"
SPEC = importlib.util.spec_from_file_location("setup_codex_mcp", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
setup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = setup
SPEC.loader.exec_module(setup)


def config(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class EnvOnlyTests(unittest.TestCase):
    def test_default_server_merge_preserves_unrelated_settings_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml",
                '# keep comment\n[other]\nvalue = "untouched"\n\n'
                '[mcp_servers.dev-workflow-standards-tools]\ncommand = "/installed/server"\n'
                'args = []\napproval = "writes"\nenv = { EXISTING = "kept" }\n'
                'env_vars = ["KEEP"]\n',
            )
            path.chmod(0o640)
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(setup.main(["--env-only", "--config", str(path)]), 0)
            text = path.read_text(encoding="utf-8")
            data = tomlkit.parse(text)
            server = data["mcp_servers"][setup.DEFAULT_SERVER]
            self.assertEqual(
                server["env_vars"], ["KEEP", "OPENAI_API_KEY", "OPENAI_BASE_URL"]
            )
            self.assertEqual(server["approval"], "writes")
            self.assertEqual(server["env"], {"EXISTING": "kept"})
            self.assertIn("# keep comment", text)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertIn(setup.DEFAULT_SERVER, out.getvalue())

    def test_env_only_is_idempotent_and_runs_no_external_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "custom.toml",
                '[mcp_servers.demo]\ncommand = "runner"\nargs = []\n'
                'env_vars = ["OPENAI_API_KEY", "OPENAI_BASE_URL"]\n',
            )
            before, mtime = path.read_bytes(), path.stat().st_mtime_ns
            with (
                patch.object(setup.subprocess, "run", side_effect=AssertionError),
                patch.object(setup.shutil, "which", side_effect=AssertionError),
            ):
                self.assertEqual(
                    setup.main(
                        ["--env-only", "--server", "demo", "--config", str(path)]
                    ),
                    0,
                )
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_env_only_dry_run_reads_but_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml",
                '[mcp_servers.demo]\ncommand = "runner"\n',
            )
            before, mtime = path.read_bytes(), path.stat().st_mtime_ns
            self.assertEqual(
                setup.main(
                    [
                        "--env-only",
                        "--server",
                        "demo",
                        "--config",
                        str(path),
                        "--dry-run",
                    ]
                ),
                0,
            )
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_missing_registration_is_not_created_in_env_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml", "[mcp_servers.other]\ncommand='x'\n"
            )
            before = path.read_bytes()
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(
                    setup.main(
                        ["--env-only", "--server", "missing", "--config", str(path)]
                    ),
                    2,
                )
            self.assertIn("section is missing", err.getvalue())
            self.assertEqual(path.read_bytes(), before)

    def test_remote_source_conflict_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml",
                '[mcp_servers.demo]\ncommand="runner"\n'
                'env_vars=[{name="OPENAI_API_KEY",source="remote"}]\n',
            )
            before = path.read_bytes()
            with self.assertRaisesRegex(setup.SetupError, "remote"):
                setup._merge_config(path, "demo")
            self.assertEqual(path.read_bytes(), before)

    def test_symlink_and_fifo_targets_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = config(
                root / "target.toml", '[mcp_servers.demo]\ncommand="runner"\n'
            )
            link = root / "link.toml"
            link.symlink_to(target)
            with self.assertRaisesRegex(setup.SetupError, "non-symlink"):
                setup._merge_config(link, "demo")
            if hasattr(os, "mkfifo"):
                fifo = root / "fifo.toml"
                os.mkfifo(fifo)
                with self.assertRaisesRegex(setup.SetupError, "regular"):
                    setup._merge_config(fifo, "demo")

    def test_unsupported_roundtrip_layout_fails_for_change_but_noop_stays_exact(
        self,
    ) -> None:
        prefix = (
            '[[fruit]]\nname="apple"\n\n[unrelated]\nflag=true\n\n'
            '[fruit.texture]\nsmooth=true\n\n[mcp_servers.demo]\ncommand="echo"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = config(Path(directory) / "config.toml", prefix)
            before, mtime = path.read_bytes(), path.stat().st_mtime_ns
            self.assertNotEqual(tomlkit.dumps(tomlkit.parse(prefix)), prefix)
            with self.assertRaisesRegex(setup.SetupError, "cannot be safely rewritten"):
                setup._merge_config(path, "demo")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mtime_ns, mtime)
            complete = prefix + 'env_vars=["OPENAI_API_KEY","OPENAI_BASE_URL"]\n'
            path.write_text(complete, encoding="utf-8")
            before, mtime = path.read_bytes(), path.stat().st_mtime_ns
            self.assertFalse(setup._merge_config(path, "demo"))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_atomic_replace_failure_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml",
                '[mcp_servers.demo]\ncommand="runner"\n',
            )
            before = path.read_bytes()
            with (
                patch.object(setup.os, "replace", side_effect=OSError("synthetic")),
                self.assertRaisesRegex(setup.SetupError, "could not be updated"),
            ):
                setup._merge_config(path, "demo")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).glob(".config.toml.*")), [])

    def test_detected_concurrent_change_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = config(
                Path(directory) / "config.toml",
                '[mcp_servers.demo]\ncommand="runner"\n',
            )
            original = setup._read_target
            calls = 0

            def changing_read(candidate: Path, *, allow_missing: bool):
                nonlocal calls
                if candidate == path:
                    calls += 1
                    if calls == 3:
                        path.write_text('[mcp_servers.demo]\ncommand="changed"\n')
                return original(candidate, allow_missing=allow_missing)

            with (
                patch.object(setup, "_read_target", side_effect=changing_read),
                self.assertRaisesRegex(setup.SetupError, "changed during update"),
            ):
                setup._merge_config(path, "demo")
            self.assertIn("changed", path.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(directory).glob(".config.toml.*")), [])


class RegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "codex-home" / "config.toml"
        self.exe = self.root / "bin" / "dev-workflow-standards-tools"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.exe.chmod(0o755)
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _codex_mocks(
        self, *, listed: bool, existing: dict[str, Any] | None = None, add=None
    ):
        def run(argv, **kwargs):
            env = kwargs.get("env")
            self.calls.append((argv, env))
            if argv[1:3] == ["mcp", "list"]:
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    json.dumps([{"name": setup.DEFAULT_SERVER}] if listed else []),
                    "",
                )
            if argv[1:3] == ["mcp", "get"]:
                return subprocess.CompletedProcess(argv, 0, json.dumps(existing), "")
            if "mcp" in argv and "add" in argv:
                if add:
                    add(argv, env)
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[-1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "codex test", "")
            return subprocess.CompletedProcess(argv, 0, str(self.root / "tool-bin"), "")

        return run

    def test_default_registration_adds_required_names_and_uses_selected_codex_home(
        self,
    ) -> None:
        def destructive_add(argv, env):
            self.assertEqual(env["CODEX_HOME"], str(self.config.parent))
            self.config.parent.mkdir(parents=True, exist_ok=True)
            self.config.write_text(
                f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand = "{argv[-1]}"\nargs = []\n',
                encoding="utf-8",
            )

        with (
            patch.object(
                setup.shutil,
                "which",
                side_effect=lambda name: "/codex" if name == "codex" else "/uv",
            ),
            patch.object(
                setup.subprocess,
                "run",
                side_effect=self._codex_mocks(listed=False, add=destructive_add),
            ),
        ):
            self.assertEqual(
                setup.main(
                    ["--config", str(self.config), "--executable", str(self.exe)]
                ),
                0,
            )
        parsed = tomllib.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(
            parsed["mcp_servers"][setup.DEFAULT_SERVER]["env_vars"],
            ["OPENAI_API_KEY", "OPENAI_BASE_URL"],
        )
        add_call = next(call for call, _env in self.calls if "add" in call)
        self.assertEqual(add_call[-2:], ["--", str(self.exe.resolve())])

    def test_matching_registration_repairs_env_without_upsert(self) -> None:
        config(
            self.config,
            f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="{self.exe}"\nargs=[]\n'
            'approval = "writes"\n',
        )
        existing = {
            "name": setup.DEFAULT_SERVER,
            "enabled": True,
            "transport": {"type": "stdio", "command": str(self.exe), "args": []},
        }
        with (
            patch.object(setup.shutil, "which", return_value="/codex"),
            patch.object(
                setup.subprocess,
                "run",
                side_effect=self._codex_mocks(listed=True, existing=existing),
            ),
        ):
            self.assertEqual(
                setup.main(
                    ["--config", str(self.config), "--executable", str(self.exe)]
                ),
                0,
            )
        self.assertFalse(any("add" in call for call, _env in self.calls))
        parsed = tomllib.loads(self.config.read_text(encoding="utf-8"))
        server = parsed["mcp_servers"][setup.DEFAULT_SERVER]
        self.assertEqual(server["approval"], "writes")
        self.assertEqual(server["env_vars"], ["OPENAI_API_KEY", "OPENAI_BASE_URL"])

    def test_replace_restores_stdio_settings_after_destructive_upsert(self) -> None:
        config(
            self.config,
            f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="/old/launcher"\nargs=[]\n'
            'enabled=false\nenv_vars=["KEEP"]\nenv={EXISTING="safe"}\n'
            'default_tools_approval_mode="writes"\ntool_timeout_sec=17\n',
        )
        existing = {
            "name": setup.DEFAULT_SERVER,
            "enabled": True,
            "transport": {"type": "stdio", "command": "/old/launcher", "args": []},
        }

        def add(argv, _env):
            self.config.write_text(
                f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="{argv[-1]}"\nargs=[]\nenabled=true\n',
                encoding="utf-8",
            )

        with (
            patch.object(setup.shutil, "which", return_value="/codex"),
            patch.object(
                setup.subprocess,
                "run",
                side_effect=self._codex_mocks(listed=True, existing=existing, add=add),
            ),
        ):
            self.assertEqual(
                setup.main(
                    [
                        "--config",
                        str(self.config),
                        "--executable",
                        str(self.exe),
                        "--replace",
                    ]
                ),
                0,
            )
        server = tomllib.loads(self.config.read_text(encoding="utf-8"))["mcp_servers"][
            setup.DEFAULT_SERVER
        ]
        self.assertTrue(server["enabled"])
        self.assertEqual(
            server["env_vars"], ["KEEP", "OPENAI_API_KEY", "OPENAI_BASE_URL"]
        )
        self.assertEqual(server["env"], {"EXISTING": "safe"})
        self.assertEqual(server["default_tools_approval_mode"], "writes")
        self.assertEqual(server["tool_timeout_sec"], 17)

    def test_http_replace_keeps_only_common_policy(self) -> None:
        config(
            self.config,
            f'[mcp_servers.{setup.DEFAULT_SERVER}]\nurl="https://example.invalid"\n'
            'bearer_token_env_var="OLD"\ndefault_tools_approval_mode="writes"\n'
            'disabled_tools=["x"]\n',
        )
        existing = {
            "name": setup.DEFAULT_SERVER,
            "enabled": True,
            "transport": {"type": "http", "url": "https://example.invalid"},
        }

        def add(argv, _env):
            config(
                self.config,
                f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="{argv[-1]}"\nargs=[]\nenabled=true\n',
            )

        with (
            patch.object(setup.shutil, "which", return_value="/codex"),
            patch.object(
                setup.subprocess,
                "run",
                side_effect=self._codex_mocks(listed=True, existing=existing, add=add),
            ),
        ):
            self.assertEqual(
                setup.main(
                    [
                        "--config",
                        str(self.config),
                        "--executable",
                        str(self.exe),
                        "--replace",
                    ]
                ),
                0,
            )
        server = tomllib.loads(self.config.read_text(encoding="utf-8"))["mcp_servers"][
            setup.DEFAULT_SERVER
        ]
        self.assertEqual(server["default_tools_approval_mode"], "writes")
        self.assertEqual(server["disabled_tools"], ["x"])
        self.assertNotIn("url", server)
        self.assertNotIn("bearer_token_env_var", server)

    def test_conflict_and_invalid_config_fail_before_install(self) -> None:
        config(
            self.config,
            f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="/old"\nargs=[]\n',
        )
        existing = {
            "name": setup.DEFAULT_SERVER,
            "enabled": True,
            "transport": {"type": "stdio", "command": "/old", "args": []},
        }
        with (
            patch.object(
                setup.shutil,
                "which",
                side_effect=lambda name: "/codex" if name == "codex" else "/uv",
            ),
            patch.object(
                setup.subprocess,
                "run",
                side_effect=self._codex_mocks(listed=True, existing=existing),
            ),
        ):
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(
                    setup.main(["--install", "--config", str(self.config)]), 2
                )
        self.assertIn("use --replace", err.getvalue())
        self.assertFalse(any("install" in call for call, _env in self.calls))
        self.assertFalse(any("add" in call for call, _env in self.calls))

    def test_symlink_config_fails_before_install_or_registration(self) -> None:
        target = config(self.root / "target.toml", "[other]\nvalue=1\n")
        self.config.parent.mkdir(parents=True)
        self.config.symlink_to(target)
        with (
            patch.object(
                setup.shutil,
                "which",
                side_effect=lambda name: "/codex" if name == "codex" else "/uv",
            ),
            patch.object(
                setup.subprocess, "run", side_effect=self._codex_mocks(listed=False)
            ),
        ):
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(
                    setup.main(["--install", "--config", str(self.config)]), 2
                )
        self.assertIn("non-symlink", err.getvalue())
        self.assertFalse(any("install" in call for call, _env in self.calls))
        self.assertFalse(any("add" in call for call, _env in self.calls))

    def test_malformed_toml_fails_before_install_or_registration(self) -> None:
        config(self.config, "not = [valid\n")
        with (
            patch.object(
                setup.shutil,
                "which",
                side_effect=lambda name: "/codex" if name == "codex" else "/uv",
            ),
            patch.object(
                setup.subprocess, "run", side_effect=self._codex_mocks(listed=False)
            ),
        ):
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(
                    setup.main(["--install", "--config", str(self.config)]), 2
                )
        self.assertIn("not valid UTF-8 TOML", err.getvalue())
        self.assertFalse(any("install" in call for call, _env in self.calls))
        self.assertFalse(any("add" in call for call, _env in self.calls))

    def test_failed_add_reports_uncertain_partial_state_without_echoing_output(
        self,
    ) -> None:
        marker = "SYNTHETIC_SUBPROCESS_OUTPUT"

        def run(argv, **kwargs):
            self.calls.append((argv, kwargs.get("env")))
            if argv[-1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[1:3] == ["mcp", "list"]:
                return subprocess.CompletedProcess(argv, 0, "[]", "")
            if "add" in argv:
                self.config.parent.mkdir(parents=True, exist_ok=True)
                self.config.write_text(
                    f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="{argv[-1]}"\nargs=[]\n',
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(argv, 7, marker, marker)
            return subprocess.CompletedProcess(argv, 0, "", "")

        with (
            patch.object(setup.shutil, "which", return_value="/codex"),
            patch.object(setup.subprocess, "run", side_effect=run),
        ):
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(
                    setup.main(
                        ["--config", str(self.config), "--executable", str(self.exe)]
                    ),
                    2,
                )
        self.assertIn("registration did not complete", err.getvalue())
        self.assertIn("inspect the selected Codex config", err.getvalue())
        self.assertNotIn(marker, err.getvalue())
        self.assertNotIn(
            "env_vars",
            tomllib.loads(self.config.read_text(encoding="utf-8"))["mcp_servers"][
                setup.DEFAULT_SERVER
            ],
        )

    def test_install_precedes_registration_and_force_is_forwarded(self) -> None:
        install_exe = self.root / "tool-bin" / "dev-workflow-standards-tools"

        def run(argv, **kwargs):
            self.calls.append((argv, kwargs.get("env")))
            if argv[1:3] == ["mcp", "list"]:
                return subprocess.CompletedProcess(argv, 0, "[]", "")
            if argv[-1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[1:4] == ["tool", "install", "--managed-python"]:
                install_exe.parent.mkdir(parents=True, exist_ok=True)
                install_exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                install_exe.chmod(0o755)
                return subprocess.CompletedProcess(argv, 0, "", "")
            if "add" in argv:
                self.config.parent.mkdir(parents=True, exist_ok=True)
                self.config.write_text(
                    f'[mcp_servers.{setup.DEFAULT_SERVER}]\ncommand="{argv[-1]}"\nargs=[]\n',
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(argv, 0, str(self.root / "tool-bin"), "")

        with (
            patch.object(
                setup.shutil,
                "which",
                side_effect=lambda name: "/codex" if name == "codex" else "/uv",
            ),
            patch.object(setup.subprocess, "run", side_effect=run),
        ):
            self.assertEqual(
                setup.main(["--install", "--force", "--config", str(self.config)]), 0
            )
        install_index = next(
            i
            for i, (call, _) in enumerate(self.calls)
            if call[1:3] == ["tool", "install"]
        )
        add_index = next(i for i, (call, _) in enumerate(self.calls) if "add" in call)
        self.assertLess(install_index, add_index)
        self.assertIn("--force", self.calls[install_index][0])

    def test_registration_dry_run_has_no_config_reads_or_subprocesses(self) -> None:
        with (
            patch.object(setup, "_read_target", side_effect=AssertionError),
            patch.object(setup.subprocess, "run", side_effect=AssertionError),
            patch.object(setup.shutil, "which", side_effect=AssertionError),
        ):
            self.assertEqual(
                setup.main(["--dry-run", "--config", str(self.config), "--install"]), 0
            )

    def test_config_home_is_forwarded_and_arbitrary_registration_filename_rejected(
        self,
    ) -> None:
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root / "home")}):
            self.assertEqual(setup.target_config(), self.root / "home" / "config.toml")
        err = StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            setup.main(["--config", str(self.root / "custom.toml"), "--dry-run"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("must name config.toml", err.getvalue())

    def test_subprocess_error_does_not_echo_captured_contents(self) -> None:
        sentinel = "SYNTHETIC_SENTINEL_VALUE"
        argv = ["fake-codex"]
        with (
            patch.object(
                setup.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(argv, 5, sentinel, sentinel),
            ),
            self.assertRaises(setup.SetupError) as caught,
        ):
            setup._run(argv, stage="Codex probe")
        self.assertNotIn(sentinel, str(caught.exception))


class StandaloneTests(unittest.TestCase):
    def test_pep723_script_runs_from_external_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            path = config(
                cwd / "external.toml",
                '[mcp_servers.demo]\ncommand="runner"\nargs=[]\n',
            )
            result = subprocess.run(
                [
                    "uv",
                    "--offline",
                    "run",
                    "--script",
                    str(SCRIPT),
                    "--env-only",
                    "--server",
                    "demo",
                    "--config",
                    str(path),
                    "--dry-run",
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OPENAI_API_KEY", result.stdout)
            self.assertNotIn("command=", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
