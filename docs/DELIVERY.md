# 单一适配器路径与残留清理交付

日期：2026-09-23。此记录替代 2026-09-09 的四端统一交付；旧记录保留在 Git 历史。

## 程序

CLI 0.3.0 删除 skillstow.toml 的包/工具/variant 投影层（plan.rs、link.rs 及配置模型）。Rust 由 1052 行降到 529 行，本机配置只剩 repo、device、module_adapter。校验、影响分析和应用统一经本机适配器，不再有 before_publish/after_apply 钩子。后台同步在无本地修改、无远端更新且已应用时静默退出：HomeServer 的 sync.log 原来每分钟约 43 行，改后 130 秒内零增长。

适配器同时修复并精简：
- Skill 或资源退出本端时清掉空目录。此前留下的空目录，正是各端客户端目录里空壳的来源。
- 移除遥测命令后，一并清掉变空的 Hook 分组和遥测说明。
- apply 前核对本机平台。
- 全新设备无需 --adopt。
- 删除旧 runtime 迁移分支。

验证：
- Windows 原生：cargo fmt/clippy 通过；e2e 14 项（跳过 1 项符号链接权限）、单元 13 项（跳过 1 项 Unix 模式）通过。
- Linux 实机（HomeServer，二进制在 Windows 以 rust-lld 交叉编译为静态 musl）：e2e 14 项、单元 13 项全部通过，没有跳过。

## 内容

内容提交 e55daa9 由 Windows 经 edit begin/finish 发布：engineering 的维护 Hook 退出 SkillStow 应用链（删除 bind_sync 与 after-apply），改为每端一次性 install；3 个文件，新增 5 行、删除 89 行。HomeServer 与 Shenzhen 由各自后台任务自然接收，未手工触发。

## 逐端状态

| 设备 | 程序 | 收据 | 清理 |
| --- | --- | --- | --- |
| Windows | 0.3.0 | e55daa9，applied=true；计划任务最近返回 0 | 16 个空 Skill 目录、skills.old、旧 runtime 脚本、迁移快照、构建目录、packages 链接、sync.json |
| HomeServer | 0.3.0 | e55daa9，applied=true | 7 个空目录、.projections/.catalog/.runtime、旧脚本、构建目录、旧状态、17MB 日志、遥测 Hook 空壳、悬空 glm-agent 链接、packages 链接、sync.json |
| Shenzhen | 0.3.0 | e55daa9，applied=true | 6 个空目录、.projections/.catalog/.runtime（含退役 luna-vision-worker 凭据，已随备份保留）、旧脚本、构建目录、旧状态、packages 链接；遥测 Hook 空壳由新适配器自动清除 |
| Mac | 0.2.0 | 未查询：Mac 不接受 SSH | 见 HANDOFF 待办一 |
| plasma-fes | 0.2.0 | 离线 | 见 HANDOFF 待办二 |

删除前各端都打包到 ~/.local/state/skillstow/backups/cleanup-20260923*.tar.gz；Shenzhen 的包权限为 600。

客户端发现：Windows 与 HomeServer 用 tests/client_discovery.py 启动 Codex app-server，skills/list 分别准确枚举 9 个与 8 个个人 Skill，错误为 0；没有发送模型任务。已有会话要重新读取才算加载新内容。
