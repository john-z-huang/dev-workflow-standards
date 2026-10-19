import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/server";
import { createReadStream, createWriteStream } from "node:fs";
import { lstat, mkdir, stat } from "node:fs/promises";
import { pipeline } from "node:stream/promises";
import path from "node:path";
import * as I from "./infra.js";

type Dict = Record<string, unknown>;
type Annotation = {
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  idempotentHint?: boolean;
  openWorldHint?: boolean;
};
const ro: Annotation = { readOnlyHint: true, openWorldHint: false };
const localWrite: Annotation = {
  readOnlyHint: false,
  destructiveHint: false,
  idempotentHint: false,
  openWorldHint: false,
};
const destructive: Annotation = {
  readOnlyHint: false,
  destructiveHint: true,
  idempotentHint: false,
  openWorldHint: false,
};
const idem: Annotation = {
  readOnlyHint: false,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false,
};
const ghRo: Annotation = { readOnlyHint: true, openWorldHint: true };
const ghWrite: Annotation = {
  readOnlyHint: false,
  destructiveHint: false,
  idempotentHint: false,
  openWorldHint: true,
};
const ghDestructive: Annotation = {
  readOnlyHint: false,
  destructiveHint: true,
  idempotentHint: false,
  openWorldHint: true,
};
const ghIdem: Annotation = {
  readOnlyHint: false,
  destructiveHint: true,
  idempotentHint: true,
  openWorldHint: true,
};
// Zod 4 advertises JS safe-integer bounds by default; Python's integer schema is unbounded.
const N = z.number().int().meta({ minimum: undefined, maximum: undefined });
const nullableOptionalString = z.string().nullable().optional();
const manifestEntry = z.object({
  path: z.string().describe("仓库根目录相对 POSIX 路径"),
  sha256: z.string().regex(/^[0-9a-f]{64}$/),
  size: z.number().int().min(0).meta({ maximum: undefined }),
});
const SUBJECT_RE =
  /^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$/;
const CHINESE_RE = /[\u3400-\u9fff]/;
const ATTRIBUTION_RE =
  /(?:generated\s+(?:with|by)|created\s+with|assisted\s+by|authored\s+by|co-?authored-?by)/i;

function asMcpResult(value: Dict) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(value) }],
    structuredContent: value,
  };
}
function tool(
  server: McpServer,
  name: string,
  description: string,
  schema: Record<string, z.ZodType>,
  annotations: Annotation,
  handler: (args: any) => Promise<Dict> | Dict,
) {
  server.registerTool(
    name,
    { description, inputSchema: z.object(schema), annotations },
    async (args: any) => asMcpResult(await handler(args)),
  );
}
const err = (error: string, extra: Dict = {}): Dict => ({
  ok: false,
  error,
  ...extra,
});
const hasTrackedChanges = (text: string) =>
  text.split(/\r?\n/).some((line) => line && !line.startsWith("?? "));
const splitStatus = (text: string) => text.split(/\r?\n/).filter(Boolean);
const refPattern = (n: number) =>
  new RegExp(
    `\\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\\s+#\\s*${n}\\b`,
    "i",
  );

export function registerGitTools(server: McpServer): void {
  tool(
    server,
    "check_branch_names_ts",
    "检查一个或多个分支名；省略 branch_names 时检查当前仓库分支。\n\n只读取 git branch --show-current，不创建、切换、删除分支或安装 Hook。",
    {
      branch_names: z.array(z.string()).nullable().optional(),
      repo_path: nullableOptionalString,
    },
    ro,
    async ({ branch_names, repo_path }) => {
      if (branch_names == null) {
        if (repo_path == null)
          return {
            passed: false,
            checks: [],
            error: "repo_path 绝对路径为必填项，除非提供 branch_names",
          };
        const { result, error } = await I.runRepo(repo_path, [
          "git",
          "branch",
          "--show-current",
        ]);
        if (error) return { passed: false, checks: [], error };
        if (result!.returncode !== 0 || !result!.stdout.trim())
          return {
            passed: false,
            checks: [],
            error: "无法确定当前分支或当前处于 detached HEAD",
          };
        branch_names = [result!.stdout.trim()];
      }
      if (!branch_names.length)
        return {
          passed: false,
          checks: [],
          error: "至少提供一个分支名，或省略以检查当前分支",
        };
      const checks = branch_names.map((branch_name: string) => {
        const errors = I.branchErrors(branch_name);
        return { branch_name, passed: !errors.length, errors };
      });
      return {
        passed: checks.every((x: { passed: boolean }) => x.passed),
        checks,
      };
    },
  );
  tool(
    server,
    "check_commit_message_ts",
    "检查提交信息标题、中文说明和禁止的工具署名；不读取或修改 Git 状态。",
    { message: z.string() },
    ro,
    ({ message }: { message: string }) => {
      const lines = message
        .split(/\r?\n/)
        .filter(
          (line: string) => line.trim() && !line.trimStart().startsWith("#"),
        );
      const subject = lines[0]?.trim() ?? "";
      const errors: string[] = [];
      if (!subject) errors.push("提交主题不能为空");
      else {
        if (!SUBJECT_RE.test(subject))
          errors.push("提交主题必须使用允许的类型前缀和格式：<type>: 中文说明");
        if (!CHINESE_RE.test(subject)) errors.push("提交主题必须包含中文说明");
      }
      const match = lines.join("\n").match(ATTRIBUTION_RE);
      if (match) errors.push(`禁止包含工具署名或生成声明: ${match[0]}`);
      return { passed: !errors.length, subject, errors };
    },
  );
  tool(
    server,
    "check_staged_changes_ts",
    "运行固定的 `git diff --cached --check` 检查暂存区空白错误。\n\n只读 Git 暂存区；不运行测试、用户提供的命令或任何 shell 命令。",
    { repo_path: z.string() },
    ro,
    async ({ repo_path }) => {
      const { result, error } = await I.runRepo(repo_path, [
        "git",
        "diff",
        "--cached",
        "--check",
      ]);
      if (error) return { passed: false, diagnostics: [], error };
      if (result!.returncode === 0) return { passed: true, diagnostics: [] };
      return {
        passed: false,
        diagnostics: splitStatus(result!.stdout),
        error: "git diff --cached --check 执行失败",
        exit_code: result!.returncode,
      };
    },
  );
  tool(
    server,
    "stage_repository_paths_ts",
    "在明确用户授权且 Codex writes approval 后，只将显式列出的普通仓库相对文件路径加入 Git index。允许精确的 tracked deletion；拒绝绝对路径、穿越、symlink、目录、重复路径及已有 staged changes。写入后核验 staged path 集合与请求完全相同；不 stage 清单外内容。",
    { repo_path: z.string(), paths: z.array(z.string()) },
    localWrite,
    stagePaths,
  );
  tool(
    server,
    "commit_repository_changes_ts",
    "在明确用户授权且 Codex writes approval 后提交已暂存内容。要求 staged paths 与 expected_paths 完全相等、提交信息通过既有策略、`git diff --cached --check` 通过。运行固定 `git commit -m <message>`，不使用绕过 Hook 的参数；返回提交 OID、实际消息、提交路径及提交后的工作区状态。",
    {
      repo_path: z.string(),
      message: z.string(),
      expected_paths: z.array(z.string()),
    },
    destructive,
    commitChanges,
  );
}

