import { createHash } from "node:crypto";
import { execFile as execFileCb } from "node:child_process";
import { createReadStream } from "node:fs";
import { lstat, realpath, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const execFile = promisify(execFileCb);
export type CommandResult = {
  stdout: string;
  stderr: string;
  returncode: number;
};
export async function run(
  args: string[],
  cwd?: string,
  input?: string,
): Promise<CommandResult> {
  try {
    const result = await execFile(args[0]!, args.slice(1), {
      cwd,
      encoding: "utf8",
      maxBuffer: 16 * 1024 * 1024,
      ...(input === undefined ? {} : { input }),
    });
    return { stdout: result.stdout, stderr: result.stderr, returncode: 0 };
  } catch (error) {
    const e = error as NodeJS.ErrnoException & {
      stdout?: string;
      stderr?: string;
      code?: number | string;
    };
    return {
      stdout: e.stdout ?? "",
      stderr: redact(e.stderr ?? e.message ?? ""),
      returncode: typeof e.code === "number" ? e.code : 1,
    };
  }
}
export function redact(value: string): string {
  return value
    .replace(/(https?:\/\/)[^/@\s:]+:[^/@\s]+@/gi, "$1[REDACTED]@")
    .replace(
      /(gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})/g,
      "[REDACTED]",
    );
}
export function lines(text: string): string[] {
  return text.split(/\r?\n/);
}

