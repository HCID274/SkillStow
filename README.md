# SkillStow

用一个 Git 仓维护个人 Skills，从任意设备发布，由程序按清单应用到适用设备。

支持 Mac、Windows 和 Linux。私人体系可作为一个统一模块：共用 Skill 只有一份源，设备专属内容也入仓，各端保留完整维护仓，客户端只使用本端启用的内容。

```sh
skillstow --config ~/.config/skillstow/config.toml locate engineering
skillstow --config ~/.config/skillstow/config.toml edit begin
# 修改返回的维护仓中的相关源文件
skillstow --config ~/.config/skillstow/config.toml impact
skillstow --config ~/.config/skillstow/config.toml edit finish -m "说明"
skillstow --config ~/.config/skillstow/config.toml fleet
```

Windows 使用本机安装的 skillstow.exe 和对应用户目录。凭据留在本机；Git 发布和设备应用分别报告。程序定位、同步和校验，不要求模型全量读取或逐端判断。

详见 [当前契约](docs/SPEC.md)、[需求](docs/REQUIREMENTS.md) 和 [交接](docs/HANDOFF.md)。

验证：cargo build --release；SKILLSTOW_BIN=target/release/skillstow python3 tests/e2e.py；python3 tests/module.py；cargo clippy -- -D warnings；cargo fmt --check。