export function registerRepositoryTools(server: McpServer): void {
  tool(
    server,
    "list_repository_worktrees_ts",
    "只读列出指定仓库的 worktree 路径、HEAD 和分支；不创建或移除 worktree。",
    { repo_path: z.string() },
    ro,
    listWorktrees,
  );
  tool(
    server,
    "switch_repository_branch_ts",
    "在授权后切换指定仓库的本地分支。副作用：改变该 worktree 当前检出的分支；拒绝不安全或不存在的目标。需要 Codex writes approval。",
    { repo_path: z.string(), branch_name: z.string() },
    localWrite,
    switchBranch,
  );
  tool(
    server,
    "pull_origin_branch_fast_forward_ts",
    "在授权后将当前同名本地分支以 `git pull --ff-only origin <branch>` 快进同步。要求跟踪更改干净且当前分支匹配。需要 Codex writes approval。",
    { repo_path: z.string(), branch_name: z.string() },
    localWrite,
    pullOrigin,
  );
  tool(
    server,
    "fetch_upstream_branch_ts",
    "在授权后执行固定的 `git fetch upstream <branch>` 更新 remote-tracking 信息。需要 Codex writes approval；不合并、不推送。",
    { repo_path: z.string(), branch_name: z.string() },
    localWrite,
    fetchUpstream,
  );
  tool(
    server,
    "merge_upstream_branch_fast_forward_ts",
    "在授权后将 upstream/<branch> 以 `git merge --ff-only` 合入当前同名本地分支。副作用：更新本地分支和工作区；不创建 merge commit。需要 Codex writes approval。",
    { repo_path: z.string(), branch_name: z.string() },
    localWrite,
    mergeUpstream,
  );
  tool(
    server,
    "rebase_repository_branch_ts",
    "在明确授权后将当前 branch_name rebase 到已存在的本地 base_branch。要求工作区完全干净且当前分支匹配；副作用：改写当前分支提交历史。若冲突或失败立即停止，不自动 continue/abort/reset。需要 Codex writes approval。",
    { repo_path: z.string(), branch_name: z.string(), base_branch: z.string() },
    destructive,
    rebaseBranch,
  );
  tool(
    server,
    "remove_repository_worktree_ts",
    "仅在用户明确要求移除指定本地 worktree 并授权后执行 `git worktree remove <path>`。要求路径属于同仓库、检出 branch_name、工作区干净；副作用：删除该 worktree 目录。不会删除本地分支或远端分支，也不使用 --force。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      target_worktree_path: z.string(),
      branch_name: z.string(),
    },
    destructive,
    removeWorktree,
  );
  tool(
    server,
    "create_repository_worktree_ts",
    "在授权后执行 `git worktree add <target> -b <branch> <base>`。会新增本地分支和目录；不执行同步、复制未跟踪文件或需求编辑。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      target_worktree_path: z.string(),
      branch_name: z.string(),
      base_branch: z.string(),
    },
    localWrite,
    createWorktree,
  );
  tool(
    server,
    "capture_untracked_file_manifest_ts",
    "只读生成未被忽略的未跟踪普通文件清单，含相对 POSIX 路径、SHA-256 和字节数；不保存文件或搬动内容。拒绝符号链接和特殊文件。",
    { repo_path: z.string() },
    ro,
    captureManifest,
  );
  tool(
    server,
    "copy_untracked_files_to_worktree_ts",
    "在授权后按先前清单复制未跟踪文件到同仓库 worktree。只复制 SHA-256/size 完全匹配的普通文件；拒绝覆盖、路径穿越、symlink 及目标不是同一仓库 worktree。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      target_worktree_path: z.string(),
      manifest: z.array(manifestEntry),
    },
    localWrite,
    copyManifest,
  );
  tool(
    server,
    "configure_project_hooks_path_ts",
    "在授权后固定设置 `git config --local core.hooksPath .githooks`。要求 `.githooks/pre-commit` 和 `commit-msg` 已存在；不复制脚本、不安装远端 Hook。会修改仓库本地 Git 配置。需要 Codex writes approval。",
    { repo_path: z.string() },
    idem,
    configureHooks,
  );
}

export function registerGithubTools(server: McpServer): void {
  tool(
    server,
    "audit_issue_pr_policy_ts",
    "只读审计 GitHub Issue/PR 开放状态、PR base/head 和关闭 Issue 的正文关联。\n\n通过固定的 gh repo view / gh api 只读请求；不创建、修改、关闭或合并 GitHub 资源。",
    {
      repo_path: z.string(),
      repo: nullableOptionalString,
      issue_number: N.nullable().optional(),
      pr_number: N.nullable().optional(),
      expected_base: nullableOptionalString,
      expected_head: nullableOptionalString,
    },
    ghRo,
    auditIssuePolicy,
  );
  tool(
    server,
    "cleanup_merged_pr_local_branch_ts",
    "在明确的人类授权后同步已合并 PR 的 base 并删除本地 head 分支。\n\nInvoke only after explicit user authorization; Codex write-approval must be enabled. The tool verifies a clean worktree and a MERGED PR, switches to the actual base, runs `git pull --ff-only origin <base>`, then uses `git branch -d`. It uses `git branch -D` only if the supplied pre-merge head OID exactly matches the local branch OID. It never deletes a remote branch or merges a PR. Side effects: local branch switch, fast-forward pull, local head branch deletion. The supplied OID must have been recorded before merge.",
    {
      repo_path: z.string(),
      pr_number: N,
      repo: nullableOptionalString,
      branch_name: nullableOptionalString,
      merged_head_oid: nullableOptionalString,
    },
    ghDestructive,
    cleanupMergedPr,
  );
  tool(
    server,
    "audit_repository_state_ts",
    "只读审计指定仓库的根路径、当前分支、工作区状态、remote 名称及 GitHub Fork/default branch 信息。\n\n固定读取：git rev-parse、git status --short --branch、git remote、git branch --show-current、gh repo view --json parent,defaultBranchRef,nameWithOwner。Remote URL 不输出，避免意外泄露嵌入凭据。",
    { repo_path: z.string() },
    ghRo,
    auditRepository,
  );
  tool(
    server,
    "list_github_issue_labels_ts",
    "只读列出指定 GitHub 仓库现有 Issue labels，供 Issue 创建前复用仓库标签。最多读取 gh label list 的 100 个结果。",
    { repo_path: z.string(), repo: nullableOptionalString },
    ghRo,
    listLabels,
  );
  tool(
    server,
    "create_github_issue_ts",
    "在明确授权后于指定仓库创建并核验 Issue。要求 body 完整、至少一个已存在的工作类型 label；默认指派 `@me`。使用安全临时 body-file，不将 Markdown 正文放入命令参数。副作用：创建 GitHub Issue。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      repo: z.string(),
      title: z.string(),
      body: z.string(),
      labels: z.array(z.string()),
    },
    ghWrite,
    createIssue,
  );
  tool(
    server,
    "push_issue_branch_to_origin_ts",
    "在明确推送授权后执行固定的 `git push origin <branch_name>`。要求当前本地分支匹配、工作区干净，且指定 GitHub Issue 开放、带 label 并指派给当前 gh 用户。副作用：向 origin 更新该分支；不强推。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      repo: z.string(),
      branch_name: z.string(),
      issue_number: N,
    },
    ghWrite,
    pushIssueBranch,
  );
  tool(
    server,
    "create_github_pull_request_ts",
    "在明确授权后创建并回读关联 PR。要求显式 repo/base/head/open Issue，body 含 Closes/Fixes/Resolves #N；PR 默认指派 `@me`。使用临时 body-file，不内联 Markdown。副作用：创建开放 PR。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      repo: z.string(),
      title: z.string(),
      body: z.string(),
      base_branch: z.string(),
      head_branch: z.string(),
      issue_number: N,
    },
    ghWrite,
    createPullRequest,
  );
  tool(
    server,
    "merge_github_pull_request_ts",
    "在明确授权合并后运行固定 `gh pr merge <number> --<merge_method>`，先核验 PR OPEN/MERGEABLE 和 required checks 全部通过。base 为 main 时只允许 squash；不使用 --admin、--auto、--delete-branch。副作用：远端合并并关闭 PR。成功执行合并命令后返回合并前的 `pre_merge_head_oid`，供后续本地分支清理核验。需要 Codex writes approval。",
    {
      repo_path: z.string(),
      repo: z.string(),
      pr_number: N,
      merge_method: z.enum(["squash", "merge", "rebase"]),
    },
    ghDestructive,
    mergePullRequest,
  );
  tool(
    server,
    "push_fork_main_fast_forward_ts",
    "在明确授权后仅将已确认 Fork 的本地 main 快进推送为 origin/main。要求 GitHub parent 非空、upstream/main 是本地 main 的祖先、当前检出 main 且工作区完全干净。副作用：更新个人 Fork 的 origin/main；不强推。需要 Codex writes approval。",
    { repo_path: z.string(), repo: z.string() },
    ghIdem,
    pushForkMain,
  );
}

