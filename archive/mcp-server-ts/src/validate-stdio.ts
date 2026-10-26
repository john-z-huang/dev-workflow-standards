import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const expected = new Set([
  "check_branch_names_ts",
  "check_commit_message_ts",
  "check_staged_changes_ts",
  "stage_repository_paths_ts",
  "commit_repository_changes_ts",
  "audit_issue_pr_policy_ts",
  "cleanup_merged_pr_local_branch_ts",
  "audit_repository_state_ts",
  "list_github_issue_labels_ts",
  "create_github_issue_ts",
  "push_issue_branch_to_origin_ts",
  "create_github_pull_request_ts",
  "merge_github_pull_request_ts",
  "push_fork_main_fast_forward_ts",
  "list_repository_worktrees_ts",
  "switch_repository_branch_ts",
  "pull_origin_branch_fast_forward_ts",
  "fetch_upstream_branch_ts",
  "merge_upstream_branch_fast_forward_ts",
  "rebase_repository_branch_ts",
  "remove_repository_worktree_ts",
  "create_repository_worktree_ts",
  "capture_untracked_file_manifest_ts",
  "copy_untracked_files_to_worktree_ts",
  "configure_project_hooks_path_ts",
]);
const requiredByTool: Record<string, string[]> = {
  check_branch_names_ts: [],
  check_commit_message_ts: ["message"],
  check_staged_changes_ts: ["repo_path"],
  stage_repository_paths_ts: ["repo_path", "paths"],
  commit_repository_changes_ts: ["repo_path", "message", "expected_paths"],
  audit_issue_pr_policy_ts: ["repo_path"],
  cleanup_merged_pr_local_branch_ts: ["repo_path", "pr_number"],
  audit_repository_state_ts: ["repo_path"],
  list_github_issue_labels_ts: ["repo_path"],
  create_github_issue_ts: ["repo_path", "repo", "title", "body", "labels"],
  push_issue_branch_to_origin_ts: [
    "repo_path",
    "repo",
    "branch_name",
    "issue_number",
  ],
  create_github_pull_request_ts: [
    "repo_path",
    "repo",
    "title",
    "body",
    "base_branch",
    "head_branch",
    "issue_number",
  ],
  merge_github_pull_request_ts: [
    "repo_path",
    "repo",
    "pr_number",
    "merge_method",
  ],
  push_fork_main_fast_forward_ts: ["repo_path", "repo"],
  list_repository_worktrees_ts: ["repo_path"],
  switch_repository_branch_ts: ["repo_path", "branch_name"],
  pull_origin_branch_fast_forward_ts: ["repo_path", "branch_name"],
  fetch_upstream_branch_ts: ["repo_path", "branch_name"],
  merge_upstream_branch_fast_forward_ts: ["repo_path", "branch_name"],
  rebase_repository_branch_ts: ["repo_path", "branch_name", "base_branch"],
  remove_repository_worktree_ts: [
    "repo_path",
    "target_worktree_path",
    "branch_name",
  ],
  create_repository_worktree_ts: [
    "repo_path",
    "target_worktree_path",
    "branch_name",
    "base_branch",
  ],
  capture_untracked_file_manifest_ts: ["repo_path"],
  copy_untracked_files_to_worktree_ts: [
    "repo_path",
    "target_worktree_path",
    "manifest",
  ],
  configure_project_hooks_path_ts: ["repo_path"],
};
const optionalByTool: Record<string, string[]> = {
  check_branch_names_ts: ["branch_names", "repo_path"],
  audit_issue_pr_policy_ts: [
    "repo",
    "issue_number",
    "pr_number",
    "expected_base",
    "expected_head",
  ],
  cleanup_merged_pr_local_branch_ts: ["repo", "branch_name", "merged_head_oid"],
  list_github_issue_labels_ts: ["repo"],
};
const client = new Client(
  { name: "dev-workflow-standards-mcp-ts-validator", version: "0.1.0" },
  { versionNegotiation: { mode: { pin: "2026-07-28" } } },
);
const transport = new StdioClientTransport({
  command: process.execPath,
  args: ["dist/server.js"],
  cwd: process.cwd(),
  stderr: "pipe",
});
try {
  await client.connect(transport);
  const result = await client.listTools();
  const names = result.tools.map((entry) => entry.name).sort();
  const wanted = [...expected].sort();
  if (
    names.length !== wanted.length ||
    names.some((name, index) => name !== wanted[index])
  )
    throw new Error(`Unexpected tools: ${names.join(", ")}`);
  for (const entry of result.tools) {
    const required = [...(entry.inputSchema.required ?? [])].sort();
    const expectedRequired = [...requiredByTool[entry.name]!].sort();
    if (
      required.length !== expectedRequired.length ||
      required.some((name, index) => name !== expectedRequired[index])
    )
      throw new Error(`Required input mismatch for ${entry.name}`);
    const properties = Object.keys(entry.inputSchema.properties ?? {}).sort();
    const expectedProperties = [
      ...requiredByTool[entry.name]!,
      ...(optionalByTool[entry.name] ?? []),
    ].sort();
    if (
      properties.length !== expectedProperties.length ||
      properties.some((name, index) => name !== expectedProperties[index])
    )
      throw new Error(`Input field mismatch for ${entry.name}`);
    for (const name of optionalByTool[entry.name] ?? []) {
      const schema = entry.inputSchema.properties?.[name] as
        | { type?: string | string[]; anyOf?: Array<{ type?: string }> }
        | undefined;
      if (!schema) throw new Error(`Missing schema for ${entry.name}.${name}`);
      if (
        !(Array.isArray(schema.type) && schema.type.includes("null")) &&
        !schema.anyOf?.some((item) => item.type === "null")
      )
        throw new Error(
          `Optional field ${entry.name}.${name} lost null support`,
        );
    }
    if (!entry.description || !entry.annotations)
      throw new Error(`Description or annotations missing for ${entry.name}`);
    const github = [
      "audit_issue_pr_policy_ts",
      "cleanup_merged_pr_local_branch_ts",
      "audit_repository_state_ts",
      "list_github_issue_labels_ts",
      "create_github_issue_ts",
      "push_issue_branch_to_origin_ts",
      "create_github_pull_request_ts",
      "merge_github_pull_request_ts",
      "push_fork_main_fast_forward_ts",
    ].includes(entry.name);
    const expectedReadOnly =
      entry.name.startsWith("check_") ||
      entry.name.startsWith("list_") ||
      entry.name.startsWith("capture_") ||
      entry.name.startsWith("audit_");
    if (
      entry.annotations.readOnlyHint !== expectedReadOnly ||
      entry.annotations.openWorldHint !== github
    )
      throw new Error(`ToolAnnotations mismatch for ${entry.name}`);
    const expectedDestructive = [
      "commit_repository_changes_ts",
      "cleanup_merged_pr_local_branch_ts",
      "rebase_repository_branch_ts",
      "remove_repository_worktree_ts",
      "merge_github_pull_request_ts",
      "push_fork_main_fast_forward_ts",
    ].includes(entry.name);
    const expectedIdempotent = [
      "configure_project_hooks_path_ts",
      "push_fork_main_fast_forward_ts",
    ].includes(entry.name);
    if (
      (entry.annotations.destructiveHint ?? false) !== expectedDestructive ||
      (entry.annotations.idempotentHint ?? false) !== expectedIdempotent
    )
      throw new Error(`Write annotations mismatch for ${entry.name}`);
  }
  const merge = result.tools.find(
    (entry) => entry.name === "merge_github_pull_request_ts",
  )!.inputSchema.properties?.merge_method as { enum?: string[] } | undefined;
  if (!merge) throw new Error("Missing merge_method schema");
  if (
    JSON.stringify(merge.enum) !== JSON.stringify(["squash", "merge", "rebase"])
  )
    throw new Error("Merge method enum mismatch");
  const manifest = result.tools.find(
    (entry) => entry.name === "copy_untracked_files_to_worktree_ts",
  )!.inputSchema.properties?.manifest as
    | {
        items?: {
          properties?: Record<
            string,
            { pattern?: string; minimum?: number; type?: string }
          >;
        };
      }
    | undefined;
  if (!manifest) throw new Error("Missing manifest schema");
  const manifestProperties = manifest.items?.properties;
  if (
    manifestProperties?.sha256?.pattern !== "^[0-9a-f]{64}$" ||
    manifestProperties?.size?.minimum !== 0 ||
    manifestProperties?.size?.type !== "integer"
  )
    throw new Error("Manifest entry constraints mismatch");
  const call = await client.callTool({
    name: "check_commit_message_ts",
    arguments: { message: "feat: 添加检查" },
  });
  if (call.isError || !call.structuredContent || call.content.length !== 1)
    throw new Error(
      "Read-only MCP tool call did not return text and structured content",
    );
  console.log(
    `MCP 2026-07-28 stdio tools/list returned ${names.length} tools; read-only tool call returned text and structured content.`,
  );
} finally {
  await client.close();
}
