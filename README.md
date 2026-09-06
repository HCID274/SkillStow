# SkillStow

个人 Skills 的多设备 Git 同步。每台机器保留同一私有仓库的完整 checkout，可以维护任意设备的 Skills 与资源；已发布内容按设备清单应用。

现已接入 Mac、HomeServer、Shenzhen。Windows 接入按用户要求暂缓。当前部署和实测结果见 [交付记录](docs/DELIVERY.md)，行为契约见 [SPEC](docs/SPEC.md)。

在本目录开启新对话时，从 [AGENTS.md](AGENTS.md) 和 [交接状态](docs/HANDOFF.md) 继续；[已确认需求](docs/REQUIREMENTS.md) 与 [当前待办](docs/TASKS.md) 均已保存在本仓，无需旧 SkillRiver 目录。

## 日常维护

已接入设备可直接让 AI 使用 `skillstow-maintain`。本次安装路径为 `~/.local/bin/skillstow`，配置为 `~/.config/skillstow/config.toml`。

```sh
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml edit begin
# 只编辑返回的维护仓；systems/<device> 保存各设备的完整 Skills 体系。
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml impact
~/.local/bin/skillstow --config ~/.config/skillstow/config.toml edit finish -m "说明修改"
```

冲突先解决，再完成发布。编辑期间后台暂停。删除/版本替换经发起端授权后使用 `--approve-removals`，接收端不重复确认。`status` 显示本机状态；其他设备是否已应用需核对其实际收据。

## 开发验证

```sh
cargo build --release
SKILLSTOW_BIN=target/release/skillstow python3 tests/e2e.py
cargo clippy -- -D warnings
```

`migration/` 是现有私人 runtime 的专用导出、验证、应用及定时器适配器；普通独立 Skills 包无需该适配器。

旧 SkillRiver 已退出实现基线。历史决策保留在 docs/REPLAN.md，当前契约以 docs/SPEC.md 为准。
