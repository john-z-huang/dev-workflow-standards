### GitHub 操作规范

- 涉及 GitHub（包括 Issue、Pull Request、Actions、仓库信息或评论）前，若有适用且可用的 GitHub Skill，先查阅其相关建议；没有时按本文和实际工具 schema 执行，不因缺失 Skill 阻塞。
- GitHub 操作优先通过 GitHub CLI（`gh`）执行。若开发环境是云端容器且未安装 `gh` CLI，可改用当前 Code Agent 已授权的 GitHub Connector 或 GitHub App 集成层执行等效操作；不得因为缺少 `gh` CLI 而改用浏览器或浏览器自动化工具。
- 使用 GitHub Connector 或 GitHub App 集成层时，必须确认该集成已获得目标仓库及当前操作所需的授权，并遵循其工具接口的参数、确认和返回值约定；不得要求用户在对话中粘贴访问令牌，也不得自行猜测或伪造授权信息。
- 无论使用 `gh` CLI 还是已授权集成层，都必须显式核对仓库、Issue、PR、base/head 分支及操作结果；集成层应提供与下述 `gh` 示例等价的查询、创建、更新、评论、合并和核验能力。

  **正确做法**：使用 `gh issue create --title "..." --body "..." --label "enhancement" --assignee "@me"`，或调用已授权 GitHub Connector / GitHub App 的等效 Issue 创建操作并通过 `labels`、`assignees` 参数附加分类标签和本人责任人；使用 `gh pr create --title "..." --body "..." --assignee "@me"`，或调用其等效 PR 创建操作并确保创建后立即完成本人指派。

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
- 创建新 Issue 时必须同时完成分类标签，不得把“先创建、以后再补标签”作为正常流程：
  1. **先读取已有标签**：使用 `gh label list --limit 100 --json name,description,color`，或调用已授权 GitHub 集成层提供的等效标签查询操作。默认标签也可能被仓库维护者修改或删除，因此不得只凭名称猜测其存在。
  2. **判断 Issue 类别**：根据 Issue 的主要目的选择至少一个能够表达工作类型的标签。优先复用仓库已经定义且语义明确的类型标签；若仓库沿用 GitHub 默认标签，可使用 `bug` 表示缺陷、`documentation` 表示纯文档改动、`enhancement` 表示新增功能或改进，`question` 仅用于确实以信息确认或答疑为主的 Issue。
  3. **区分主类别与辅助标签**：`good first issue`、`help wanted`、优先级、状态、组件或领域等标签可以追加，但不能替代工作类型分类标签。若仓库已有更细的 `type:*`、组件或领域标签体系，应遵循仓库约定，可同时附加多个标签以提高筛选能力。
  4. **创建时一次性附加**：`gh` CLI 使用 `gh issue create ... --label "<类别标签>" --assignee "@me"`；多个标签可重复传入 `--label`。GitHub Connector / GitHub App 应在 Issue 创建调用中通过等效 `labels` 与 `assignees` 字段一次性附加分类标签和本人责任人，不应先创建无标签、无责任人的 Issue 再依赖人工补录。
  5. **创建后核验**：使用 `gh issue view <编号> --json number,title,state,labels,assignees`，或集成层的等效 Issue 读取操作，确认目标仓库、Issue 编号、标签和本人 assignee 均正确。若返回结果未包含预期分类标签或本人责任人，应先修正再视为流程完成。
  6. **无可用分类标签时停止猜测**：若仓库没有语义合适的现有类别标签，或当前工具无法可靠读取/使用标签，不得随意发明一次性标签，也不得把未分类 Issue 当作流程完成。应明确报告缺失的标签或工具能力；只有在当前用户任务已经授权修改仓库标签体系时，才创建稳定、可复用的新标签后继续。
- 若组织或仓库同时使用 GitHub Issue types，可将其作为额外分类元数据；本 Skill 仍要求保留至少一个类别 label，以便在 Issue/PR 列表、搜索和筛选中快速识别工作类型。
- Issue 和 PR 默认指派给当前已认证的本人 GitHub 账号；只有当前用户明确指定其他责任人时才覆盖此默认值：
  1. **先解析当前账号**：`gh` CLI 使用 `gh api user --jq .login` 获取当前登录用户名；GitHub Connector / GitHub App 使用其当前用户/登录信息查询能力。不得假设仓库 owner 一定等于当前认证账号，也不得在 Skill 中硬编码用户名。
  2. **Issue 自指派**：创建 Issue 时优先直接使用 `--assignee "@me"` 或创建接口的 `assignees` 字段，与分类标签一起写入。
  3. **PR 自指派**：`gh pr create` 使用 `--assignee "@me"`。若 GitHub 集成层的 PR 创建接口不提供 assignee 字段，应在 PR 创建成功后立即通过该 PR 对应的 Issue/assignee 接口把当前登录用户名加入 assignees；这属于创建流程的一部分，不视为人工补录。
  4. **创建后核验**：Issue 使用 `gh issue view <编号> --json assignees`，PR 使用 `gh pr view <编号> --json assignees`，或集成层等效读取操作，确认本人账号确实在 assignees 中。若指派失败、当前身份不可被指派或工具缺少必要能力，应明确报告阻塞，不得把 Issue/PR 创建流程视为完成。
- 实现改动必须通过 Pull Request 合并，并在 PR 描述中通过 `Closes #<Issue 编号>`（或等效关键字）关联对应的开放 Issue。
- 未关联任何开放 Issue 时，禁止将本地改动推送到 GitHub。
- 可使用只读脚本 `scripts/check-pr-policy.py` 检查 Issue 开放状态、PR 关联关键词以及显式指定的 base/head 拓扑；该脚本不替代 Issue/PR 的创建、审核和合并授权。
