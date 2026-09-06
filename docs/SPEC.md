# SkillStow 当前行为契约

2026-09-06。用户已确认从旧 SkillRiver 转到 SkillStow 实现，保留本轮多设备需求。
旧契约保存在 [SPEC-20260821.md](SPEC-20260821.md)，历史原因见 [REPLAN.md](REPLAN.md)。

## 范围

个人 Mac、Windows、Linux 共享一个 GitHub 私有数据仓库。任何设备都拥有全部内容并可维护任意设备。
当前实机范围为 Mac、HomeServer、Shenzhen；用户暂缓 Windows 接入。

不再恢复 SkillRiver 的 Hub、签名、PR 审批协议、网站和服务端。发布采用普通 Git main，冲突由维护 AI 解决。
不是把旧 80,886 行代码逐步复活，也不对一般 Skill 改写内容。

## 两个目录

- 维护仓：用户克隆的完整数据仓，必须位于 main；唯一编辑入口。
- 配置目录下的 `published/`：由 Git worktree 管理的已发布副本。工具目录链接到它，未发布的修改不会暴露给工具。

同步顺序：在线 fetch → 校验本地包 → 提交修改 → rebase origin/main → 再校验 → 影响分析和必要确认 → push → 验证 main 包含提交 → 更新 published → 应用本机 → 收据。
只有远端前进引起拒绝时最多重新对账两次。冲突保留现场，不自动 abort、force push 或选择 ours/theirs。

## 数据清单

`skillstow.toml` 是共享真相。所有设备都能编辑它。以下是独立包示例：

```toml
[tools.codex]
path = "~/.codex/skills"
[skills.review]
requires = []
[skills.review.variants.common]
path = "skills/review/common"
[skills.review.variants.home]
path = "skills/review/home"
platform = "linux"
device = "home"
[devices.mac]
platform = "macos"
enabled = ["review"]
[devices.home]
platform = "linux"
enabled = ["review"]
# 可选精确选择，仍检查平台和设备兼容性。
[devices.home.variants]
review = "home"
```

版本选择为设备优先、平台其次、通用最后；同层歧义失败。enabled 加上传递依赖决定本机内容。
每个包必须有 SKILL.md；附属文件全部随目录同步。禁止外逸路径、目录重叠、包内链接、特殊文件、已跟踪 submodule、Windows 保留文件名和包内大小写冲突。被 gitignore 遗漏的包内资源阻止发布。
发布校验所有已登记设备，不仅校验当前设备。依赖循环在设备解析时失败。

现有私人体系共用 runtime：首次迁移按 `personal-skill-system` 的三个设备版本完整封装，保留每台设备的 `.runtime/manifest.json`、overlay 和资源。体系内逐项启用关系继续由该设备的 runtime 清单维护，避免首轮拆散依赖。
可独立的 Skill 仍可单独注册成上例的包。无需把完整体系强行拆成几十个相互依赖的小包。

## 本机配置

CLI 支持 `--config <path>` 和 `SKILLSTOW_CONFIG`；本次部署统一显式使用 `~/.config/skillstow/config.toml`。
不指定时走操作系统配置目录，Mac 为 Application Support，Linux 为 XDG config，Windows 为 APPDATA。

```toml
repo = "~/skills"
device = "home"
tools = ["codex"]
before_publish = []
after_apply = []
[overrides]
codex = "~/.codex/skills"
```

repo、工具绝对路径、before_publish 和 after_apply 是本机配置，不进入内容仓。两种钩子都是可选的 argv 数组；before_publish 在提交前及 rebase 后校验候选，after_apply 在发布后应用本机内容。钩子，通过直接启动程序执行，不经过 shell；仅放本机明确安装的适配器，不自动执行仓库内脚本。
完整旧式 runtime 的适配器为 `migration/apply_runtime.py`：保留凭据、插件、缓存和状态，备份实际变化，验证并刷新原有投影；检测到活动副本被另行修改时停止，要求先合并回维护仓。

## 命令

```text
init --repo <已有本地 checkout> --device <id> --tools codex
sync [-m 说明] [--background] [--approve-removals]
status
impact
edit begin
edit finish [-m 说明] [--approve-removals]
edit cancel
```

init 不覆盖已有配置。克隆、凭据配置直接使用 Git/SSH。

edit begin 先同步，再记录持久编辑标记并返回路径；已有任务则继续原任务。编辑期间后台不发布，普通 sync 也不绕过标记，使用 edit finish 显式结束。失败保留标记，解决后重跑 finish。cancel 保留修改且维持后台暂停。

每次同步通过一个 create_new 锁文件互斥；进程被强杀后，确认进程已退出再移除遗留锁。没有自建文件系统事务或自动恢复引擎。

后台由宿主定时器（Mac launchd、Shenzhen systemd、HomeServer crontab）每 60 秒调用 sync --background。内容连续稳定至少 60 秒才提交；等待时返回 0，编辑标记存在时也安静退出。后台不携带删除批准。

impact 对比最近 fetch 的 origin/main 与候选，列出受影响设备；同步提交并 rebase 后重新计算。设备移除、版本替换、所选包内文件删除都要求发起端明确 `--approve-removals`。已有具体用户授权可以直接使用该参数。接收方不再次确认已发布变更。
这是本人的 CLI/AI 工作流约束，GitHub 分支本身未设置签名或强制 CI 防绕过协议。

## 应用与报告

非受管文件、目录和外部链接不覆盖，记录 pending.md。隐藏的宿主目录不管理。
Unix 使用目录软链；Windows 使用 junction，删除时只删除链接本身。Windows 整条同步链尚待实机验收。

返回值：0 = 本机完整成功或后台正常等待；1 = 存在应用阻塞/状态不一致；2 = 操作失败。
错误保留 Git 原始输出。失败后不伪报设备已应用。

receipt.toml 记录实际提交与本机应用结果；status 只读，使用最近 fetch 的远端信息。
其他设备没有返回证据时必须报告 unknown，不能从一次 push 推测它们已同步。定时器使在线设备主动补齐；离线设备不阻塞发布。

## 验证

`tests/e2e.py` 使用真实 bare 仓和两个 checkout，验证完整资源、设备版本、跨设备维护、冲突恢复、编辑隔离、删除确认、资源遗漏和失败收据。
`tests/runtime_migration.py` 使用真实 runtime 包的隔离副本，验证迁移、重复应用、凭据保留和漂移保护。
实际接入与运行证据见 [DELIVERY.md](DELIVERY.md)。