async function auditIssuePolicy({
  repo_path,
  repo,
  issue_number,
  pr_number,
  expected_base,
  expected_head,
}: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { passed: false, errors: [error] };
  if (issue_number != null && issue_number <= 0)
    return { passed: false, errors: ["issue_number 必须为正数"] };
  if (pr_number != null && pr_number <= 0)
    return { passed: false, errors: ["pr_number 必须为正数"] };
  if (issue_number == null && pr_number == null)
    return {
      passed: false,
      errors: ["至少提供正数 issue_number 或 pr_number"],
    };
  if (expected_base != null && pr_number == null)
    return {
      passed: false,
      errors: ["expected_base 需要与 pr_number 一起使用"],
    };
  if (expected_head != null && pr_number == null)
    return {
      passed: false,
      errors: ["expected_head 需要与 pr_number 一起使用"],
    };
  const resolved = await I.resolveRepo(repo, root!);
  if (resolved.error) return { passed: false, errors: [resolved.error] };
  const errors: string[] = [];
  if (issue_number != null) {
    const x = await I.ghApi(
      `repos/${resolved.repo}/issues/${issue_number}`,
      root!,
    );
    if (x.error)
      return { passed: false, repo: resolved.repo, errors: [x.error] };
    if (x.value!.state !== "open")
      errors.push(
        `Issue #${issue_number}: Issue 当前不是开放状态: ${x.value!.state ?? "未知"}`,
      );
  }
  if (pr_number != null) {
    const x = await I.ghApi(`repos/${resolved.repo}/pulls/${pr_number}`, root!);
    if (x.error)
      return { passed: false, repo: resolved.repo, errors: [x.error] };
    const pr = x.value!;
    if (pr.state !== "open")
      errors.push(
        `PR #${pr_number}: PR 当前不是开放状态: ${pr.state ?? "未知"}`,
      );
    const base = pr.base?.ref,
      head = pr.head?.ref;
    if (expected_base != null && base !== expected_base)
      errors.push(
        `PR #${pr_number}: base 实际为 ${JSON.stringify(base)}，预期为 ${JSON.stringify(expected_base)}`,
      );
    if (expected_head != null && head !== expected_head)
      errors.push(
        `PR #${pr_number}: head 实际为 ${JSON.stringify(head)}，预期为 ${JSON.stringify(expected_head)}`,
      );
    if (issue_number != null && !refPattern(issue_number).test(pr.body ?? ""))
      errors.push(
        `PR #${pr_number}: 描述未关联 Closes/Fixes/Resolves #${issue_number}`,
      );
  }
  return { passed: !errors.length, repo: resolved.repo, errors };
}
async function cleanupMergedPr({
  repo_path,
  pr_number,
  repo,
  branch_name,
  merged_head_oid,
}: any): Promise<Dict> {
  if (pr_number <= 0)
    return { completed: false, actions: [], error: "pr_number 必须为正数" };
  if (merged_head_oid != null && !I.OID_RE.test(merged_head_oid))
    return { completed: false, actions: [], error: "merged_head_oid 格式无效" };
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { completed: false, actions: [], error };
  const clean = await I.requireClean(root!);
  if (clean) return { completed: false, actions: [], error: clean };
  if (repo != null && !I.REPO_RE.test(repo))
    return {
      completed: false,
      actions: [],
      error: "repo 必须采用 owner/repo 格式",
    };
  const args = ["gh", "pr", "view", String(pr_number)];
  if (repo) args.push("--repo", repo);
  args.push("--json", "state,mergedAt,baseRefName,headRefName,title");
  const r = await I.run(args, root!);
  if (r.returncode !== 0)
    return {
      completed: false,
      actions: [],
      error: `gh pr view 失败（退出码 ${r.returncode}）`,
    };
  let info: any;
  try {
    info = JSON.parse(r.stdout);
  } catch {
    return { completed: false, actions: [], error: "gh 返回了无效的 PR JSON" };
  }
  if (!info || typeof info !== "object" || Array.isArray(info))
    return {
      completed: false,
      actions: [],
      error: "gh 返回的 PR 数据不是对象",
    };
  if (info.state !== "MERGED")
    return {
      completed: false,
      actions: [],
      error: `PR 尚未合并（状态: ${info.state ?? "未知"}）`,
    };
  const base = info.baseRefName,
    head = info.headRefName,
    target = branch_name || head;
  if (!base || !head)
    return {
      completed: false,
      actions: [],
      error: "PR 缺少 base/head 分支信息",
    };
  if (branch_name != null && branch_name !== head)
    return {
      completed: false,
      actions: [],
      error: "指定 branch_name 与 PR head 不一致",
    };
  if (target === base)
    return {
      completed: false,
      actions: [],
      error: "PR head 不能与 base 分支相同",
    };
  const ref = await I.run(
    ["git", "check-ref-format", "--branch", target],
    root!,
  );
  if (ref.returncode !== 0)
    return {
      completed: false,
      actions: [],
      error: "PR head 不是有效的本地分支名",
    };
  const actions: string[] = [];
  let sw = await I.run(["git", "switch", "--", base], root!);
  if (sw.returncode !== 0)
    sw = await I.run(["git", "switch", "--track", `origin/${base}`], root!);
  if (sw.returncode !== 0)
    return { completed: false, actions, error: "无法切换到 PR base 分支" };
  actions.push(`switched to ${base}`);
  const pull = await I.run(["git", "pull", "--ff-only", "origin", base], root!);
  if (pull.returncode !== 0)
    return {
      completed: false,
      actions,
      error: "git pull --ff-only 同步 base 失败",
    };
  actions.push(`fast-forwarded origin/${base}`);
  const cleanAgain = await I.requireClean(root!);
  if (cleanAgain) return { completed: false, actions, error: cleanAgain };
  const current = await I.run(["git", "branch", "--show-current"], root!);
  if (current.returncode !== 0 || current.stdout.trim() === target)
    return {
      completed: false,
      actions,
      error: "当前仍处于待删除分支，或无法确定当前分支",
    };
  let deleted = await I.run(["git", "branch", "-d", "--", target], root!);
  if (deleted.returncode === 0) {
    actions.push(`deleted local branch ${target} with -d`);
    return { completed: true, repo, pr_number, actions };
  }
  if (merged_head_oid == null)
    return {
      completed: false,
      actions,
      error:
        "普通删除失败；若为 squash merge，需提供合并前记录的 PR head SHA 后重试",
    };
  const oid = await I.run(
    ["git", "rev-parse", "--verify", `refs/heads/${target}`],
    root!,
  );
  if (
    oid.returncode !== 0 ||
    oid.stdout.trim().toLowerCase() !== merged_head_oid.toLowerCase()
  )
    return {
      completed: false,
      actions,
      error: "本地 head SHA 与合并前记录值不一致，拒绝强制删除",
    };
  deleted = await I.run(["git", "branch", "-D", "--", target], root!);
  if (deleted.returncode !== 0)
    return { completed: false, actions, error: "核验后强制删除本地分支失败" };
  actions.push(
    `deleted local branch ${target} with -D after exact OID verification`,
  );
  return { completed: true, repo, pr_number, actions };
}
async function auditRepository({
  repo_path,
}: {
  repo_path: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, error };
  const [status, remotes, branch, gh] = await Promise.all([
    I.run(
      ["git", "status", "--short", "--branch", "--untracked-files=all"],
      root!,
    ),
    I.run(["git", "remote"], root!),
    I.currentBranch(root!),
    I.run(
      ["gh", "repo", "view", "--json", "nameWithOwner,parent,defaultBranchRef"],
      root!,
    ),
  ]);
  let github: Dict | null = null,
    github_error: string | null = null;
  if (gh.returncode === 0) {
    try {
      const value = JSON.parse(gh.stdout);
      github =
        value && typeof value === "object" && !Array.isArray(value)
          ? value
          : null;
    } catch {
      github_error = "gh repo view returned invalid JSON";
    }
  } else
    github_error = `gh repo view unavailable or failed (exit ${gh.returncode})`;
  return {
    ok: status.returncode === 0 && remotes.returncode === 0,
    repo_path: root,
    current_branch: branch,
    status_lines: status.returncode === 0 ? splitStatus(status.stdout) : [],
    remotes: remotes.returncode === 0 ? splitStatus(remotes.stdout) : [],
    github,
    github_error,
    errors: [
      ...(status.returncode === 0 ? [] : ["git status failed"]),
      ...(remotes.returncode === 0 ? [] : ["git remote failed"]),
    ],
  };
}
async function listLabels({ repo_path, repo }: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, labels: [], error };
  const resolved = await I.resolveRepo(repo, root!);
  if (resolved.error) return { ok: false, labels: [], error: resolved.error };
  const r = await I.run(
    [
      "gh",
      "label",
      "list",
      "--repo",
      resolved.repo!,
      "--limit",
      "100",
      "--json",
      "name,description,color",
    ],
    root!,
  );
  if (r.returncode !== 0)
    return {
      ok: false,
      repo: resolved.repo,
      labels: [],
      error: `gh label list failed (exit ${r.returncode})`,
    };
  let labels: any;
  try {
    labels = JSON.parse(r.stdout);
  } catch {
    return {
      ok: false,
      repo: resolved.repo,
      labels: [],
      error: "gh label list returned invalid JSON",
    };
  }
  if (!Array.isArray(labels))
    return {
      ok: false,
      repo: resolved.repo,
      labels: [],
      error: "gh label list returned a non-list",
    };
  return { ok: true, repo: resolved.repo, labels, limit: 100 };
}
async function createIssue({
  repo_path,
  repo,
  title,
  body,
  labels,
}: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, created: false, error };
  if (!I.REPO_RE.test(repo))
    return { ok: false, created: false, error: "repo 必须为 owner/repo" };
  if (
    !title.trim() ||
    !body.trim() ||
    !labels.length ||
    labels.some((x: string) => !x.trim())
  )
    return {
      ok: false,
      created: false,
      error: "title/body 和至少一个非空 label 均为必填",
    };
  const lr = await I.run(
    ["gh", "label", "list", "--repo", repo, "--limit", "100", "--json", "name"],
    root!,
  );
  if (lr.returncode !== 0)
    return {
      ok: false,
      created: false,
      error: "无法读取仓库 labels；为避免猜标签而停止",
    };
  let available: Set<string>;
  try {
    available = new Set(
      JSON.parse(lr.stdout)
        .filter(
          (x: any) => x && typeof x === "object" && typeof x.name === "string",
        )
        .map((x: any) => x.name),
    );
  } catch {
    return { ok: false, created: false, error: "仓库 labels 响应无效" };
  }
  const missing = labels.filter((x: string) => !available.has(x));
  if (missing.length)
    return {
      ok: false,
      created: false,
      error: `指定 label 不存在或不在前 100 项中: ${JSON.stringify(missing)}`,
    };
  const who = await I.ghLogin(root!);
  if (who.error) return { ok: false, created: false, error: who.error };
  let temp: { dir: string; file: string };
  try {
    temp = await I.tempBody(body);
  } catch {
    return {
      ok: false,
      created: false,
      error: "无法创建安全的 GitHub 正文临时文件",
    };
  }
  let created: any;
  try {
    const args = [
      "gh",
      "issue",
      "create",
      "--repo",
      repo,
      "--title",
      title,
      "--body-file",
      temp.file,
      "--assignee",
      "@me",
    ];
    for (const label of labels) args.push("--label", label);
    const r = await I.run(args, root!);
    if (r.returncode !== 0)
      return {
        ok: false,
        created: false,
        error: `gh issue create failed (exit ${r.returncode})`,
      };
    created = r;
  } finally {
    await I.removeTemp(temp.dir);
  }
  const match = created.stdout.trim().match(/\/issues\/(\d+)\s*$/);
  if (!match)
    return {
      ok: false,
      created: true,
      error:
        "Issue 创建命令返回成功，但无法解析 Issue URL；请人工回读，不要重复创建",
    };
  const number = Number(match[1]);
  const details = await I.ghObject(
    [
      "gh",
      "issue",
      "view",
      String(number),
      "--repo",
      repo,
      "--json",
      "number,title,state,labels,assignees",
    ],
    root!,
  );
  if (details.error)
    return {
      ok: false,
      created: true,
      issue_number: number,
      error: details.error,
    };
  const value = details.value;
  const labelNames = new Set(
    (value.labels ?? [])
      .filter((x: any) => x && typeof x === "object")
      .map((x: any) => x.name),
  );
  const assignees = new Set(
    (value.assignees ?? [])
      .filter((x: any) => x && typeof x === "object")
      .map((x: any) => x.login),
  );
  const verified =
    value.state === "OPEN" &&
    labels.every((x: string) => labelNames.has(x)) &&
    assignees.has(who.login);
  return {
    ok: verified,
    created: true,
    repo,
    issue: value,
    error: verified
      ? null
      : "Issue 已创建，但开放状态、labels 或 @me assignee 回读校验失败",
  };
}
async function pushIssueBranch({
  repo_path,
  repo,
  branch_name,
  issue_number,
}: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (
    !I.REPO_RE.test(repo) ||
    issue_number <= 0 ||
    !I.validRemoteBranch(branch_name)
  )
    return err("repo/issue_number/branch_name 参数无效");
  if (
    ["main", "master"].includes(branch_name) ||
    (await I.currentBranch(root!)) !== branch_name
  )
    return err("只允许推送当前检出的非主分支");
  const status = await I.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    root!,
  );
  if (status.returncode !== 0 || status.stdout.trim())
    return err("工作区必须完全干净才能推送");
  const issue = await I.ghObject(
    [
      "gh",
      "issue",
      "view",
      String(issue_number),
      "--repo",
      repo,
      "--json",
      "number,state,labels,assignees",
    ],
    root!,
  );
  if (issue.error) return err(issue.error);
  const who = await I.ghLogin(root!);
  if (who.error) return err(who.error);
  const value = issue.value;
  if (
    value.state !== "OPEN" ||
    !(value.labels ?? []).length ||
    !(value.assignees ?? []).some((x: any) => x?.login === who.login)
  )
    return err("Issue 必须开放、具备至少一个 label 并指派给当前 gh 用户");
  const r = await I.run(["git", "push", "origin", branch_name], root!);
  return {
    ok: r.returncode === 0,
    repo_path: root,
    repo,
    branch_name,
    issue_number,
    error:
      r.returncode === 0
        ? null
        : "git push origin failed; no force push was attempted",
  };
}
async function createPullRequest({
  repo_path,
  repo,
  title,
  body,
  base_branch,
  head_branch,
  issue_number,
}: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, created: false, error };
  if (
    !I.REPO_RE.test(repo) ||
    issue_number <= 0 ||
    !title.trim() ||
    !body.trim()
  )
    return {
      ok: false,
      created: false,
      error: "repo/title/body/issue_number 参数无效",
    };
  if (
    !I.validRemoteBranch(base_branch) ||
    !I.validRemoteBranch(head_branch) ||
    base_branch === head_branch
  )
    return {
      ok: false,
      created: false,
      error: "base_branch/head_branch 无效或相同",
    };
  const ref = refPattern(issue_number);
  if (!ref.test(body))
    return {
      ok: false,
      created: false,
      error: `PR body 必须包含 Closes/Fixes/Resolves #${issue_number}`,
    };
  const issue = await I.ghObject(
    [
      "gh",
      "issue",
      "view",
      String(issue_number),
      "--repo",
      repo,
      "--json",
      "number,state",
    ],
    root!,
  );
  if (issue.error || issue.value?.state !== "OPEN")
    return {
      ok: false,
      created: false,
      error: issue.error ?? "Issue 必须处于 OPEN 状态",
    };
  const exists = await I.run(
    ["git", "show-ref", "--verify", `refs/heads/${head_branch}`],
    root!,
  );
  if (exists.returncode !== 0)
    return {
      ok: false,
      created: false,
      error: "本地 head_branch 不存在；先完成本地验证和推送",
    };
  const who = await I.ghLogin(root!);
  if (who.error) return { ok: false, created: false, error: who.error };
  let temp: { dir: string; file: string };
  try {
    temp = await I.tempBody(body);
  } catch {
    return {
      ok: false,
      created: false,
      error: "无法创建安全的 GitHub 正文临时文件",
    };
  }
  let created: any;
  try {
    const r = await I.run(
      [
        "gh",
        "pr",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body-file",
        temp.file,
        "--base",
        base_branch,
        "--head",
        head_branch,
        "--assignee",
        "@me",
      ],
      root!,
    );
    if (r.returncode !== 0)
      return {
        ok: false,
        created: false,
        error: `gh pr create failed (exit ${r.returncode})`,
      };
    created = r;
  } finally {
    await I.removeTemp(temp.dir);
  }
  const match = created.stdout.trim().match(/\/pull\/(\d+)\s*$/);
  if (!match)
    return {
      ok: false,
      created: true,
      error: "PR 创建命令返回成功，但无法解析 PR URL；请人工回读，不要重复创建",
    };
  const number = Number(match[1]);
  const details = await I.ghObject(
    [
      "gh",
      "pr",
      "view",
      String(number),
      "--repo",
      repo,
      "--json",
      "number,title,state,baseRefName,headRefName,body,assignees",
    ],
    root!,
  );
  if (details.error)
    return {
      ok: false,
      created: true,
      pr_number: number,
      error: details.error,
    };
  const value = details.value,
    assignees = new Set(
      (value.assignees ?? [])
        .filter((x: any) => x && typeof x === "object")
        .map((x: any) => x.login),
    );
  const verified =
    value.state === "OPEN" &&
    value.baseRefName === base_branch &&
    value.headRefName === head_branch &&
    assignees.has(who.login) &&
    ref.test(value.body ?? "");
  return {
    ok: verified,
    created: true,
    repo,
    pull_request: value,
    error: verified
      ? null
      : "PR 已创建，但 state/base/head/Issue 关联/assignee 回读校验失败",
  };
}
async function mergePullRequest({
  repo_path,
  repo,
  pr_number,
  merge_method,
}: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (!I.REPO_RE.test(repo) || pr_number <= 0)
    return err("repo/pr_number 参数无效");
  const pr = await I.ghObject(
    [
      "gh",
      "pr",
      "view",
      String(pr_number),
      "--repo",
      repo,
      "--json",
      "number,state,baseRefName,headRefName,mergeable,reviewDecision,headRefOid",
    ],
    root!,
  );
  if (pr.error) return err(pr.error);
  const p = pr.value;
  if (p.state !== "OPEN" || p.mergeable !== "MERGEABLE")
    return err("PR 必须为 OPEN 且 mergeable=MERGEABLE");
  if (p.baseRefName === "main" && merge_method !== "squash")
    return err("目标 base 为 main，按策略只能 squash merge");
  if (p.reviewDecision === "CHANGES_REQUESTED")
    return err("PR 有 changes requested review");
  const checks = await I.ghObject(
    [
      "gh",
      "pr",
      "checks",
      String(pr_number),
      "--repo",
      repo,
      "--required",
      "--json",
      "name,bucket",
    ],
    root!,
  );
  if (checks.error) return err(checks.error);
  if (
    !Array.isArray(checks.value) ||
    checks.value.some(
      (x: any) => x && typeof x === "object" && x.bucket !== "pass",
    )
  )
    return {
      ok: false,
      error: "required checks 未全部通过或响应格式无效",
      checks: checks.value,
    };
  if (checks.value.some((x: any) => !x || typeof x !== "object"))
    return {
      ok: false,
      error: "required checks 响应格式无效",
      checks: checks.value,
    };
  const merged = await I.run(
    [
      "gh",
      "pr",
      "merge",
      String(pr_number),
      `--${merge_method}`,
      "--repo",
      repo,
    ],
    root!,
  );
  if (merged.returncode !== 0)
    return err(
      `gh pr merge failed (exit ${merged.returncode}); no admin/auto fallback was attempted`,
    );
  const final = await I.ghObject(
    [
      "gh",
      "pr",
      "view",
      String(pr_number),
      "--repo",
      repo,
      "--json",
      "number,state,mergedAt,baseRefName,headRefName,mergeCommit",
    ],
    root!,
  );
  const value = final.value ?? {};
  const verified =
    !final.error &&
    value.state === "MERGED" &&
    value.baseRefName === p.baseRefName;
  return {
    ok: verified,
    merged: verified,
    repo,
    pull_request: value,
    pre_merge_head_oid: p.headRefOid,
    error:
      final.error ??
      (verified
        ? null
        : "merge command succeeded but PR merged state/base could not be verified"),
  };
}
async function pushForkMain({ repo_path, repo }: any): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (!I.REPO_RE.test(repo)) return err("repo 必须为 owner/repo");
  const fork = await I.ghObject(
    ["gh", "repo", "view", repo, "--json", "parent,defaultBranchRef"],
    root!,
  );
  if (fork.error || !fork.value?.parent)
    return err(fork.error ?? "目标不是 GitHub Fork");
  if (
    fork.value.defaultBranchRef?.name !== "main" ||
    (await I.currentBranch(root!)) !== "main"
  )
    return err("只支持默认分支为 main 且当前检出 main 的 Fork 镜像同步");
  const status = await I.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    root!,
  );
  if (status.returncode !== 0 || status.stdout.trim())
    return err("main 工作区必须完全干净");
  const remotes = await I.run(["git", "remote"], root!);
  if (
    remotes.returncode !== 0 ||
    !["upstream", "origin"].every((x) =>
      remotes.stdout.split(/\r?\n/).includes(x),
    )
  )
    return err("必须预先配置 upstream 和 origin remotes");
  const ancestor = await I.run(
    ["git", "merge-base", "--is-ancestor", "upstream/main", "main"],
    root!,
  );
  if (ancestor.returncode !== 0)
    return err("upstream/main 尚未快进合入本地 main");
  const pushed = await I.run(["git", "push", "origin", "main"], root!);
  return {
    ok: pushed.returncode === 0,
    repo_path: root,
    repo,
    branch: "main",
    error: pushed.returncode === 0 ? null : "git push origin main 失败；未强推",
  };
}

