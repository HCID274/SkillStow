# 当前交接

更新：2026-09-23。

用户最新要求见 REQUIREMENTS.md；程序契约见 SPEC.md；最近交付见 DELIVERY.md。

程序仓为 HCID274/SkillStow；私人内容仓为 HCID274/skills。每端维护仓位于用户目录 .local/share/skillstow/workspace，客户端活动目录不是编辑入口。内容入口是 system/manifest.json；日常使用 locate、edit begin、impact、edit finish、fleet。代码修改走普通 Git；内容修改走 SkillStow 维护流程。程序升级要逐端更新二进制与适配器，源码 push 不代表设备已升级。

## 升级步骤（Mac 已于 2026-09-23 完成，详见 DELIVERY.md）

以下路径以 Mac 为例，其他设备换成本机用户目录与解释器。

1. 先看现场：`skillstow --config ~/.config/skillstow/config.toml status`、`cat ~/.config/skillstow/config.toml`、`ls -a ~/.codex/skills ~/.local/share/skillstow ~/.local/state/skillstow`。如果 editing=true 或 local_changes=true，先停下来问用户，不覆盖未发布修改。
2. 取代码：沿用 Mac 上已有的 SkillStow 克隆（`git remote -v` 指向 HCID274/SkillStow）；没有就克隆到惯用源码目录。更新到 main，确认 Cargo.toml 为 0.3.0。
3. 验证：`cargo fmt --check`、`cargo clippy --release -- -D warnings`、`cargo build --release`、`SKILLSTOW_BIN=target/release/skillstow python3 tests/e2e.py`、`python3 tests/module.py`。macOS 应全部通过，不跳过。没有 cargo 时先问用户是否安装 rustup，不找别的二进制替代。
4. 安装：等 `~/.config/skillstow/sync.lock` 消失后，`install -m 755 target/release/skillstow ~/.local/bin/skillstow`，`install -m 644 migration/skill_module.py ~/.local/share/skillstow/skill_module.py`。
5. 配置：把 `~/.config/skillstow/config.toml` 改成只有三项。解释器沿用原 module_adapter 中的 Python（需要 3.11 及以上），路径写绝对路径：

   ```toml
   repo = "/Users/daolin/.local/share/skillstow/workspace"
   device = "mac"
   module_adapter = ["<原解释器>", "-X", "utf8", "/Users/daolin/.local/share/skillstow/skill_module.py"]
   ```

6. 退役旧机制：删除 `~/.local/share/skillstow/packages/personal-skill-system` 链接（只删链接）和空的 packages 目录；删除 `~/.config/skillstow/pending.md`；删除 `~/.local/state/codex-maintenance/sync.json` 和同目录的 `skillstow-*.toml`，保留其他状态和 hooks 备份。
7. 清残留：先打包到 `~/.local/state/skillstow/backups/cleanup-<日期>.tar.gz` 并 `chmod 600`，再删除。
   - `~/.codex/skills` 下没有 SKILL.md 且没有文件的空目录；`.projections`、`.catalog`、`.runtime`（其中凭据文件随包备份）。
   - `~/.local/share/skillstow` 下除 skill_module.py 和 workspace 以外的旧脚本、`*.before-*` 备份和 build-unified。
   - `~/.local/state/skillstow/runtime.json`、`global-entry-backups`、一次性审计记录；`~/.claude/skills.old-*`。
   - `~/.local/bin` 中指向维护仓或已不存在目标的悬空链接。
   - 删除前用 `find ~ -xdev -type l` 确认没有外部链接指向要删的目录；项目目录的 .agents/.claude 若引用 .projections，先把这些项目 Skill 按项目范围登记到清单并发布。`.system`、插件、凭据以外的非受管内容保留。
8. 验收：`skillstow --config ~/.config/skillstow/config.toml sync` 输出 application=applied；`status` 返回 0；紧接着 `sync --background` 无输出；`~/.config/skillstow/receipt.toml` 的 commit 等于 origin/main。等一分钟，确认 launchd 后台运行后收据仍是 applied=true，`~/.local/state/skillstow/sync.log` 不再每分钟增长（旧日志可先存档再清空）。`~/.codex/hooks.json` 中遗留的遥测空分组由新适配器在应用时自动清掉。
9. 回报：按 decision-grade-reporting 给短回执，写明删除清单、备份位置、收据提交和验收输出。

## 待办二：plasma-fes（下一任务）

plasma-fes 离线，仍是 0.2.0。先解决连通性，再按上面升级步骤第 4 至 8 步升级；Linux 静态二进制按 README 的交叉编译命令构建。

它升级到 0.3.0 前，内容仓根目录的 skillstow.toml 必须保留：0.2.0 发布和应用时仍会读取它，新版本已不再使用。清单已含 project 项，plasma-fes 的旧适配器会拒绝新清单，恢复连通后在升级前收据会是 applied=false；装上 0.3.0 与当前适配器后恢复。全部设备升级后，用 edit begin/finish 删除内容仓的 skillstow.toml，此后清单只剩 system/manifest.json。

不要恢复旧 Hub、审批平台、LRU、统计 Hook、全量 Skills 加载或设备副本维护方式。
