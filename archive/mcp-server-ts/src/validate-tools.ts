import { createServer } from "./tools.js";

// Lightweight package-local registry contract check. It does not invoke tool handlers.
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
const server = createServer() as unknown as {
  _registeredTools?: Record<string, unknown>;
  registeredTools?: Record<string, unknown>;
};
const registered = server._registeredTools ?? server.registeredTools;
if (!registered)
  throw new Error("SDK registry is not exposed for local validation");
const names = Object.keys(registered).sort();
const wanted = [...expected].sort();
if (
  names.length !== wanted.length ||
  names.some((name, index) => name !== wanted[index])
) {
  throw new Error(
    `Registered tool mismatch. Got ${names.length}: ${names.join(", ")}`,
  );
}
console.log(`Validated ${names.length} registered tool names.`);
