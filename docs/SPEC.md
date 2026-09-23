# SkillStow 行为契约

更新：2026-09-23，CLI 0.3.0。

## 职责划分

CLI 只负责 Git 事务、编辑标记、后台静默窗口、收据和调用本机模块适配器。Skill 清单、设备范围、校验、影响分析和落盘全部由适配器 migration/skill_module.py 解释；CLI 不读取内容仓的清单格式，也不执行内容仓中的任意脚本。

本机 config.toml 只有三项：

```toml
repo = "~/.local/share/skillstow/workspace"   # 维护仓，main 分支完整 checkout
device = "windows"                            # manifest.json 中的设备名
module_adapter = ["python3", "-X", "utf8", "~/.local/share/skillstow/skill_module.py"]  # 本机安装的适配器 argv，路径写绝对路径
```

CLI 调用适配器时追加 `--repo <目录> <子命令>`：发布前后对维护仓运行 validate 和 impact；应用时对已发布 worktree 运行 `apply --device <本机>`；locate、fleet 透传。

## 发布与应用

维护仓是 main 上的完整内容 checkout；配置目录下的 published 是独立 Git worktree，只检出已发布提交。顺序为 fetch、校验、提交、rebase、再次校验、影响分析、push、确认远端包含提交、应用、收据。冲突保留现场，不强推、不默认丢弃任一端。

edit begin 先对账并持久暂停本机后台发布；edit finish 发布完成后解除标记。cancel 保留修改并继续暂停。宿主每分钟调用 sync --background：编辑中只输出暂停；有未提交修改时等内容稳定 60 秒再发布；无本地修改、无远端更新且收据已应用当前提交时静默退出，不再运行适配器。离线设备不阻塞发布。

已授权删除或范围收缩在发起端使用 --approve-removals；接收端不重复询问。status 只使用最近 fetch 信息；其他设备结果看 fleet 或实机收据。

## 统一模块

私人内容仓的 system/manifest.json 是唯一清单：version、devices（平台、SSH 端点，可选 global_rules 与 projects）、skills（源目录及适用设备或所属项目）。共享源在 system/shared/，设备专属源在 system/devices/，项目专属源在 system/projects/；每端完整 checkout，应用阶段按清单筛选。

- locate ID：输出该 Skill 的源路径、设备范围和清单路径。
- impact：对比最近 fetch 的 origin/main，输出受影响 Skills、设备及删除/替换状态，含未跟踪新资源；删除或替换返回 3，CLI 转为授权检查。
- fleet：并发只读查询各端收据；失败显示未知和上次确认时间。凭据来自各机 SSH 配置，不进清单。
- validate：核对清单、设备、入口和资源；未知范围、链接或外逸路径拒绝发布。
- apply：先核对本机平台与清单一致，再复制到 .codex/skills，并把 .agents/skills 与 .claude/skills 链到该目录（Windows 用 junction，Unix 用软链）。资源或 Skill 退出本端时同时清掉留下的空目录。
- 项目范围：设备的 projects 把项目名映射到本机绝对路径；Skill 用 project 代替 devices，只应用到登记该项目的设备，落到 <项目>/.agents/skills，并把 <项目>/.claude/skills 链到该目录，不进入全局 .codex/skills。收据键以 @项目 开头并记录项目路径；项目退出或路径变更按删除/替换授权，并清掉旧位置。项目目录不存在时应用失败；旧投影链接只替换链接自身；已接管文件被 git clean 清掉时直接补回。

全新设备本机没有 .codex/skills 时直接应用；已有个人内容时首次接入须显式 apply --adopt，核查后接管。修改前逐文件备份，检测到外部修改时停止；失败按本次日志回滚，不递归删除目录链接目标。凭据、.system 和其他非受管内容保留。

共用全局规则由模块提供：Codex AGENTS.md 是程序生成的本机副本，Claude CLAUDE.md 引用同一正文；设备 global_rules 仅追加到该设备入口。旧会话不因文件已写入自动算已重载。模块不运行 LRU、SQLite 遥测或调用 Hook；应用时移除旧 Skills 遥测 Hook 及其留下的空分组，保留其他客户端设置。

## 返回与验证

CLI：0 为成功或正常等待，1 为 status 未同步，2 为失败（含本机应用失败）。receipt.toml 中 applied=true 只证明该端应用流程完成，不替代真实客户端枚举。不变的同版本应用不创建新备份。

tests/e2e.py 使用真实 Git 双 checkout 和真实适配器；tests/module.py 验证单一源、设备范围、项目范围、资源删除、凭据保留、漂移拒绝、失败回滚和遥测 Hook 退出。Windows 原生与 Linux 实机分别运行。