export const REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
export const OID_RE = /^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$/;
export const REMOTE_BRANCH_RE = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;
const WORK_BRANCH_RE =
  /^(?:(?:agent|feat|fix|docs|refactor|personal)\/[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*|personal-[a-z0-9]+(?:-[a-z0-9]+)*)$/;
const FORBIDDEN = [
  "codex",
  "claude",
  "antigravity",
  "opencode",
  "cursor",
  "copilot",
  "cline",
  "roo-code",
  "roo_code",
  "aider",
  "continue",
  "windsurf",
  "devin",
  "gemini",
  "cody",
  "junie",
  "kiro",
  "goose",
  "augment",
  "amazon-q",
  "amazon_q",
];
export function branchErrors(name: string): string[] {
  const errors: string[] = [];
  if (name !== "main" && name !== "master" && !WORK_BRANCH_RE.test(name))
    errors.push("必须是 main/master，或使用允许的类别前缀和小写连字符格式");
  const hits = FORBIDDEN.filter((item) => name.toLowerCase().includes(item));
  if (hits.length) errors.push(`包含禁止的产品名: ${hits.join(", ")}`);
  return errors;
}
export function expandUser(value: string): string {
  return value === "~"
    ? os.homedir()
    : value.startsWith("~/")
      ? path.join(os.homedir(), value.slice(2))
      : value;
}
export async function validRepo(
  repoPath: string,
): Promise<{ root: string | null; error: string | null }> {
  repoPath = expandUser(repoPath);
  if (!path.isAbsolute(repoPath) || repoPath.split(path.sep).includes(".."))
    return {
      root: null,
      error: "repo_path 必须是绝对路径且不能包含 '..' 路径段",
    };
  let root: string;
  try {
    root = await realpath(repoPath);
  } catch {
    return { root: null, error: "repo_path 不存在或无法解析" };
  }
  try {
    if (!(await stat(root)).isDirectory())
      return { root: null, error: "repo_path 必须指向 Git 仓库目录" };
  } catch {
    return { root: null, error: "repo_path 必须指向 Git 仓库目录" };
  }
  const result = await run(["git", "rev-parse", "--show-toplevel"], root);
  if (result.returncode !== 0)
    return { root: null, error: "repo_path 不是可访问的 Git 仓库或 worktree" };
  let gitRoot: string;
  try {
    gitRoot = await realpath(result.stdout.trim());
  } catch {
    return { root: null, error: "无法解析 Git 仓库根目录" };
  }
  if (gitRoot !== root)
    return { root: null, error: `repo_path 必须是 Git 仓库根目录：${gitRoot}` };
  return { root, error: null };
}
export async function runRepo(repoPath: string, args: string[]) {
  const checked = await validRepo(repoPath);
  return checked.error
    ? {
        result: null as CommandResult | null,
        root: null as string | null,
        error: checked.error,
      }
    : {
        result: await run(args, checked.root!),
        root: checked.root,
        error: null as string | null,
      };
}
export async function currentBranch(root: string): Promise<string | null> {
  const r = await run(["git", "branch", "--show-current"], root);
  return r.returncode === 0 && r.stdout.trim() ? r.stdout.trim() : null;
}
export async function validLocalBranch(
  root: string,
  name: string,
): Promise<string | null> {
  const r = await run(["git", "check-ref-format", "--branch", name], root);
  return r.returncode === 0 ? null : "branch_name 不是有效的本地分支名";
}
export function validRemoteBranch(name: string): boolean {
  return (
    !!name &&
    REMOTE_BRANCH_RE.test(name) &&
    !name.includes("..") &&
    !name.includes("//")
  );
}
export async function requireClean(root: string): Promise<string | null> {
  const r = await run(["git", "status", "--porcelain"], root);
  if (r.returncode !== 0) return "无法读取 Git 工作区状态";
  return r.stdout.trim() ? "工作区存在已暂存、未暂存或未跟踪内容" : null;
}
export function safeRelative(value: string): string | null {
  if (!value || value.includes("\\") || value.startsWith("/")) return null;
  const parts = value.split("/");
  if (
    parts.some((p) => !p || p === "." || p === "..") ||
    parts.includes(".git")
  )
    return null;
  return parts.join("/") === value ? value : null;
}
export function requestedPaths(values: string[]): {
  paths: string[] | null;
  error: string | null;
} {
  if (!values.length) return { paths: null, error: "paths 不能为空" };
  const paths: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const rel = safeRelative(value);
    if (!rel)
      return {
        paths: null,
        error: `路径必须是安全、规范的仓库相对 POSIX 路径: ${JSON.stringify(value)}`,
      };
    if (seen.has(rel))
      return { paths: null, error: `路径重复: ${JSON.stringify(value)}` };
    seen.add(rel);
    paths.push(rel);
  }
  return { paths, error: null };
}
export async function stagedNames(
  root: string,
): Promise<{ paths: string[] | null; error: string | null }> {
  const r = await run(
    ["git", "diff", "--cached", "--name-only", "--no-renames", "-z"],
    root,
  );
  if (r.returncode !== 0)
    return { paths: null, error: "无法读取 staged paths" };
  return { paths: r.stdout.split("\0").filter(Boolean), error: null };
}
export async function validateStagePath(
  root: string,
  rel: string,
): Promise<string | null> {
  const parts = rel.split("/");
  let cursor = root;
  for (const part of parts.slice(0, -1)) {
    cursor = path.join(cursor, part);
    try {
      const s = await lstat(cursor);
      if (s.isSymbolicLink()) return `路径父目录不能是 symlink: ${rel}`;
      if (!s.isDirectory()) return `路径父组件不是目录: ${rel}`;
    } catch {
      /* missing parent allowed only to reach tracked deletion check */
    }
  }
  const candidate = path.join(root, ...parts);
  try {
    const s = await lstat(candidate);
    if (s.isSymbolicLink()) return `不能暂存 symlink: ${rel}`;
    if (!s.isFile()) return `只能暂存普通文件或 tracked deletion: ${rel}`;
    return null;
  } catch {
    const tracked = await run(
      ["git", "ls-files", "--error-unmatch", "--", `:(literal)${rel}`],
      root,
    );
    return tracked.returncode === 0
      ? null
      : `不存在的路径不是 tracked deletion: ${rel}`;
  }
}
export async function absoluteNewPath(
  value: string,
): Promise<{ target: string | null; error: string | null }> {
  value = expandUser(value);
  if (!path.isAbsolute(value) || value.split(path.sep).includes(".."))
    return { target: null, error: "路径必须是绝对路径且不能包含 '..' 路径段" };
  try {
    const parent = await realpath(path.dirname(value));
    return { target: path.join(parent, path.basename(value)), error: null };
  } catch {
    return { target: null, error: "目标父目录不存在或无法解析" };
  }
}
export async function sameGitCommonDir(a: string, b: string): Promise<boolean> {
  const args = [
    "git",
    "rev-parse",
    "--path-format=absolute",
    "--git-common-dir",
  ];
  const [x, y] = await Promise.all([run(args, a), run(args, b)]);
  return (
    x.returncode === 0 &&
    y.returncode === 0 &&
    x.stdout.trim() === y.stdout.trim()
  );
}
export async function sha256(
  file: string,
): Promise<{
  digest: string | null;
  size: number | null;
  error: string | null;
}> {
  try {
    const hash = createHash("sha256");
    let size = 0;
    for await (const chunk of createReadStream(file)) {
      hash.update(chunk);
      size += (chunk as Buffer).length;
    }
    return { digest: hash.digest("hex"), size, error: null };
  } catch {
    return { digest: null, size: null, error: "文件无法读取" };
  }
}
export async function resolveRepo(
  repo: string | null | undefined,
  cwd: string,
): Promise<{ repo: string | null; error: string | null }> {
  if (repo !== null && repo !== undefined)
    return REPO_RE.test(repo)
      ? { repo, error: null }
      : { repo: null, error: "repo 必须采用 owner/repo 格式" };
  const r = await run(
    ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
    cwd,
  );
  const resolved = r.stdout.trim();
  return r.returncode === 0 && REPO_RE.test(resolved)
    ? { repo: resolved, error: null }
    : {
        repo: null,
        error:
          "无法从当前目录确定 GitHub 仓库；请提供 repo=owner/repo 并确认 gh 已授权",
      };
}
export async function ghApi(
  endpoint: string,
  cwd: string,
): Promise<{ value: Record<string, any> | null; error: string | null }> {
  const r = await run(["gh", "api", endpoint], cwd);
  if (r.returncode !== 0)
    return { value: null, error: `gh API 请求失败（退出码 ${r.returncode}）` };
  try {
    const value = JSON.parse(r.stdout);
    return value && typeof value === "object" && !Array.isArray(value)
      ? { value, error: null }
      : { value: null, error: "gh API 返回的数据结构不是对象" };
  } catch {
    return { value: null, error: "gh API 返回了无效 JSON" };
  }
}
export async function ghObject(
  args: string[],
  cwd: string,
): Promise<{ value: any; error: string | null }> {
  const r = await run(args, cwd);
  if (r.returncode !== 0)
    return {
      value: null,
      error: `GitHub CLI operation failed (exit ${r.returncode})`,
    };
  try {
    return { value: JSON.parse(r.stdout), error: null };
  } catch {
    return { value: null, error: "GitHub CLI returned invalid JSON" };
  }
}
export async function ghLogin(
  cwd: string,
): Promise<{ login: string | null; error: string | null }> {
  const r = await run(["gh", "api", "user", "--jq", ".login"], cwd);
  const login = r.stdout.trim();
  return r.returncode === 0 && login
    ? { login, error: null }
    : { login: null, error: "无法解析当前 gh 登录账号；未输出认证信息" };
}
export async function tempBody(
  body: string,
): Promise<{ dir: string; file: string }> {
  const dir = await import("node:fs/promises");
  const folder = await dir.mkdtemp(path.join(os.tmpdir(), "dev-workflow-mcp-"));
  const file = path.join(folder, "body.md");
  await dir.writeFile(file, body, {
    encoding: "utf8",
    mode: 0o600,
    flag: "wx",
  });
  return { dir: folder, file };
}
export async function removeTemp(dir: string): Promise<void> {
  await rm(dir, { recursive: true, force: true });
}
