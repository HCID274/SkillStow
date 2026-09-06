# 首批三设备交付记录

日期：2026-09-06。当前范围：Mac、HomeServer、Shenzhen；Windows 由用户明确暂缓。

## 已落地

- 从占位 SkillStow 实现完整目录包、设备独立选择、依赖解析、Git 对账与发布、编辑隔离、必要删除确认、本机应用收据。
- 个人数据使用现有私有仓库 `HCID274/skills`，所有设备持有完整 checkout。当前内容布局为 systems/mac、systems/homeserver、systems/shenzhen。
- 当前 runtime 共享依赖按完整设备包导入；各设备原有 manifest、overlay、独有能力和凭据保留。HomeServer 的 development-toolchain、debian-host-bootstrap 与 Shenzhen 的 panclilocal 均保留。
- 原 Mac 单向同步入口改为兼容入口；skillgo、agent-skill-ops 和 runtime 维护入口均引导到 skillstow-maintain。
- 所有受管内容经发布前 runtime 校验；应用有备份、漂移保护和恢复路径。状态、缓存、投影、凭据、第三方插件不作为个人规范源复制。

## 实机证据

三台设备均已返回 `applied=true`，提交为 `531530385730f28853ccbe5f0f10fd11c4a33a4d`，受管工作区干净，无编辑标记和未完成投影动作。

真实维护顺序：

1. Mac 导入并发布各设备内容；随后发布同步机制文档更新 `fe27f5e`。
2. HomeServer 修改三端的维护恢复经验和新入口回归断言，发布 `2fffc0b`；Mac、Shenzhen 的后台任务自动接收，收据及相同维护文件摘要一致。
3. Shenzhen 将各端旧维护入口接入 SkillStow，发布 `5315303`；Mac、HomeServer 自动接收并返回相同提交的实际应用收据。

客户端实际枚举成功：Mac 62、HomeServer 44、Shenzhen 53 个可发现 Skills（含宿主技能与插件）；三端均包含 skillstow-maintain，枚举错误为 0。这些数字不是个人叶子数量；个人体系分别为 37、24、37 个叶子。

## 后台与访问

| 设备 | 后台方式 | GitHub 访问 |
| --- | --- | --- |
| Mac | launchd，60 秒检查 | HTTPS，使用本机已登录的 GitHub CLI；SSH 22/443 经诊断仍有间歇超时 |
| HomeServer | 用户 crontab，60 秒检查 | 仅限 Skills 仓的专用可写 deploy key |
| Shenzhen | systemd 用户 timer，60 秒检查；已开启该用户 linger | 现有 GitHub SSH 身份 |

SSH 经 HomeServer 跳转只用于 Mac 临时登录/传输到 Shenzhen；内容同步由三台设备分别连接 GitHub 完成，不依赖 SSH 中转链。

## 验证范围

- 15 项真实 Git 集成测试：资源完整性、设备版本、跨设备维护、并发修改、冲突恢复、编辑隔离、静默窗口、外部文件保护、删除确认、遗漏资源、发布前校验、失败收据和同层版本歧义。
- 同层设备版本歧义测试在修复前失败、修复后通过。
- 原 Mac runtime 的 36 项测试通过；新入口引起的两处固定计数断言随行为更新。
- 隔离迁移验证：首次应用、重复应用、凭据保留、活动漂移阻断、合并回维护仓后的恢复、新增资源投放。
- cargo clippy -- -D warnings、cargo fmt、git diff --check 通过。

## 使用与恢复

三端 CLI：`~/.local/bin/skillstow`；配置：`~/.config/skillstow/config.toml`；维护仓：`~/.local/share/skillstow/workspace`。

日常使用 skillstow-maintain，或按 README 的 edit begin/finish 流程操作。不要直接修改 `.codex/skills` 活动副本；若已经发生，先把差异合并回维护仓，重新发布后适配器允许对齐。

应用备份位于 `~/.local/state/skillstow/backups/`，文件状态清单为同目录上层的 runtime.json。恢复旧内容优先在维护仓 `git revert` 对应提交，然后通过正常同步发布；Git 冲突保留现场由 AI 处理。

## 未纳入本轮

- Windows 实机接入。CLI 已保留 junction 分支；现有私人 runtime 的 Unix 依赖仍需在 Windows 接入时适配和验证，不能据本轮 Linux 测试声称 Windows 已可用。
- 公众服务、Hub、签名发布协议、网页控制台和项目级差异产品化。
- GitHub 主分支并未建立防绕过的签名/强制校验协议。本轮发布边界由个人 CLI、维护 Skill 与本机钩子实现；其他设备应用状态以各自收据为准。
