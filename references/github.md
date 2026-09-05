### GitHub 操作规范

- 涉及 GitHub（包括 Issue、Pull Request、Actions、仓库信息或评论）前，若有适用且可用的 GitHub Skill，先查阅其相关建议；没有时按本文和实际工具 schema 执行，不因缺失 Skill 阻塞。
- GitHub 操作优先通过 GitHub CLI（`gh`）执行。若开发环境是云端容器且未安装 `gh` CLI，可改用当前 Code Agent 已授权的 GitHub Connector 或 GitHub App 集成层执行等效操作；不得因为缺少 `gh` CLI 而改用浏览器或浏览器自动化工具。
- 使用 GitHub Connector 或 GitHub App 集成层时，必须确认该集成已获得目标仓库及当前操作所需的授权，并遵循其工具接口的参数、确认和返回值约定；不得要求用户在对话中粘贴访问令牌，也不得自行猜测或伪造授权信息。
- 无论使用 `gh` CLI 还是已授权集成层，都必须显式核对仓库、Issue、PR、base/head 分支及操作结果；集成层应提供与下述 `gh` 示例等价的查询、创建、更新、评论、合并和核验能力。

  **正确做法**：使用 `gh issue create --title "..." --body "..."`，或调用已授权 GitHub Connector / GitHub App 的等效 Issue 创建操作；使用 `gh pr create --title "..." --body "..."`，或调用其等效 PR 创建操作。

  **错误做法**：在浏览器中打开 `github.com` 手动创建 Issue/PR、使用 Playwright/Selenium 等浏览器自动化工具操作 GitHub 页面。

- 执行 `gh` 命令时，必须使用能够进行受限网络访问的沙箱环境，不得在完全禁止网络访问的沙箱中运行 `gh`。`gh` 需要与 GitHub API 通信，完全断网的沙箱会导致命令不可用，应使用允许出站 HTTPS 请求但施加其他合理限制的沙箱配置。已授权 GitHub Connector / GitHub App 集成层的网络访问由集成运行环境负责，但调用仍必须通过其正式接口完成。

### 网络与认证

- 在受限或配置代理的网络环境中使用 `gh` 前，先确认请求将通过可访问的 HTTP Proxy；不得因代理或 GitHub API 不可达而直接判定 `GH_TOKEN` 或本地登录凭据失效。使用已授权 GitHub Connector / GitHub App 集成层时，遵循其连接状态和授权检查，不将 CLI 的代理或 `GH_TOKEN` 排查要求强加于集成层。

  **使用 `gh` CLI 时的认证排查顺序**：
  1. 先检查代理与 GitHub API 连通性（如 `gh api /zen 2>&1` 或 `curl -I https://api.github.com`）。
  2. 确认网络连通后，再检查 `GH_TOKEN` 是否已设置和凭据是否有效。

- 使用 `gh` CLI 时，确认网络连通后若仍需重新认证：先确认环境变量 `GH_TOKEN` 已设置，再仅通过标准输入将其传递给 `gh auth login --with-token` 完成认证；`GH_TOKEN` 未设置时应报告认证阻塞，不得猜测、伪造或要求用户在对话中粘贴令牌。
- 若云端容器没有 `gh` CLI 且使用已授权 GitHub Connector / GitHub App 集成层：仅使用当前已建立的授权连接；若集成未连接、授权不足或无法访问目标仓库，应报告认证或权限阻塞，不得要求用户粘贴令牌，也不得绕过集成层改用浏览器操作。
- `GH_TOKEN` 是敏感信息：严禁打印、回显、插值展示、记录或写入其值。

  **禁止的行为（非穷举）**：
  - 终端与工具输出（如 `echo $GH_TOKEN`、`printenv GH_TOKEN`）
  - 日志文件、源代码、配置文件
  - 提交信息、Issue、Pull Request、评论和错误报告
  - 调试输出（如 `set -x` 后执行含令牌的命令）

### Issue 与 PR 流程

- 进入 GitHub 协作流程时，新增功能或修复须关联开放 Issue；本地审查和已授权的本地修改可先完成，不因尚未建立 Issue 阻塞。推送前必须补齐开放 Issue。
- Issue 必须清晰、详细地说明以下内容：
  - 功能需求或缺陷表现
  - 影响范围
  - 预期行为与验收标准
  - 必要时补充：复现步骤、技术约束、前置依赖
- 实现改动必须通过 Pull Request 合并，并在 PR 描述中通过 `Closes #<Issue 编号>`（或等效关键字）关联对应的开放 Issue。
- 未关联任何开放 Issue 时，禁止将本地改动推送到 GitHub。
- 可使用只读脚本 `scripts/check-pr-policy.py` 检查 Issue 开放状态、PR 关联关键词以及显式指定的 base/head 拓扑；该脚本不替代 Issue/PR 的创建、审核和合并授权。
