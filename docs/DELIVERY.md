# 四端统一模块交付

日期：2026-09-09。此记录替代 2026-09-06 的三设备阶段；旧记录保留在 Git 历史。

## 结果与归属

私人内容仓 HCID274/skills 只登记一个 personal-skill-system 模块。system/manifest.json 明确源位置与设备范围；四端持有完整 checkout，共享 Skill 的规范源只有一份，设备专属源也在同一仓。客户端只安装适用内容。

共同规则明确：对整个体系优先删减，必要时再补；定位、分发、校验和状态查询优先用程序；影响目标、范围、验收、授权或关键取舍的歧义先复述对齐。规则从同一源生成 Codex AGENTS.md，并由 Claude CLAUDE.md 导入本机应用后的同一正文。

| 源范围 | Skills | 应用设备 |
| --- | --- | --- |
| 单一共享源 | engineering、decision-grade-reporting、personal-tools、skillstow-maintain | 四端 |
| Mac 专属源 | mac-ops | Mac |
| Windows 专属源 | windows-automation | Windows 原生账户 |
| HomeServer 专属源 | host-ops | HomeServer |
| 深圳专属源 | panclilocal | Shenzhen |

最终共 8 个个人 Skill 源，每端 5 个、7 个内容文件。Mac 原生 Codex 枚举的个人条目由 45 降为 5；这不是总插件数或实测 Token 数。退出旧树、LRU、SQLite 遥测和原调用 Hook，保留凭据、宿主 .system 与第三方插件。

## 内容发布与逐端应用

内容 main 最终提交 aa5ce833a8b21d85a9d955aa248a6ac8d99af904 已 push。相对改动前 eea566702b0849eba234b6a5ac0a3eb69b8fc2e5，981 文件变更，新增 248 行、删除 101310 行；统计包含旧多设备副本、脚本与历史资源，不能等同模型上下文删减。最终内容仓 15 个跟踪文件，其中模块 12 个。

真实双向链路逐一验证：Mac 发布 3da55e7、HomeServer 发布 4ca55b7、Shenzhen 发布 7ff578d、Windows 发布 e4b5d83，每次其他三端均收到对应内容。最后 Mac 删除临时验证文件，另外三端由各自后台任务接收最终版本，未手工触发接收。

| 设备 | 程序 | 最终收据 | 后台实机证据 |
| --- | --- | --- | --- |
| Mac | 0.2.0 | aa5ce83，applied=true | launchd，60 秒，最近退出 0 |
| Windows | 原生 0.2.0 | aa5ce83，applied=true | SkillStowSync 计划任务，60 秒，LastTaskResult=0 |
| HomeServer | Linux 0.2.0 | aa5ce83，applied=true | 用户 crontab，60 秒；自动接收最终提交 |
| Shenzhen | Linux 0.2.0 | aa5ce83，applied=true | systemd 用户 timer，60 秒；服务后续执行退出 0 |

四端工作区干净、无编辑标记、临时验证文件不存在；逐文件 SHA-256 与模块状态一致，全局正文一致。已安装适配器 SHA-256 均为 4f0d34d5d6cd5984a50fa1d32fbbaf19bd165dbb7efd37b32d9b0cce0eafa1ea。Mac 的 fleet 实查四端均 reachable=true，收据为同一最终提交。

Windows 已配置本机仓库专用可写 GitHub deploy key；秘密未进入仓库。初次检出产生的纯换行差异保留于本机备份后重新检出，后续统一 LF。首次接管后四端移除日常 --adopt，避免重复迁移。深圳收据查询使用已验证的原 SSH 公网端点；其 Tailscale 22 端口此次不可达，不影响设备各自通过 GitHub 同步。

## 验证和边界

- 每个平台执行真实 Git 集成测试 17 项及模块测试 12 项。Mac、HomeServer、Shenzhen 全部通过；Windows 27 项通过，2 项因 Unix 文件模式或符号链接权限跳过，其 junction、资源、迁移与发布链路通过。
- cargo fmt --check、cargo clippy -- -D warnings、git diff --check 通过；8 个入口通过 skill-creator 格式校验。Mac 最后复核明确使用已安装的 release 0.2.0；遗留旧 debug 二进制不作为候选版本。
- 四端启动新的 Codex app-server，通过原生 skills/list 枚举到准确 5 个个人 Skill，错误为 0。HomeServer 与 Windows 的 Claude 原生控制协议也返回相同 5 个个人命令。验证未发送模型任务。
- Mac、Shenzhen 未找到 Claude CLI，只验证共享目录和全局导入落盘；不能声称这两端 Claude 已实际加载。Windows 范围为原生账户，不包括 WSL。
- 文件已同步不会清空已有会话上下文；新任务读取新规则，已有任务需要实际重读。旧内容可从 Git 历史或本机逐文件迁移备份恢复。

程序源码与内容分别发布。程序开发分支为 codex/unified-skill-module，运行版本已独立部署四端；代码合入主分支以对应 PR 状态为准，不以内容 main 推断代码已合并。
