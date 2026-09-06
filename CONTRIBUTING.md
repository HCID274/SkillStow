# SkillStow 开发约定

更新：2026-09-06。先读 [AGENTS.md](AGENTS.md)、[当前需求](docs/REQUIREMENTS.md) 和 [SPEC](docs/SPEC.md)。用户已确认以本项目为实现基线，接入 Mac、HomeServer、Shenzhen，Windows 延后。

## 保持实现简单

- Git 操作调用系统 git，保留原始错误和冲突现场；不引入 libgit2/gitoxide，不自行重建 Git 协议。
- 文件操作优先标准库，不建设通用文件系统事务框架或解析 Windows reparse point 二进制结构。Windows 删除链接使用 remove_dir，禁止用递归删除代替。
- 已确认的 Git worktree、单个同步锁、持久编辑标记、宿主定时器和单用途 Python runtime 适配器属于当前方案。
- plan.rs 保持纯计划计算，平台链接原语集中在 link.rs；私人 runtime 特有逻辑留在 migration/。
- 保留 1000 行 Rust 源码规模检查作为重新审视复杂度的绊线。超过时先复核职责与需求，不通过压行、删验证或把通用实现搬进脚本规避。旧 SPEC 的逐文件预算已过时，不要求每新增一行就删除一行。

## 文档和授权

行为变化同步更新 SPEC、相关测试与交接状态。发现文档含糊或与已确认需求冲突，修正文档并说明原因；不凭历史文档制造新的审批流程。
旧 REPLAN、SPEC 和任务拆分保留为背景。旧版“先通过 Windows 才允许 README、第三台设备和适配器”等限制已由用户批准的本轮范围替代。
不恢复旧 SkillRiver 的 Hub、签名、PR 强制审批、服务端或网站。公众产品、新设备范围及其他实质扩展按用户新需求处理。

## 验证和交付

使用真实 Git 临时仓覆盖同步行为，实现与直接相关的测试同批提交；迁移适配器在隔离 runtime 副本中验证。命令见 [HANDOFF.md](docs/HANDOFF.md)。测试按实际改动选择，未变化的已验证内容复用证据。
Windows 链接修改须参考历史平台探针并补当前环境验证；本轮 Linux 结果不能替代 Windows 实机验收。
按能力分批使用中文 Conventional Commits，保护现有修改和远端历史。源代码提交、推送、合并、设备升级及个人内容发布分别记录，不互相冒充。

当前完成标准是已批准三台设备的个人使用闭环及相应证据。Windows 仍为后续接入项，详见 [TASKS.md](docs/TASKS.md)。
