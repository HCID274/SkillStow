# SkillStow 行为契约

更新：2026-09-09，CLI 0.2.0。

## 发布与应用

维护仓是 main 上的完整内容 checkout；published 是独立 Git worktree。顺序为 fetch、校验、提交、rebase、再次校验、影响分析、push、确认远端包含提交、应用、收据。冲突保留现场，不强推、不默认丢弃任一端。

edit begin 先对账并持久暂停本机后台发布；edit finish 发布完成后解除标记。cancel 保留修改并继续暂停。后台由宿主每分钟调用 sync --background；无编辑标记的内容稳定 60 秒后才发布。离线设备不阻塞发布。

已授权删除或范围收缩可在发起端使用 --approve-removals；接收端不重复询问。普通 status 只使用最近 fetch 信息；其他设备结果需要 fleet 或实机收据。

## 统一模块

外层 skillstow.toml 继续支持普通目录包、设备启用集合和设备/平台/通用版本。私人体系只登记一个 personal-skill-system 通用包，指向 system/；四端选择同一个源。

system/manifest.json 是模块内部唯一的 Skill 归属清单：version、devices（平台和 SSH 端点）、skills（源目录及适用设备）。Skill 的正文、脚本与参考资源随其目录完整管理。每端完整 checkout，应用阶段按清单筛选。

本机 config.toml 的 module_adapter argv 指向明确安装的 migration/skill_module.py。before_publish 调用 validate，after_apply 调用 apply --device ID。CLI 不执行内容仓中任意脚本。

- locate ID：只输出该 Skill 的源路径、设备范围和清单路径。
- impact：对比最近 fetch 的 origin/main，程序输出具体受影响 Skills、设备及删除/替换状态，包括未跟踪的新资源。
- fleet：并发只读查询设备收据；失败显示未知和上次确认时间。凭据来自各机现有 SSH 配置，不进清单。
- validate：核对清单、设备、入口和资源；未知范围或外逸路径拒绝发布。
- apply：按范围复制到本机 .codex/skills，并连接 .agents/skills 与 .claude/skills。目录链接在 Windows 使用 junction，Unix 使用软链。

旧 runtime 受管文件和入口退出活动体系，凭据、.system 插件和其他非受管内容保留。Windows 初次接入显式 --adopt 接管核查过的旧个人 Skills。修改前逐文件备份，检测到外部修改时停止；失败按本次日志回滚，不递归删除目录链接目标。

共用全局规则由模块提供：Codex AGENTS.md 是程序生成的本机副本，Claude CLAUDE.md 引用本机应用后的同一正文。二者都由一个仓库源更新，不独立维护。旧会话不因文件已写入自动算已重载。

模块不运行自定义树、LRU、SQLite 遥测或调用 Hook。只移除原 Skills 遥测 Hook，保留其他客户端设置。

## 返回与验证

CLI：0 为成功/正常等待，1 为应用阻塞，2 为失败。模块适配器 impact 的内部返回码 3 表示删除或替换，CLI 将其转为发起端删除授权检查。

receipt.toml 中 applied=true 只证明该端应用流程完成；不替代真实客户端枚举。模块状态包含应用提交、文件摘要、启用集合和备份位置。不变的同版本同步不创建新备份。

tests/e2e.py 使用真实 Git 双 checkout；tests/module.py 验证单一源、设备范围、资源删除、凭据保留、漂移拒绝、失败回滚及旧 Hook 定向退出。Windows 原生和 Linux 实机验证分别记录，不用平台探针替代完整链路。
