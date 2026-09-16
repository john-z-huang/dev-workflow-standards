# 专项操作工作流

只在用户或项目明确要求时执行。

## 队列

| 步骤 | 完成条件 |
|---|---|
| Hook | 明确要求接入/修复 Hook |
| 自动化 | 明确要求新增脚本 |
| 历史维护 | 明确授权历史重写 |
| 验证 | 完成适用验证 |

## 1. Hook

按 [`hooks.md`](../references/hooks.md) 将脚本和 wrapper 接入目标项目；运行集成/等效检查。Hook 不会自动安装，`--no-verify` 不等于验证通过。

## 2. 自动化

使用可移植 Shell/Python、标准库、Git/公开 CLI，不使用专有 Hook/内部状态；按 [`automation-index.md`](../references/automation-index.md) 登记用途、调用和退出码；测试成功/失败/参数错误及副作用；不写入令牌。GitHub 写操作仍读取 [`github-delivery.md`](github-delivery.md)。

## 3. 历史维护

按 [`rewrite-weather-commit-subjects.md`](../references/rewrite-weather-commit-subjects.md) 执行；未经明确授权不得重写、强推或垃圾回收。
