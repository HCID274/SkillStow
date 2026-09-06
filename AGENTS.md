# SkillStow 工作入口

这里是当前有效的实现仓库。新对话先读 [交接状态](docs/HANDOFF.md)、[已确认需求](docs/REQUIREMENTS.md)、[行为契约](docs/SPEC.md) 和 [开发约定](CONTRIBUTING.md)，按任务需要查阅 [交付证据](docs/DELIVERY.md)。

- 用户已确认以 SkillStow 替代旧 SkillRiver。所需需求、决策和接续信息均在本仓；不依赖旧目录，不恢复旧 Hub、签名或 PR 审批系统。
- 首批 Mac、HomeServer、Shenzhen 已部署并完成双向维护验收。Windows 由用户暂缓，不能当作已完成，也不阻塞这三台设备使用。
- 本仓保存 CLI、迁移适配器、测试和项目文档。个人 Skills 正文与资源在独立私有数据仓；不得复制进本代码仓。
- 修改个人 Skills 时，读取已安装的 `skillstow-maintain`，先 `edit begin`，只修改返回的维护仓，完成后主动 `edit finish` 并解决冲突。不要直接改 `.codex/skills` 活动副本或 `published/`。
- 修改本仓代码和文档采用普通 Git 开发流程，不需要开启个人 Skills 的编辑任务。提交按能力分批，使用中文 Conventional Commits；部署证据与代码推送分别报告。
- 用户明确由自己删除旧项目目录。不要替用户删除。

`docs/REPLAN.md`、`docs/SPEC-20260821.md`、`docs/TASKS-20260821.md` 是历史资料，不能覆盖当前需求和契约。