export function createServer(): McpServer {
  const server = new McpServer(
    { name: "dev-workflow-standards-mcp-ts", version: "0.1.0" },
    {
      instructions:
        "Tools act on the explicitly supplied repo_path and run only fixed, domain-specific Git/GitHub operations. Check applicable user authorization before every write and rely on Codex writes approval. If an operation is not covered, do not substitute a generic command runner.",
    },
  );
  registerGitTools(server);
  registerRepositoryTools(server);
  registerGithubTools(server);
  return server;
}

async function listWorktrees({
  repo_path,
}: {
  repo_path: string;
}): Promise<Dict> {
  const { result, root, error } = await I.runRepo(repo_path, [
    "git",
    "worktree",
    "list",
    "--porcelain",
  ]);
  if (error) return { ok: false, worktrees: [], error };
  const entries: Dict[] = [];
  let cur: Dict = {};
  for (const line of [...result!.stdout.split(/\r?\n/), ""]) {
    if (!line) {
      if (Object.keys(cur).length) {
        entries.push(cur);
        cur = {};
      }
      continue;
    }
    const i = line.indexOf(" "),
      key = i < 0 ? line : line.slice(0, i),
      value = i < 0 ? "" : line.slice(i + 1);
    if (key === "worktree") cur.path = value;
    else if (key === "HEAD") cur.head = value;
    else if (key === "branch") cur.branch = value.replace(/^refs\/heads\//, "");
    else if (key === "detached" || key === "locked") cur[key] = true;
  }
  return {
    ok: result!.returncode === 0,
    repo_path: root,
    worktrees: entries,
    error: result!.returncode === 0 ? null : "git worktree list failed",
  };
}
async function switchBranch({
  repo_path,
  branch_name,
}: {
  repo_path: string;
  branch_name: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  const invalid = await I.validLocalBranch(root!, branch_name);
  if (invalid) return err(invalid);
  const exists = await I.run(
    ["git", "show-ref", "--verify", `refs/heads/${branch_name}`],
    root!,
  );
  if (exists.returncode !== 0)
    return err("本地目标分支不存在；不自动创建或追踪 remote 分支");
  const status = await I.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    root!,
  );
  if (status.returncode !== 0 || hasTrackedChanges(status.stdout))
    return err("存在已跟踪的暂存或未暂存更改，切换已拒绝");
  const r = await I.run(["git", "switch", "--", branch_name], root!);
  return {
    ok: r.returncode === 0,
    repo_path: root,
    branch_name,
    error:
      r.returncode === 0
        ? null
        : "git switch failed; existing user data was not intentionally discarded",
  };
}
async function pullOrigin({
  repo_path,
  branch_name,
}: {
  repo_path: string;
  branch_name: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (!I.validRemoteBranch(branch_name)) return err("branch_name 格式无效");
  if ((await I.currentBranch(root!)) !== branch_name)
    return err("当前分支必须与 branch_name 完全一致");
  const status = await I.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    root!,
  );
  if (status.returncode !== 0 || hasTrackedChanges(status.stdout))
    return err("存在已跟踪的暂存或未暂存更改，pull 已拒绝");
  const r = await I.run(
    ["git", "pull", "--ff-only", "origin", branch_name],
    root!,
  );
  return {
    ok: r.returncode === 0,
    repo_path: root,
    branch_name,
    error:
      r.returncode === 0
        ? null
        : "git pull --ff-only 失败；未执行非快进替代操作",
  };
}
async function fetchUpstream({
  repo_path,
  branch_name,
}: {
  repo_path: string;
  branch_name: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (!I.validRemoteBranch(branch_name)) return err("branch_name 格式无效");
  const rem = await I.run(["git", "remote"], root!);
  if (rem.returncode !== 0 || !rem.stdout.split(/\r?\n/).includes("upstream"))
    return err("未配置 upstream remote；不自动添加 remote");
  const r = await I.run(["git", "fetch", "upstream", branch_name], root!);
  return {
    ok: r.returncode === 0,
    repo_path: root,
    remote: "upstream",
    branch_name,
    error: r.returncode === 0 ? null : "git fetch upstream 失败",
  };
}
async function mergeUpstream({
  repo_path,
  branch_name,
}: {
  repo_path: string;
  branch_name: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (!I.validRemoteBranch(branch_name)) return err("branch_name 格式无效");
  if ((await I.currentBranch(root!)) !== branch_name)
    return err("当前分支必须与 branch_name 完全一致");
  const status = await I.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    root!,
  );
  if (status.returncode !== 0 || status.stdout.trim())
    return err("工作区必须完全干净才能合并 upstream");
  const rem = await I.run(["git", "remote"], root!);
  if (rem.returncode !== 0 || !rem.stdout.split(/\r?\n/).includes("upstream"))
    return err("未配置 upstream remote；不自动添加 remote");
  const ref = await I.run(
    ["git", "show-ref", "--verify", `refs/remotes/upstream/${branch_name}`],
    root!,
  );
  if (ref.returncode !== 0) return err("upstream ref 不存在；请先单独 fetch");
  const r = await I.run(
    ["git", "merge", "--ff-only", `upstream/${branch_name}`],
    root!,
  );
  return {
    ok: r.returncode === 0,
    repo_path: root,
    branch_name,
    error: r.returncode === 0 ? null : "git merge --ff-only 失败；保留现场",
  };
}
async function rebaseBranch({
  repo_path,
  branch_name,
  base_branch,
}: {
  repo_path: string;
  branch_name: string;
  base_branch: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  for (const name of [branch_name, base_branch]) {
    const e = await I.validLocalBranch(root!, name);
    if (e) return err(e);
  }
  if (
    branch_name === base_branch ||
    (await I.currentBranch(root!)) !== branch_name
  )
    return err("当前分支必须等于 branch_name，且不能 rebase 到自身");
  for (const name of [branch_name, base_branch]) {
    const exists = await I.run(
      ["git", "show-ref", "--verify", `refs/heads/${name}`],
      root!,
    );
    if (exists.returncode !== 0) return err(`本地分支不存在: ${name}`);
  }
  const clean = await I.requireClean(root!);
  if (clean) return err(clean);
  const r = await I.run(["git", "rebase", base_branch], root!);
  return {
    ok: r.returncode === 0,
    repo_path: root,
    branch_name,
    base_branch,
    error:
      r.returncode === 0
        ? null
        : "git rebase 失败或产生冲突；未执行后续恢复命令",
  };
}
async function removeWorktree({
  repo_path,
  target_worktree_path,
  branch_name,
}: {
  repo_path: string;
  target_worktree_path: string;
  branch_name: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  target_worktree_path = I.expandUser(target_worktree_path);
  if (
    !path.isAbsolute(target_worktree_path) ||
    target_worktree_path.split(path.sep).includes("..")
  )
    return err("target_worktree_path 必须是绝对路径且不含 '..'");
  let target: string;
  try {
    target = await (
      await import("node:fs/promises")
    ).realpath(target_worktree_path);
  } catch {
    return err("目标 worktree 不存在或无法解析");
  }
  if (target === root) return err("拒绝移除 repo_path 本身");
  const tr = await I.validRepo(target);
  if (tr.error || !(await I.sameGitCommonDir(root!, tr.root!)))
    return err(tr.error ?? "目标不是同一 Git 仓库的 worktree");
  if ((await I.currentBranch(tr.root!)) !== branch_name)
    return err("目标当前分支与 branch_name 不符");
  const clean = await I.requireClean(tr.root!);
  if (clean) return err(clean);
  const r = await I.run(["git", "worktree", "remove", target], root!);
  return {
    ok: r.returncode === 0,
    repo_path: root,
    target_worktree_path: target,
    branch_name,
    error:
      r.returncode === 0 ? null : "git worktree remove 失败；未使用 --force",
  };
}
async function createWorktree({
  repo_path,
  target_worktree_path,
  branch_name,
  base_branch,
}: {
  repo_path: string;
  target_worktree_path: string;
  branch_name: string;
  base_branch: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  if (
    ["main", "master"].includes(branch_name) ||
    I.branchErrors(branch_name).length
  )
    return err("branch_name 未通过项目分支策略");
  let e = await I.validLocalBranch(root!, branch_name);
  if (e) return err(e);
  e = await I.validLocalBranch(root!, base_branch);
  if (e) return err(`base_branch 无效: ${e}`);
  const [base, branch] = await Promise.all([
    I.run(["git", "show-ref", "--verify", `refs/heads/${base_branch}`], root!),
    I.run(["git", "show-ref", "--verify", `refs/heads/${branch_name}`], root!),
  ]);
  if (base.returncode !== 0) return err("base_branch 必须是已核验的本地分支");
  if (branch.returncode === 0)
    return err("branch_name 已存在；不复用未核实的旧基点");
  const resolved = await I.absoluteNewPath(target_worktree_path);
  if (resolved.error) return err(resolved.error);
  const target = resolved.target!;
  try {
    await lstat(target);
    return err("target_worktree_path 已存在，拒绝复用或覆盖");
  } catch {}
  if (target === root || target.startsWith(root! + path.sep))
    return err("worktree 目标不能位于源仓库目录内");
  const w = await I.run(["git", "worktree", "list", "--porcelain"], root!);
  if (w.returncode !== 0) return err("无法核验当前 worktree 拓扑");
  if (w.stdout.split(/\r?\n/).includes(`branch refs/heads/${branch_name}`))
    return err("该分支已被其他 worktree 检出");
  const r = await I.run(
    ["git", "worktree", "add", target, "-b", branch_name, base_branch],
    root!,
  );
  return {
    ok: r.returncode === 0,
    repo_path: root,
    target_worktree_path: target,
    branch_name,
    base_branch,
    error:
      r.returncode === 0
        ? null
        : "git worktree add 失败；不删除或回滚用户已有路径",
  };
}
async function captureManifest({
  repo_path,
}: {
  repo_path: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, entries: [], error };
  const r = await I.run(
    ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
    root!,
  );
  if (r.returncode !== 0)
    return { ok: false, entries: [], error: "git status failed" };
  const entries: Dict[] = [],
    unsupported: string[] = [];
  for (const record of r.stdout.split("\0")) {
    if (!record.startsWith("?? ")) continue;
    const rel = I.safeRelative(record.slice(3));
    if (!rel) {
      unsupported.push(record.slice(3));
      continue;
    }
    const file = path.join(root!, ...rel.split("/"));
    try {
      const s = await lstat(file);
      if (!s.isFile() || s.isSymbolicLink()) {
        unsupported.push(rel);
        continue;
      }
    } catch {
      unsupported.push(rel);
      continue;
    }
    const h = await I.sha256(file);
    if (h.error) unsupported.push(rel);
    else entries.push({ path: rel, sha256: h.digest, size: h.size });
  }
  return {
    ok: unsupported.length === 0,
    repo_path: root,
    entries,
    unsupported_paths: unsupported,
    note: "Git status excludes ignored files; ignored files are not included.",
  };
}
async function copyManifest({
  repo_path,
  target_worktree_path,
  manifest,
}: {
  repo_path: string;
  target_worktree_path: string;
  manifest: Array<{ path: string; sha256: string; size: number }>;
}): Promise<Dict> {
  const { root: source, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, copied: [], error };
  target_worktree_path = I.expandUser(target_worktree_path);
  if (
    !path.isAbsolute(target_worktree_path) ||
    target_worktree_path.split(path.sep).includes("..")
  )
    return {
      ok: false,
      copied: [],
      error: "target_worktree_path 必须为绝对路径且不能包含 '..'",
    };
  let target: string;
  try {
    target = await (
      await import("node:fs/promises")
    ).realpath(target_worktree_path);
  } catch {
    return { ok: false, copied: [], error: "目标 worktree 不存在或无法解析" };
  }
  const tr = await I.validRepo(target);
  if (tr.error || !(await I.sameGitCommonDir(source!, tr.root!)))
    return {
      ok: false,
      copied: [],
      error: tr.error ?? "目标不属于同一 Git 仓库的 worktree",
    };
  if (!manifest.length)
    return { ok: false, copied: [], error: "manifest 不能为空" };
  const seen = new Set<string>(),
    validated: Array<{
      rel: string;
      src: string;
      entry: { path: string; sha256: string; size: number };
    }> = [];
  for (const entry of manifest) {
    const rel = I.safeRelative(entry.path);
    if (!rel || seen.has(entry.path))
      return {
        ok: false,
        copied: [],
        error: `manifest 路径无效或重复: ${JSON.stringify(entry.path)}`,
      };
    seen.add(entry.path);
    const src = path.join(source!, ...rel.split("/"));
    let cursor = source!;
    for (const part of rel.split("/").slice(0, -1)) {
      cursor = path.join(cursor, part);
      try {
        if ((await lstat(cursor)).isSymbolicLink())
          return {
            ok: false,
            copied: [],
            error: `源路径包含 symlink 目录: ${entry.path}`,
          };
      } catch {}
    }
    try {
      const s = await lstat(src);
      if (s.isSymbolicLink() || !s.isFile())
        return {
          ok: false,
          copied: [],
          error: `源文件已不存在、不是普通文件或为 symlink: ${entry.path}`,
        };
    } catch {
      return {
        ok: false,
        copied: [],
        error: `源文件已不存在、不是普通文件或为 symlink: ${entry.path}`,
      };
    }
    const h = await I.sha256(src);
    if (h.error || h.digest !== entry.sha256 || h.size !== entry.size)
      return {
        ok: false,
        copied: [],
        error: `源文件指纹与清单不一致: ${entry.path}`,
      };
    const ignored = await I.run(
      ["git", "check-ignore", "--no-index", "--quiet", "--", entry.path],
      source!,
    );
    if (ignored.returncode === 0)
      return {
        ok: false,
        copied: [],
        error: `路径现在被忽略，拒绝复制: ${entry.path}`,
      };
    const tracked = await I.run(
      ["git", "ls-files", "--error-unmatch", "--", entry.path],
      source!,
    );
    if (tracked.returncode === 0)
      return {
        ok: false,
        copied: [],
        error: `路径已跟踪，拒绝复制: ${entry.path}`,
      };
    const current = await I.run(
      [
        "git",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        entry.path,
      ],
      source!,
    );
    if (
      current.returncode !== 0 ||
      current.stdout.split("\0")[0] !== `?? ${entry.path}`
    )
      return {
        ok: false,
        copied: [],
        error: `路径当前不是 Git 未跟踪文件: ${entry.path}`,
      };
    validated.push({ rel, src, entry });
  }
  const copied: string[] = [];
  for (const { rel, src, entry } of validated) {
    const dest = path.join(target, ...rel.split("/"));
    try {
      let cursor = target;
      for (const part of rel.split("/").slice(0, -1)) {
        cursor = path.join(cursor, part);
        try {
          const s = await lstat(cursor);
          if (s.isSymbolicLink() || !s.isDirectory())
            throw new Error(`目标路径父组件冲突: ${rel}`);
        } catch (e) {
          if ((e as NodeJS.ErrnoException).code === "ENOENT")
            await mkdir(cursor);
          else throw e;
        }
      }
      await pipeline(
        createReadStream(src),
        createWriteStream(dest, { flags: "wx" }),
      );
      const h = await I.sha256(dest);
      if (h.error || h.digest !== entry.sha256 || h.size !== entry.size)
        throw new Error(`目标复制后指纹不匹配: ${rel}`);
      copied.push(rel);
    } catch (e) {
      return { ok: false, copied, error: (e as Error).message };
    }
  }
  return { ok: true, copied, target_worktree_path: target, staged: false };
}
async function configureHooks({
  repo_path,
}: {
  repo_path: string;
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return err(error);
  const missing: string[] = [];
  for (const name of ["pre-commit", "commit-msg"])
    try {
      const s = await stat(path.join(root!, ".githooks", name));
      if (!s.isFile()) missing.push(`.githooks/${name}`);
    } catch {
      missing.push(`.githooks/${name}`);
    }
  if (missing.length) return err(`缺少 Hook wrapper: ${missing.join(", ")}`);
  const current = await I.run(
    ["git", "config", "--local", "--get", "core.hooksPath"],
    root!,
  );
  if (
    current.returncode === 0 &&
    current.stdout.trim() !== ".githooks" &&
    current.stdout.trim() !== ""
  )
    return err(
      `当前 core.hooksPath=${JSON.stringify(current.stdout.trim())}；拒绝覆盖既有设置`,
    );
  const r = await I.run(
    ["git", "config", "--local", "core.hooksPath", ".githooks"],
    root!,
  );
  return {
    ok: r.returncode === 0,
    repo_path: root,
    "core.hooksPath": ".githooks",
    error: r.returncode === 0 ? null : "git config failed",
  };
}

async function stagePaths({
  repo_path,
  paths,
}: {
  repo_path: string;
  paths: string[];
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, staged_paths: [], error };
  const parsed = I.requestedPaths(paths);
  if (parsed.error) return { ok: false, staged_paths: [], error: parsed.error };
  const before = await I.stagedNames(root!);
  if (before.error) return { ok: false, staged_paths: [], error: before.error };
  if (before.paths!.length)
    return {
      ok: false,
      staged_paths: before.paths,
      error: "index 已有 staged changes；先由用户决定如何处理",
    };
  for (const rel of parsed.paths!) {
    const e = await I.validateStagePath(root!, rel);
    if (e) return { ok: false, staged_paths: [], error: e };
  }
  const added = await I.run(
    ["git", "add", "--", ...parsed.paths!.map((p) => `:(literal)${p}`)],
    root!,
  );
  const staged = await I.stagedNames(root!);
  const expected = new Set(parsed.paths!);
  const actual = new Set(staged.paths ?? []);
  if (
    added.returncode !== 0 ||
    staged.error ||
    actual.size !== expected.size ||
    [...actual].some((p) => !expected.has(p))
  )
    return {
      ok: false,
      staged_paths: staged.paths ?? [],
      error: staged.error ?? "git add 失败或 staged paths 与显式请求不一致",
    };
  return { ok: true, repo_path: root, staged_paths: [...actual].sort() };
}
async function commitChanges({
  repo_path,
  message,
  expected_paths,
}: {
  repo_path: string;
  message: string;
  expected_paths: string[];
}): Promise<Dict> {
  const { root, error } = await I.validRepo(repo_path);
  if (error) return { ok: false, error };
  const expected = I.requestedPaths(expected_paths);
  if (expected.error) return { ok: false, error: expected.error };
  const staged = await I.stagedNames(root!);
  if (staged.error) return { ok: false, error: staged.error };
  const wanted = new Set(expected.paths!),
    actual = new Set(staged.paths!);
  if (wanted.size !== actual.size || [...actual].some((p) => !wanted.has(p)))
    return {
      ok: false,
      staged_paths: [...actual].sort(),
      error: "staged paths 与 expected_paths 不完全一致；未提交",
    };
  const check = await checkMessage(message);
  if (!check.passed)
    return { ok: false, error: "提交信息未通过既有策略", message_check: check };
  const whitespace = await I.run(["git", "diff", "--cached", "--check"], root!);
  if (whitespace.returncode !== 0)
    return {
      ok: false,
      error: "git diff --cached --check 未通过",
      diagnostics: splitStatus(whitespace.stdout),
    };
  const commit = await I.run(["git", "commit", "-m", message], root!);
  if (commit.returncode !== 0)
    return {
      ok: false,
      error: `git commit failed (exit ${commit.returncode}); no hook bypass was attempted`,
    };
  const [oid, msg, paths, status] = await Promise.all([
    I.run(["git", "rev-parse", "--verify", "HEAD"], root!),
    I.run(["git", "log", "-1", "--format=%B"], root!),
    I.run(
      [
        "git",
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "--no-renames",
        "-r",
        "-z",
        "HEAD",
      ],
      root!,
    ),
    I.run(
      ["git", "status", "--short", "--branch", "--untracked-files=all"],
      root!,
    ),
  ]);
  if ([oid, msg, paths, status].some((r) => r.returncode !== 0))
    return {
      ok: false,
      committed: true,
      error: "提交已成功，但提交元数据或后续工作区状态无法完整回读",
    };
  return {
    ok: true,
    committed: true,
    commit_oid: oid.stdout.trim(),
    message: msg.stdout.replace(/\n+$/, ""),
    paths: paths.stdout.split("\0").filter(Boolean).sort(),
    status: splitStatus(status.stdout),
  };
}
async function checkMessage(
  message: string,
): Promise<{ passed: boolean; subject: string; errors: string[] }> {
  const lines = message
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.trimStart().startsWith("#"));
  const subject = lines[0]?.trim() ?? "";
  const errors: string[] = [];
  if (!subject) errors.push("提交主题不能为空");
  else {
    if (!SUBJECT_RE.test(subject))
      errors.push("提交主题必须使用允许的类型前缀和格式：<type>: 中文说明");
    if (!CHINESE_RE.test(subject)) errors.push("提交主题必须包含中文说明");
  }
  const match = lines.join("\n").match(ATTRIBUTION_RE);
  if (match) errors.push(`禁止包含工具署名或生成声明: ${match[0]}`);
  return { passed: !errors.length, subject, errors };
}
