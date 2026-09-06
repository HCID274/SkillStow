# 新对话交接

更新：2026-09-06。本仓包含后续开发所需的需求、契约、验收记录和历史决策，无需读取旧 SkillRiver 目录或旧对话。

## 当前到哪一步

同步主功能和现有 runtime 适配器已实现，Mac、HomeServer、Shenzhen 已部署，三端均实际发起过维护并由其他端接收。Windows 按用户要求暂缓。下一步按用户提出的具体问题继续维护；不要重新执行首次接管或恢复旧项目架构。

本次代码按四批中文提交整理在 `codex/skillstow-delivery`：同步 CLI 与集成测试、runtime 迁移与测试、行为契约与三设备证据、新对话交接与当前开发约定。原单提交分支 `codex/device-skill-packages` 保留作历史参照。交付采用开发分支和草稿 PR，尚未合并 main；后续以实际 Git/PR 状态为准。

代码、迁移脚本和测试与三设备已验收候选 `9b89299` 相同，分批仅改变提交组织，新增修改为项目文档。原候选不是私有内容仓的提交。

## 两个仓库不要混淆

| 用途 | 位置 |
| --- | --- |
| 当前代码仓 | GitHub `HCID274/SkillStow`；当前 Mac 为 `/Users/daolin/Documents/HCID274/Code/Own/SkillStow` |
| 私人 Skills 内容仓 | GitHub 私有仓 `HCID274/skills`，三端维护 checkout 均为 `~/.local/share/skillstow/workspace`，分支 main |
| 设备完整内容 | 内容仓 `systems/mac`、`systems/homeserver`、`systems/shenzhen`；共享注册表 `skillstow.toml` |

这里的 `~` 指命令执行设备的 home。代码仓的提交/push 不会自动升级三台设备的已安装程序；个人 Skills 的发布由 SkillStow 完成。

## 已安装位置与操作入口

三端均使用：

- CLI：`~/.local/bin/skillstow`；配置：`~/.config/skillstow/config.toml`。
- 已发布 Git worktree：`~/.config/skillstow/published`；收据与 pending 位于同一配置目录。
- 运行中的私人 Skills：`~/.codex/skills`；不要直接编辑。
- 本机适配器：`~/.local/share/skillstow/apply_runtime.py` 和 `validate_runtime.py`。
- 应用状态：`~/.local/state/skillstow/runtime.json`；文件备份：`~/.local/state/skillstow/backups/`。

日常让 AI 使用 `skillstow-maintain`。CLI 显式带配置路径，避免 Mac 默认配置目录不同造成误用：

```sh
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml status
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml edit begin
# 修改命令返回的维护仓；明确针对哪个设备或共享版本。
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml impact
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml edit finish -m "中文变更说明"
```

存在编辑标记时先检查原任务，不再重复 begin；解决 Git 冲突并完成 rebase 后重跑 finish。cancel 保留修改且后台继续暂停。不要通过删标记、force push 或盲选 ours/theirs 绕过未完成任务。
若活动目录发生漂移，把应保留的修改合并回维护仓，再发布；需要回退已发布内容时优先在维护仓 revert 后正常发布。

## 设备运行与连接

| 设备 | 后台机制 | 维护连接与注意事项 |
| --- | --- | --- |
| Mac | launchd `com.hcid274.skillstow`，60 秒 | GitHub 使用已登录 gh 的 HTTPS 凭据；SSH 22/443 曾间歇超时 |
| HomeServer | 用户 crontab，标记 `# skillstow-sync`，每分钟 | SSH 别名 `HomeServer`；GitHub 使用仓库专用 deploy key；无需重做 sudo/linger 配置 |
| Shenzhen | systemd 用户 `skillstow.timer`，60 秒 | Mac 登录使用 `ssh -J HomeServer Shenzhen`；GitHub 使用设备已有身份 |

HomeServer 跳转只用于登录 Shenzhen。内容传播链为各设备分别连接 GitHub；真实 HomeServer → GitHub → Shenzhen 及 Shenzhen → GitHub → Mac/HomeServer 均已验收。
后续网络变化先诊断已有连接与凭据，不把 SSH 中转改成内容同步依赖。

2026-09-06 的三设备最后共同验收内容提交为 `531530385730f28853ccbe5f0f10fd11c4a33a4d`，各自收据均 applied=true。该值是历史验收锚点；排障先查询当前状态，不要求设备回退到这个提交。详细证据见 [DELIVERY.md](DELIVERY.md)。

## 如何继续验证和升级

```sh
cargo build --release
SKILLSTOW_BIN=target/release/skillstow python3 tests/e2e.py
cargo clippy -- -D warnings
cargo fmt --check
git diff --check
# 已有私人 Mac 内容仓时，在隔离副本中验证适配器：
python3 tests/runtime_migration.py ~/.local/share/skillstow/workspace/systems/mac
```

15 项真实 Git 集成测试已分别在三台设备通过；原 Mac runtime 的 36 项测试、隔离迁移测试及实际 Codex Skills 枚举均已通过。Claude 投影保留，但未取得本轮 Mac Claude CLI 的实际验收证据。
只调整提交组织或文档时复用已有功能证据，检查内容一致性与文档链接。实际修改程序或适配器后，补相关测试，并显式更新目标设备安装文件、核对版本和应用收据；推送源代码不等于完成部署。

Windows 接入时先读取 [PLATFORM_NOTES.md](PLATFORM_NOTES.md) 的历史 junction 探针，再核对当前 Windows 环境、Python/runtime 的 Unix 依赖、后台执行身份和目录共存方式。在隔离内容上通过完整资源、删除保留目标、冲突恢复、后台及真实客户端识别验收后，再接入私人内容。

## 文档导航

- [REQUIREMENTS.md](REQUIREMENTS.md)：用户已确认的结果和方案取舍。
- [SPEC.md](SPEC.md)：当前可执行契约；[TASKS.md](TASKS.md)：完成范围与剩余事项。
- [DELIVERY.md](DELIVERY.md)：实机与测试证据；[CONTRIBUTING.md](../CONTRIBUTING.md)：开发边界。
- [REPLAN.md](REPLAN.md)、[SPEC-20260821.md](SPEC-20260821.md)、[TASKS-20260821.md](TASKS-20260821.md)：历史资料，不作为当前待办或新增审批条件。

新对话可直接说：“先阅读 AGENTS.md 和 docs/HANDOFF.md，沿用已确认需求，继续处理……”。
