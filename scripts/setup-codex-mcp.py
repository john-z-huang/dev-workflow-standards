#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit>=0.15,<1"]
# ///
"""Install or register this repository's MCP server and forward required env names."""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import ParseError

DEFAULT_SERVER = "dev-workflow-standards-tools"
DEFAULT_ENV_NAMES = ("OPENAI_API_KEY", "OPENAI_BASE_URL")
HTTP_POLICY_FIELDS = (
    "default_tools_approval_mode",
    "tools",
    "enabled_tools",
    "disabled_tools",
    "startup_timeout_sec",
    "tool_timeout_sec",
    "required",
)
TIMEOUT = 30
INSTALL_TIMEOUT = 300


class SetupError(RuntimeError):
    """Safe user-facing setup error. Never include config or subprocess contents."""


@dataclass(frozen=True)
class Registration:
    name: str
    transport: str
    command: str
    args: tuple[str, ...]
    enabled: bool


def target_config(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().absolute()
    codex_home = os.environ.get("CODEX_HOME")
    home = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return home / "config.toml"


def _read_target(
    path: Path, *, allow_missing: bool
) -> tuple[bytes, os.stat_result] | None:
    try:
        path_info = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None
        raise SetupError("Codex config file does not exist") from None
    except OSError:
        raise SetupError("Codex config file could not be inspected") from None
    if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISREG(path_info.st_mode):
        raise SetupError("Codex config target must be a regular, non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise SetupError(
                "Codex config target must be a regular, non-symlink file"
            ) from None
        raise SetupError("Codex config file could not be inspected") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (
            path_info.st_dev,
            path_info.st_ino,
        ):
            raise SetupError("Codex config target changed during inspection")
        chunks: list[bytes] = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), info
    except SetupError:
        raise
    except OSError:
        raise SetupError("Codex config file could not be read") from None
    finally:
        os.close(fd)


def _parse(raw: bytes) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(raw.decode("utf-8"))
    except (UnicodeDecodeError, ParseError):
        raise SetupError("Codex config is not valid UTF-8 TOML") from None


def _validate_env_vars(server: Any, name: str) -> None:
    values = server.get("env_vars", [])
    if not isinstance(values, list):
        raise SetupError(f"Codex env_vars must be an array for server {name}")
    for item in values:
        if isinstance(item, str):
            continue
        if isinstance(item, dict):
            var_name = item.get("name")
            source = item.get("source", "local")
            if not isinstance(var_name, str) or source not in {"local", "remote"}:
                raise SetupError(f"Codex env_vars entry is malformed for server {name}")
            continue
        raise SetupError(f"Codex env_vars entry is malformed for server {name}")


def _stdio_table(document: Any, name: str, *, required: bool) -> Any | None:
    servers = document.get("mcp_servers")
    if servers is None:
        if required:
            raise SetupError("Codex config has no mcp_servers table")
        return None
    if not isinstance(servers, dict):
        raise SetupError("Codex mcp_servers setting must be a table")
    server = servers.get(name)
    if server is None:
        if required:
            raise SetupError(f"Codex server section is missing: {name}")
        return None
    if not isinstance(server, dict):
        raise SetupError(f"Codex server section is malformed: {name}")
    if "url" in server or "http_headers" in server:
        raise SetupError(f"Codex server is not stdio: {name}")
    command = server.get("command")
    args = server.get("args", [])
    if (
        not isinstance(command, str)
        or not command
        or not isinstance(args, list)
        or not all(isinstance(arg, str) for arg in args)
    ):
        raise SetupError(f"Codex server is not a valid stdio registration: {name}")
    _validate_env_vars(server, name)
    return server


def _check_sources(server: Any, server_name: str, env_names: tuple[str, ...]) -> None:
    sources: dict[str, set[str]] = {}
    for item in server.get("env_vars", []):
        if isinstance(item, str):
            sources.setdefault(item, set()).add("local")
        else:
            sources.setdefault(str(item["name"]), set()).add(
                str(item.get("source", "local"))
            )
    for name in env_names:
        if "remote" in sources.get(name, set()):
            raise SetupError(f"Codex env_vars marks {name} as remote for {server_name}")


