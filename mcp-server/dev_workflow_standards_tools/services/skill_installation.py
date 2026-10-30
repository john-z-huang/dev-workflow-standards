"""离线 Skill 快照管理，所有写操作都在本地硬校验后执行。

macOS/Linux 使用内核 no-replace / exchange 原语发布完整目录。合作 CLI 通过
同目标的持久锁串行化；不把该锁描述为对恶意外部文件写入者的隔离机制。
"""

from contextlib import contextmanager
import ctypes
import errno
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile


OWNER = "dev-workflow-standards-tools"
SKILL = "dev-workflow-standards"
DEFAULT_DIRECTORY = "dev-workflow-standards-skill"
MARKER = ".dev-workflow-skill.json"
MAX_FILES = 200
MAX_BYTES = 2_000_000


class SkillError(Exception):
    """可以向用户显示的本地配置或完整性错误。"""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(data: bytes) -> dict:
    try:
        value = json.loads(data)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "owner", "skill", "version", "files"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["owner"] != OWNER or value["skill"] != SKILL
            or not isinstance(value["version"], str) or not 0 < len(value["version"]) <= 120
            or not isinstance(value["files"], dict) or not 0 < len(value["files"]) <= MAX_FILES
            or "SKILL.md" not in value["files"]
        ):
            raise ValueError
        for name, digest in value["files"].items():
            path = PurePosixPath(name)
            if (
                path.is_absolute() or path.as_posix() != name or "\\" in name or "\x00" in name
                or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
                or path.suffix != ".md" or len(name) > 240
                or not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError
        return value
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise SkillError("Skill 清单无效；不执行写入") from None


def _bundle() -> tuple[dict, dict[str, bytes]]:
    root = files("dev_workflow_standards_tools").joinpath("skill_bundle")
    try:
        manifest = _manifest(root.joinpath("manifest.json").read_bytes())
        payload = {name: root.joinpath(name).read_bytes() for name in manifest["files"]}
    except (OSError, UnicodeError):
        raise SkillError("发布包缺少 Skill 资源；请从完整 wheel 安装工具") from None
    if sum(map(len, payload.values())) > MAX_BYTES or any(
        _digest(data) != manifest["files"][name] for name, data in payload.items()
    ):
        raise SkillError("发布包 Skill 资源完整性检查失败")
    return manifest, payload


def _target(raw: str | None) -> Path:
    raw = raw if raw is not None else str(Path.home() / ".agents" / "skills" / DEFAULT_DIRECTORY)
    if not raw or "\x00" in raw or ".." in Path(raw).parts:
        raise SkillError("目标不能为空或含路径穿越")
    target = Path(os.path.abspath(Path(raw).expanduser()))
    if target == Path(target.anchor):
        raise SkillError("不能将文件系统根目录作为 Skill 目标")
    legacy = Path.home() / ".agents" / "skills" / SKILL
    for protected in (legacy, legacy.resolve()):
        if target.is_relative_to(protected) or protected.is_relative_to(target):
            raise SkillError("旧项目目录受保护；请使用 dev-workflow-standards-skill 或其他独立目标")
    for path in reversed((target, *target.parents)):
        if path.is_symlink():
            raise SkillError("目标或祖先目录是符号链接；请提供真实且独立的路径")
        if path.exists() and not path.is_dir():
            raise SkillError("目标或祖先不是普通目录")
        if (path / ".git").exists() or (path / ".git").is_symlink():
            raise SkillError("目标位于 Git checkout 中；不修改开发仓库")
    return target


def _read_regular(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
            raise SkillError("安装包含特殊文件、硬链接或过大文件")
        data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise SkillError("安装文件超过大小上限")
        return data


def _snapshot(target: Path) -> dict[str, str]:
    result = {}
    directories = set()
    def onerror(error):
        raise error

    for parent, dirs, names in os.walk(target, followlinks=False, onerror=onerror):
        for name in dirs:
            path = Path(parent) / name
            if path.is_symlink():
                raise SkillError("安装包含目录符号链接")
            directories.add(path.relative_to(target).as_posix())
        for name in names:
            path = Path(parent) / name
            result[path.relative_to(target).as_posix()] = _digest(_read_regular(path))
            if len(result) > MAX_FILES + 1:
                raise SkillError("安装包含过多文件")
    expected_dirs = {
        parent.as_posix()
        for name in result for parent in PurePosixPath(name).parents if parent != PurePosixPath(".")
    }
    if directories != expected_dirs:
        raise SkillError("安装包含额外目录；请人工核查")
    return result


def _installed(target: Path) -> tuple[dict, dict[str, str]]:
    if not target.is_dir():
        raise SkillError("目标尚未安装；请先使用 skills install")
    try:
        data = _read_regular(target / MARKER)
    except FileNotFoundError:
        raise SkillError("目标不是本工具管理的安装；不会迁移或覆盖旧目录") from None
    manifest = _manifest(data)
    snapshot = _snapshot(target)
    if snapshot != {**manifest["files"], MARKER: _digest(data)}:
        raise SkillError("安装内容已修改、缺失或含额外文件；请人工核查，拒绝更新")
    return manifest, snapshot


def _rename_function():
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        return lambda source, target, exchange: function(source, target, 2 if exchange else 4)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        function = libc.renameat2
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        return lambda source, target, exchange: function(-100, source, -100, target, 2 if exchange else 1)
    raise SkillError("当前平台不支持安全的目录原子发布；仅支持 macOS/Linux")


def _publish(source: Path, target: Path, *, exchange: bool) -> None:
    if _rename_function()(os.fsencode(source), os.fsencode(target), exchange) != 0:
        code = ctypes.get_errno()
        if code in {errno.EEXIST, errno.ENOTEMPTY}:
            raise SkillError("目标已被其他进程创建；原内容保留")
        raise SkillError(f"目录原子发布失败（errno={code}）；不降级为非原子覆盖")


@contextmanager
def _lock(target: Path):
    import fcntl

    path = target.parent / f".{target.name}.skill-install.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SkillError("安装锁不是独立普通文件")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SkillError("另一个安装/更新正在进行；请稍后重试") from None
        yield
    finally:
        os.close(fd)
    # 不删除锁文件，防止第三个进程锁住不同 inode。


def manage_skill(action: str, raw_target: str | None = None, *, dry_run: bool = False) -> dict:
    try:
        return _manage_skill(action, raw_target, dry_run=dry_run)
    except OSError:
        raise SkillError("本地文件访问失败；检查权限、目录类型及残留暂存目录后重试") from None


def _manage_skill(action: str, raw_target: str | None, *, dry_run: bool) -> dict:
    if action not in {"install", "update", "show"}:
        raise SkillError("未知 Skill 操作")
    manifest, payload = _bundle()
    target = _target(raw_target)
    result = {"ok": True, "target": str(target), "skill": SKILL, "package_version": manifest["version"]}

    def preflight():
        _target(str(target))
        if action == "install":
            if target.exists():
                raise SkillError("目标已存在；不覆盖旧目录，受管安装请使用 skills update")
            return None, None
        return _installed(target)

    if action == "show":
        if not target.exists():
            return {**result, "status": "not_installed", "installed_version": None}
        current, _ = _installed(target)
        return {**result, "status": "installed", "installed_version": current["version"]}
    _, before = preflight()
    _rename_function()  # 写入前确认平台能力；文件系统支持由原子操作判定。
    if dry_run:
        return {**result, "status": "preview", "action": action, "changed": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    _target(str(target))
    with _lock(target):
        _, before = preflight()
        if before == {**manifest["files"], MARKER: _digest(_manifest_bytes(manifest))}:
            return {**result, "status": "unchanged", "changed": False}
        parent_identity = target.parent.stat()
        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.skill-stage-", dir=target.parent))
        cleanup_snapshot = None
        try:
            for name, data in payload.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            with (stage / MARKER).open("xb") as stream:
                stream.write(_manifest_bytes(manifest))
                stream.flush()
                os.fsync(stream.fileno())
            _, cleanup_snapshot = _installed(stage)
            # 在发布前重复边界、目录身份与完整快照检查。
            _, latest = preflight()
            parent_now = target.parent.stat()
            if latest != before or (parent_now.st_dev, parent_now.st_ino) != (
                parent_identity.st_dev, parent_identity.st_ino
            ):
                raise SkillError("发布前检测到并发目录修改；保留现有安装")
            _publish(stage, target, exchange=action == "update")
            if action == "update":
                cleanup_snapshot = before
                try:
                    old_matches = _snapshot(stage) == before
                except (SkillError, OSError):
                    old_matches = False
                if not old_matches:
                    # 交换后旧目录仍完整保存。发现非合作写入时撤回，并保留现场。
                    _publish(stage, target, exchange=True)
                    cleanup_snapshot = None
                    raise SkillError(f"检测到外部并发修改；已撤回更新，请核查暂存目录 {stage}")
            return {**result, "status": "installed" if action == "install" else "updated", "changed": True}
        finally:
            # 不删除未知或被外部修改的内容；中断可能留下隐藏暂存副本，但正式目标始终完整。
            if stage.exists() and cleanup_snapshot is not None and _snapshot(stage) == cleanup_snapshot:
                shutil.rmtree(stage)


def _manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
