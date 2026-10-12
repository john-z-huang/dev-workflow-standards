# 本地 Serena MCP 工具更新流程

## 授权门槛

只有用户明确要求检查本机 uv 安装的 Serena 时，才可检查安装来源、版本、源码 checkout、remote、branch 或工作区状态，并获取和比较上游状态。若用户只要求检查，发现上游有更新后只报告，不执行 pull 或 `uv tool upgrade serena-agent`。只有用户明确要求升级/更新，或在检查后明确批准应用更新，才可执行 pull、`uv tool upgrade serena-agent` 及其后续核验和重启步骤。未获相应授权时，不得自主检查或更新；普通代码任务、Serena MCP 项目初始化或激活都不构成授权。

## 执行步骤

1. **确认安装来源。** 获得上述授权后，运行 `uv tool list --show-version-specifiers`，确认 `serena-agent` 是从本地源码以 editable 方式安装，并记录显示的本地 `file://` URL。运行 `uv tool dir` 找到 uv tools 目录，再检查其中对应的 `serena_agent-*.dist-info/direct_url.json`；其 `url` 必须指向同一源码 checkout，且 `dir_info.editable` 为 `true`。来源不明、不匹配或不是 editable 安装时停止。

   ```sh
   uv tool list --show-version-specifiers
   UV_TOOL_DIR="$(uv tool dir)"
   find "$UV_TOOL_DIR" -type f -path '*/serena_agent-*.dist-info/direct_url.json' -print
   ```

   确认只找到预期安装对应的文件后，读取该文件并核对 JSON 字段；路径不明确或结果不唯一时停止。

2. **核实 checkout 和上游。** 将实际核实的源码路径、remote 名和上游默认分支填入变量；路径可以含空格。检查 checkout 是预期的 Serena 仓库、remote 指向预期上游，并通过 remote 信息核实其默认分支。不要照抄示例值：

   ```sh
   SERENA_SOURCE="/absolute/path/to/serena"
   SERENA_UPSTREAM=upstream
   SERENA_BRANCH=main
   git -C "$SERENA_SOURCE" remote -v
   git -C "$SERENA_SOURCE" remote show "$SERENA_UPSTREAM"
   ```

3. **确认工作区干净。**

   ```sh
   git -C "$SERENA_SOURCE" status --short
   ```

   若命令有任何输出，立即停止；不得 stash、重置或覆盖本地改动。

4. **获取并比较上游。** 确认 `SERENA_UPSTREAM` 和 `SERENA_BRANCH` 与上一步核实的 remote 及默认分支一致后，执行：

   ```sh
   git -C "$SERENA_SOURCE" fetch "$SERENA_UPSTREAM"
   git -C "$SERENA_SOURCE" rev-list --left-right --count "HEAD...$SERENA_UPSTREAM/$SERENA_BRANCH"
   ```

   结果左侧是本地独有提交数，右侧是上游独有提交数。只有结果为 `0 N` 且 `N > 0` 时才继续。结果为 `0 0` 表示没有上游更新，不需要 pull 或升级；本地与上游分叉、结果不符或命令失败时停止，不得重置或强制覆盖。

5. **快进并升级 uv 工具。** 仅在上一步结果为 `0 N` 且 `N > 0` 时执行：

   ```sh
   git -C "$SERENA_SOURCE" pull --ff-only "$SERENA_UPSTREAM" "$SERENA_BRANCH"
   uv tool upgrade serena-agent
   ```

   任一命令失败时停止并保留现场，不要继续尝试覆盖或重置。

6. **核验安装并重启。** 再次运行 `uv tool list --show-version-specifiers`，确认 `serena-agent` 的 required 来源仍是预期本地 `file://` URL；再次检查对应 `serena_agent-*.dist-info/direct_url.json`，确认 `url` 指向 `$SERENA_SOURCE` 且 `dir_info.editable` 为 `true`。核验成功后重启 Serena MCP 服务或 Session，再使用更新后的代码。

更新中的任何阶段若发现安装来源不明、工作区有改动、上游关系分叉或命令失败，立即停止并报告现场；不得 stash、重置或强制覆盖。
