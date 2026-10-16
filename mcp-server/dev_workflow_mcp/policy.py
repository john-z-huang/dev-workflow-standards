"""Stable repository, branch, commit and GitHub input policy."""

import re

ROOT_BRANCH_NAMES = frozenset({"main", "master"})
WORK_BRANCH_PATTERN = re.compile(
    r"^(?:(?:agent|feat|fix|docs|refactor|personal)/"
    r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*"
    r"|personal-[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
FORBIDDEN_AGENT_NAMES = (
    "codex", "claude", "antigravity", "opencode", "cursor", "copilot", "cline",
    "roo-code", "roo_code", "aider", "continue", "windsurf", "devin", "gemini",
    "cody", "junie", "kiro", "goose", "augment", "amazon-q", "amazon_q",
)
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
SUBJECT_PATTERN = re.compile(r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$")
ATTRIBUTION_PATTERN = re.compile(
    r"(?:generated\s+(?:with|by)|created\s+with|assisted\s+by|authored\s+by|co-?authored-?by)",
    re.IGNORECASE,
)
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OID_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
REMOTE_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
def branch_errors(branch_name: str) -> list[str]:
    errors: list[str] = []
    if branch_name not in ROOT_BRANCH_NAMES and not WORK_BRANCH_PATTERN.fullmatch(branch_name):
        errors.append("必须是 main/master，或使用允许的类别前缀和小写连字符格式")
    hits = [name for name in FORBIDDEN_AGENT_NAMES if name in branch_name.lower()]
    if hits:
        errors.append(f"包含禁止的产品名: {', '.join(hits)}")
    return errors
