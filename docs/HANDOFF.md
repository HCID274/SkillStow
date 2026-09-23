# 当前交接

更新：2026-09-23。

用户最新要求见 REQUIREMENTS.md；程序契约见 SPEC.md；最近交付见 DELIVERY.md。

程序仓为 HCID274/SkillStow；私人内容仓为 HCID274/skills。每端维护仓位于用户目录 .local/share/skillstow/workspace，客户端活动目录不是编辑入口。内容入口是 system/manifest.json；日常使用 locate、edit begin、impact、edit finish、fleet。代码修改走普通 Git；内容修改走 SkillStow 维护流程。程序升级要逐端更新二进制与适配器，源码 push 不代表设备已升级。

## 已完成：Mac 升级到 0.3.0

2026-09-23 在 Mac 本机完成，并新增项目范围，详见 DELIVERY.md。升级其他设备时沿用以下步骤：先看现场，edit/local_changes 为 true 就停下；构建并跑完测试；安装二进制与适配器；配置只留 repo、device、module_adapter；删除 packages 链接、pending.md、codex-maintenance 下的 sync.json 与 skillstow-*.toml；残留先打包再删。删 .projections/.catalog 前先用 `find ~ -xdev -type l` 查项目目录里的 .agents/.claude 链接，有引用就先按项目范围登记到清单。

## 待办二：plasma-fes（下一任务）

plasma-fes 离线，仍是 0.2.0。先解决连通性，再按待办一第 4 至 8 步升级；Linux 静态二进制按 README 的交叉编译命令构建。

它升级到 0.3.0 前，内容仓根目录的 skillstow.toml 必须保留：0.2.0 发布和应用时仍会读取它，新版本已不再使用。清单已含 project 项，plasma-fes 的旧适配器会拒绝新清单，恢复连通后在升级前收据会是 applied=false；装上 0.3.0 与当前适配器后恢复。全部设备升级后，用 edit begin/finish 删除内容仓的 skillstow.toml，此后清单只剩 system/manifest.json。

不要恢复旧 Hub、审批平台、LRU、统计 Hook、全量 Skills 加载或设备副本维护方式。
