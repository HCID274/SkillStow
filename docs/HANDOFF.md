# 当前交接

更新：2026-09-09。

用户最新要求见 REQUIREMENTS.md；程序契约见 SPEC.md。当前工作把三套完整副本与 Windows 旧机制收敛为单一精简模块。

程序仓为 HCID274/SkillStow；私人内容仓为 HCID274/skills。每端维护仓位于用户目录 .local/share/skillstow/workspace，客户端活动目录不是编辑入口。

内容入口：system/manifest.json 指定源与设备范围；共享内容在 system/shared/，专属内容在 system/devices/。一个 personal-skill-system 包覆盖四端，日常使用 locate、edit begin、impact、edit finish、fleet。

代码修改通过普通 Git；内容修改通过 SkillStow 维护流程。每次程序升级要更新各端二进制与本机适配器，源码 push 不代表设备已升级。部署与验收结果见 DELIVERY.md 中最新记录。

不要恢复旧 Hub、审批平台、LRU、统计 Hook、全量 Skills 加载或设备副本维护方式。旧历史文件用于追溯，不覆盖最新范围。
