# 独立 Skill 安装与更新

Skill 指令从发布包复制为普通文件快照。开发仓库可以放在任意目录，不需要放入 Skill 扫描目录，也不使用指向源码的符号链接。安装软件包与更新已安装 Skill 是两个独立动作。

## 安装发布包

使用已取得并核验版本的 wheel；不假定本项目已有公开包索引。以下路径替换为实际构建产物：

```text
uv tool install /absolute/path/dev_workflow_standards_tools-0.2.0-py3-none-any.whl
dev-workflow-standards skills install --dry-run
dev-workflow-standards skills install
dev-workflow-standards skills show
```

默认目标为 `~/.agents/skills/dev-workflow-standards`。`--target /absolute/path/dev-workflow-standards` 指定完整目标目录；支持显式选择兼容目录，但不默认写入 `~/.codex/skills`，也不覆盖任何已有目标。路径不得含 `..`、符号链接祖先或位于 Git checkout 内。父目录可由正式安装创建；预览和查看不创建目录或锁文件。

命令离线读取包资源，不读取 OpenAI 凭据、不调用 OpenAI、不注册 MCP、不修改 Codex 配置，也不复制或启用 Hook。安装器写入资源、受管清单及同目标的持久锁文件。macOS/Linux 使用原子目录发布；其他平台或不支持原子操作的文件系统拒绝写入，不退回非原子覆盖。

## 显式更新

先按原安装来源升级软件包，例如 `uv tool install --force /absolute/path/new-version.whl`；这一步不会更新已安装 Skill。之后执行：

```text
dev-workflow-standards skills update --dry-run
dev-workflow-standards skills update
dev-workflow-standards skills show
```

使用显式目标安装的，更新和查看时继续传入同一 `--target`。查看输出包含包版本及已安装版本。重复 `install` 会拒绝已有目标；重复 `update` 在内容相同时返回 `unchanged`。源码文档变化不会影响已安装快照；相同包版本也会比较内容校验和。

更新要求原清单归属正确，且全部文件与清单一致。用户修改、缺失文件、额外文件或目录、硬链接、符号链接和特殊文件均会阻止更新。未知旧目录没有受管清单，不会被自动接管。完整性清单用于检测损坏和修改，不是来源签名或授权凭证；安装包来源仍需用户核验。

## 现有 Skill 和中断处理

已有 `~/.agents/skills/dev-workflow-standards` 不会被自动迁移、覆盖或删除。先保留旧项目；需要共存时可选择独立目标或隔离的 Skill 根目录，但目录名变化不会改变 `SKILL.md` 的技能名称。避免同时让 Codex 加载两份同名 Skill；现有绝对路径引用不会自动调整。人工迁移和全局指令变更需另行确认。

安装/更新使用同目标的合作进程锁，竞争时失败而非排队覆盖。原子交换前后正式目录均为完整快照；强制终止可能留下 `.名称.skill-stage-*` 副本。先用 `skills show` 检查正式安装并人工核对副本，再决定如何处理；工具不自动清理未知残留。锁文件保留以维持同一锁身份，不应在安装进程运行时删除。

合作进程锁不能阻止外部编辑器或恶意进程写文件；更新期间应停止其他写入者。发布前核对快照，交换后检测到旧目录变化会撤回并保留现场。此机制不承诺断电持久化或对恶意并发写入者的沙箱隔离。

## MCP 与源码辅助脚本

原 `dev-workflow-standards-tools` 命令仍直接启动 stdio MCP。Skill 管理入口是另一个命令，不向该入口加入隐式安装动作。MCP 注册、环境变量名称转发及审批继续遵循原规则。

需要源码安装配置脚本时，按仓库 [README 的 Codex 安装说明](https://github.com/john-z-huang/dev-workflow-standards#codex-中安装) 使用 `scripts/setup-codex-mcp.py`；该脚本属于源码开发资产，不包含在 Skill 快照中。完整仓库结构和 Hook/历史兼容脚本见 [项目仓库](https://github.com/john-z-huang/dev-workflow-standards)。独立 Skill 不依赖这些脚本才能加载；固定操作仍按 [MCP 工具目录](mcp-tools.md) 调用已注册服务。