def _snapshot_replacement(path: Path, name: str, *, replacing: bool) -> dict[str, Any]:
    snapshot = _read_target(path, allow_missing=True)
    if snapshot is None:
        return {}
    raw, _info = snapshot
    document = _parse(raw)
    if replacing and tomlkit.dumps(document).encode("utf-8") != raw:
        raise SetupError(
            "Codex config uses a TOML layout that cannot be safely rewritten without reformatting"
        )
    servers = document.get("mcp_servers")
    if servers is None:
        return {}
    if not isinstance(servers, dict):
        raise SetupError("Codex mcp_servers setting must be a table")
    server = servers.get(name)
    if server is None:
        return {}
    if not isinstance(server, dict):
        raise SetupError(f"Codex server section is malformed: {name}")
    if "url" in server or "http_headers" in server:
        if not replacing:
            raise SetupError(f"Codex server is not stdio: {name}")
        return {
            key: deepcopy(server[key]) for key in HTTP_POLICY_FIELDS if key in server
        }
    _stdio_table(document, name, required=True)
    _check_sources(server, name, DEFAULT_ENV_NAMES)
    if not replacing:
        return {}
    return {
        key: deepcopy(value)
        for key, value in server.items()
        if key not in {"command", "args", "enabled"}
    }


def _merge_config(
    path: Path,
    name: str,
    *,
    dry_run: bool = False,
    preserved: dict[str, Any] | None = None,
) -> bool:
    snapshot = _read_target(path, allow_missing=False)
    assert snapshot is not None
    original, info = snapshot
    document = _parse(original)
    original_roundtrip = tomlkit.dumps(document).encode("utf-8")
    server = _stdio_table(document, name, required=True)
    assert server is not None
    _check_sources(server, name, DEFAULT_ENV_NAMES)
    expected = deepcopy(document)
    expected_server = expected["mcp_servers"][name]
    for key, value in (preserved or {}).items():
        expected_server[key] = deepcopy(value)
    changed = bool(preserved)
    for key, value in (preserved or {}).items():
        server[key] = deepcopy(value)
    env_vars = server.get("env_vars")
    if env_vars is None:
        env_vars = tomlkit.array().multiline(False)
        server["env_vars"] = env_vars
    existing: set[str] = set()
    for item in env_vars:
        existing.add(item if isinstance(item, str) else str(item["name"]))
    for variable in DEFAULT_ENV_NAMES:
        if variable not in existing:
            env_vars.append(variable)
            existing.add(variable)
            changed = True
    if not changed:
        return False
    if original_roundtrip != original:
        raise SetupError(
            "Codex config uses a TOML layout that cannot be safely rewritten without reformatting"
        )
    rendered = tomlkit.dumps(document).encode("utf-8")
    verified = _parse(rendered)
    verified_server = _stdio_table(verified, name, required=True)
    assert verified_server is not None
    _check_sources(verified_server, name, DEFAULT_ENV_NAMES)
    forwarded = {
        item if isinstance(item, str) else str(item["name"])
        for item in verified_server.get("env_vars", [])
    }
    if not set(DEFAULT_ENV_NAMES).issubset(forwarded):
        raise SetupError(
            "Codex config validation failed; required env_vars are missing"
        )
    check = deepcopy(verified)
    check["mcp_servers"][name].pop("env_vars", None)
    expected["mcp_servers"][name].pop("env_vars", None)
    if check != expected:
        raise SetupError("Codex config validation failed; no changes were written")
    if dry_run:
        return True
    current = _read_target(path, allow_missing=False)
    assert current is not None
    current_bytes, current_info = current
    if (
        (current_info.st_dev, current_info.st_ino) != (info.st_dev, info.st_ino)
        or stat.S_IMODE(current_info.st_mode) != stat.S_IMODE(info.st_mode)
        or current_bytes != original
    ):
        raise SetupError("Codex config changed during update; retry after reviewing it")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as f:
            temp_path = Path(f.name)
            f.write(rendered)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, stat.S_IMODE(info.st_mode))
        current = _read_target(path, allow_missing=False)
        assert current is not None
        current_bytes, current_info = current
        if (
            (current_info.st_dev, current_info.st_ino) != (info.st_dev, info.st_ino)
            or stat.S_IMODE(current_info.st_mode) != stat.S_IMODE(info.st_mode)
            or current_bytes != original
        ):
            raise SetupError(
                "Codex config changed during update; retry after reviewing it"
            )
        os.replace(temp_path, path)
        temp_path = None
    except SetupError:
        raise
    except OSError:
        raise SetupError("Codex config could not be updated") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
    return True


def _run(
    argv: list[str],
    *,
    stage: str,
    env: dict[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> str:
    try:
        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError(f"{stage} failed or timed out") from None
    if result.returncode != 0:
        raise SetupError(f"{stage} failed ({result.returncode})")
    return result.stdout


def _json_command(argv: list[str], *, stage: str, env: dict[str, str]) -> Any:
    try:
        return json.loads(_run(argv, stage=stage, env=env))
    except (json.JSONDecodeError, TypeError):
        raise SetupError(f"{stage} returned invalid JSON") from None


def _listed_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        servers = value.get("servers", value.get("mcpServers"))
        if isinstance(servers, dict):
            if not all(
                isinstance(key, str) and isinstance(item, dict)
                for key, item in servers.items()
            ):
                raise SetupError("Codex returned a malformed MCP server listing")
            return set(servers)
        value = servers
    if not isinstance(value, list):
        raise SetupError("Codex returned an invalid MCP server listing")
    names: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SetupError("Codex returned a malformed MCP server listing entry")
        if item["name"] in names:
            raise SetupError("Codex returned a duplicate MCP server listing entry")
        names.add(item["name"])
    return names


def _registration(value: Any, expected_name: str) -> Registration:
    if not isinstance(value, dict) or value.get("name") != expected_name:
        raise SetupError(f"Codex returned an invalid registration for {expected_name}")
    transport = value.get("transport")
    if not isinstance(transport, dict):
        raise SetupError(f"Codex returned an invalid transport for {expected_name}")
    enabled = value.get("enabled")
    if not isinstance(enabled, bool):
        raise SetupError(f"Codex returned an invalid enabled state for {expected_name}")
    kind = transport.get("type")
    if kind == "http":
        return Registration(expected_name, "http", "", (), enabled)
    if kind != "stdio":
        raise SetupError(
            f"Codex returned an unsupported transport type for {expected_name}"
        )
    command, args = transport.get("command"), transport.get("args", [])
    if (
        not isinstance(command, str)
        or not isinstance(args, list)
        or not all(isinstance(arg, str) for arg in args)
    ):
        raise SetupError(
            f"Codex returned an invalid stdio registration for {expected_name}"
        )
    return Registration(expected_name, "stdio", command, tuple(args), enabled)


def _tool_bin() -> Path:
    uv = shutil.which("uv")
    if uv is None:
        raise SetupError("uv was not found on PATH")
    output = _run([uv, "tool", "dir", "--bin"], stage="uv tool directory lookup")
    path = Path(output.strip()).expanduser()
    if not path.is_absolute():
        raise SetupError("uv returned an invalid tool bin directory")
    return path


def _executable(args: argparse.Namespace, *, after_install: bool) -> Path:
    if args.executable is not None:
        path = args.executable.expanduser()
        if not path.is_absolute():
            raise SetupError("--executable must be an absolute path")
    else:
        path = _tool_bin() / "dev-workflow-standards-tools"
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        if args.install and not after_install:
            return path.resolve()
        raise SetupError("installed MCP executable was not found") from None
    if not resolved.is_file() or (os.name != "nt" and not os.access(resolved, os.X_OK)):
        raise SetupError("installed MCP executable is not executable")
    return resolved


def _same_registration(registration: Registration, executable: Path) -> bool:
    if (
        not registration.enabled
        or registration.transport != "stdio"
        or registration.args
    ):
        return False
    try:
        return Path(registration.command).resolve() == executable.resolve()
    except (OSError, RuntimeError):
        return False


def _codex_env(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(path.parent)
    return env


def _env_only(args: argparse.Namespace, path: Path) -> int:
    changed = _merge_config(path, args.server, dry_run=args.dry_run, preserved=None)
    if args.dry_run:
        print(f"Would merge env_vars {list(DEFAULT_ENV_NAMES)!r} into {args.server}")
    elif changed:
        print(f"Updated env_vars for {args.server}")
    else:
        print(f"Environment forwarding already configured for {args.server}")
    return 0


def _setup(args: argparse.Namespace, path: Path) -> int:
    if args.dry_run:
        if args.install:
            source = Path(__file__).resolve().parents[1] / "mcp-server"
            print(f"Would install MCP tool from {source}")
        print(f"Would register or reuse Codex server {args.server}")
        print(f"Would merge env_vars {list(DEFAULT_ENV_NAMES)!r}")
        return 0
    codex = shutil.which("codex")
    if codex is None:
        raise SetupError("Codex CLI was not found on PATH")

    # Resolve the expected launcher and check Codex before installation or registration writes.
    executable = _executable(args, after_install=False)
    codex_env = _codex_env(path)
    _run(
        [str(Path(codex).resolve()), "--version"],
        stage="Codex CLI preflight",
        env=codex_env,
    )
    codex_path = str(Path(codex).resolve())
    names = _listed_names(
        _json_command(
            [codex_path, "mcp", "list", "--json"],
            stage="Codex MCP listing",
            env=codex_env,
        )
    )
    registration: Registration | None = None
    if args.server in names:
        registration = _registration(
            _json_command(
                [codex_path, "mcp", "get", args.server, "--json"],
                stage="Codex MCP registration lookup",
                env=codex_env,
            ),
            args.server,
        )
    matching = registration is not None and _same_registration(registration, executable)
    pending = not matching
    if registration is not None and pending and not args.replace:
        raise SetupError(f"Codex server {args.server} conflicts; use --replace")
    preserved = _snapshot_replacement(path, args.server, replacing=pending)

    installed = False
    if args.install:
        uv = shutil.which("uv")
        if uv is None:
            raise SetupError("uv was not found on PATH")
        install_argv = [str(Path(uv).resolve()), "tool", "install", "--managed-python"]
        if args.force:
            install_argv.append("--force")
        install_argv.append(str(Path(__file__).resolve().parents[1] / "mcp-server"))
        try:
            _run(install_argv, stage="uv tool install", timeout=INSTALL_TIMEOUT)
        except SetupError as exc:
            raise SetupError(
                f"uv tool installation did not complete; inspect installed tool state before "
                f"retrying: {exc}"
            ) from exc
        installed = True
        try:
            executable = _executable(args, after_install=True)
        except SetupError as exc:
            raise SetupError(
                f"installation completed; executable verification failed: {exc}"
            ) from exc
    else:
        executable = _executable(args, after_install=True)

    if pending:
        try:
            _run(
                [codex_path, "mcp", "add", args.server, "--", str(executable)],
                stage="Codex MCP registration",
                env=codex_env,
            )
        except SetupError as exc:
            prefix = "installation completed; " if installed else ""
            raise SetupError(
                f"{prefix}registration did not complete; inspect the selected Codex config "
                f"before retrying: {exc}"
            ) from exc
        try:
            _merge_config(path, args.server, preserved=preserved)
        except SetupError as exc:
            raise SetupError(
                f"registration applied for {args.server}; environment forwarding/settings repair "
                f"is pending: {exc}"
            ) from exc
        print(f"Registered and configured {args.server}")
    else:
        _merge_config(path, args.server)
        print(f"Reused and configured {args.server}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server", default=DEFAULT_SERVER, help="Codex MCP server name"
    )
    parser.add_argument("--config", type=Path, help="Codex config.toml path")
    parser.add_argument(
        "--env-only", action="store_true", help="repair forwarding only"
    )
    parser.add_argument(
        "--install", action="store_true", help="install the local MCP tool first"
    )
    parser.add_argument(
        "--force", action="store_true", help="force install; requires --install"
    )
    parser.add_argument(
        "--executable", type=Path, help="absolute installed MCP executable path"
    )
    parser.add_argument(
        "--replace", action="store_true", help="replace a conflicting registration"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show a safe action plan"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.force and not args.install:
        parser.error("--force requires --install")
    if args.env_only and (
        args.install or args.force or args.executable or args.replace
    ):
        parser.error(
            "--env-only cannot be combined with installation or registration options"
        )
    if not args.server or any(char in args.server for char in "\x00\r\n"):
        parser.error("--server must be a nonempty single-line name")
    path = target_config(args.config)
    if not args.env_only and path.name != "config.toml":
        parser.error(
            "registration --config must name config.toml; use --env-only for other files"
        )
    try:
        if args.env_only:
            return _env_only(args, path)
        return _setup(args, path)
    except SetupError as exc:
        print(f"setup-codex-mcp: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
