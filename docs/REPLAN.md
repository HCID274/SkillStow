# skillstow 重规划决策日志

> 本项目原名 **SkillRiver**，2026-08-21 更名为 **skillstow**（见 D28）。

状态：**决策已定稿**（grill-me 访谈 7 轮，2026-08-21，D1–D27 全部确认）
用途：这是"我上次想到哪了"的唯一记录。下次回来先读这份文件。
注意：本文记录的是**决策**，不是实现。所有待办在第四节，决策全部定完之前不动手写代码。

---

## 一、为什么要重规划（2026-08-21 的现场证据）

代码规模和问题规模差了三个数量级：

```
首次提交    2026-08-08（13 天）
提交数      104
Rust 代码   80,886 行，18 个 crate/app
未提交      57 个文件 +14,858/-10,587，另有 64 个未跟踪条目
cargo check 通过（不是编译坏了）
```

要同步的真实数据：`~/.codex/skills/` 916 KB，23 个 skill，全是 markdown。

最近 30 多个提交全部在修 Windows CI（NT 路径句柄、目录 rename 的 ACCESS_DENIED、
陈旧锁判定）。`crates/safe-fs` 有 3,273 行，用来安全地移动 916 KB 的 markdown。

`docs/V1_COMPLETION_BLUEPRINT.md` 的"剩余范围"仍包含 Hub HTTP、Web 控制台、
三平台服务化、真实 GitHub 验收、云验收——**80k 行写完之后，"两台机器上的 skill
真的同步了"这件事一次都没发生过。**

结论：项目不是烂在某个技术选择上，是烂在把"个人文件同步"当成"多用户分布式
控制平面产品"来做。

---

## 二、现状事实（重规划的输入）

布局（三种映射策略同时在用）：

```
~/.codex/skills/                 真身，23 个 skill，916 KB
~/.claude/skills/<name>          21 条软链，逐个链（可挑选）
~/.zcode/skills                  1 条软链，整目录链（全暴露）
~/.codex/prompts/pua.md          1 条软链（另一个表面：prompts ≠ skills）
~/.claude/skills/show-then-tell  真实目录，不是软链，codex 里没有
```

真实分歧只有 3 个，**且全部是"给哪个工具用"的分歧，不是"这个操作系统上要改写"**：

| skill | 分歧 |
| --- | --- |
| luna-vision-worker | codex 有，claude 没有 |
| playwright-interactive | codex 有，claude 没有 |
| show-then-tell | claude 有，codex 没有 |

平台相关内容：23 个 skill 里只有 6 个沾平台，其中只有 `md2hci` 是重度
（8 个文件，依赖 pandoc/typst 二进制）。而它的差异是"pandoc 装在哪"，
属于**环境配置**，不属于 skill 内容同步。

---

## 三、已定决策

| # | 议题 | 结论 | 定于 |
| --- | --- | --- | --- |
| D1 | 项目目的 | 自用优先 + 后续开源。先让它对自己真的有用，再谈别人。 | R1 |
| D2 | 真痛点 | 跨机器同步 + 历史回滚。单机多工具已被软链解决。四层 Profile 差异化砍掉。 | R1 |
| D3 | 平台 | 设计上支持 Windows。 | R1 |
| D4 | 旧代码 | **全删**。打 tag 归档，重新开始。 | R1 |
| D5 | 同步 vs 移植 | **分层**。传输层做死（确定性、幂等、可回滚，AI 一律不介入）；适配层做活（AI 交互）。**关键：AI 问出来的答案必须落成仓库里的一条规则，永久生效，不能每次重问。**AI 的角色是"规则采集器"，不是"每次的决策者"。 | R2 |
| D6 | 提示词粘贴通道 | 真实场景是"能 SSH 过去但每次很麻烦"（不是连不上、也不是不许装东西）。→ 见 Q9，本轮收口。 | R2 |
| D7 | 同步主轴 | **主轴是工具，不是操作系统。**一份真身 + N 个工具视图，每个工具的暴露策略可配置。OS 只影响"软链还是复制"这一个技术细节。 | R2 |
| D8 | 开源边界 | **开源机制，不开源 skill 内容。**但 v1 先硬编码自己的布局，配置项留成一个文件，先跑通再泛化。 | R2 |
| D9 | 提示词粘贴通道 | **砍掉。**它解决的是"麻烦"不是"不可能"，而且对面干了什么不可验证、退不回去。那个场景交给已有的 `oneshot-handoff-prompt` skill。 | R3 |
| D10 | 编辑权方向 | **对等 + 冲突甩给 git。**任何机器都能改，就是普通 pull/push，冲突了 git 报错、人来解决。工具不为冲突写一行代码。（老架构的 draft 分支/签名信封/CAS/三方合并/治理探针/PR 自动合并全部作废——它们服务的是一个一年发生零次的场景。） | R3 |
| D11 | 真身位置 | **独立的、只有 skill 的干净 git 仓库。**所有工具目录（含 codex）一律软链过去，codex 从"真身"降级为"又一个视图"，和 claude/zcode 平级。理由：codex 当真身是历史偶然，且 `~/.codex/` 混着 sessions/cache/tmp/sqlite 等运行时垃圾（提交 617741a 已被咬过一次）。 | R3 |
| D13 | 传输层 | **GitHub 私有仓**，三台机器都 clone。顺带解决历史回滚与异地备份。**sync = `git pull --rebase` + 按 manifest 刷新软链 + `git push`，冲突了就停下来报错让人处理。除此之外一行都不多。** | R4 |
| D14 | Windows 落地 | **Junction 为主（`mklink /J`），零提权。**启动时探测开发者模式，开了就用真软链。理由：23 个 skill 全是目录，Junction 覆盖 100% 主场景；要求陌生人开开发者模式是实打实的流失（对 D8 致命）。 | R4 |
| D15 | 投影形态 | **只支持目录投影。**一个 skill 一个目录，投给某工具就建一个目录链。整目录链退化为"这个工具全选"。单文件 prompt 投影（`~/.codex/prompts/pua.md`）不支持，手动维护。**格式转换明确禁止**——投影出去必须和真身逐字节相同，否则就要建"投影脏了没"的检测，老架构的 Bundle/Active 就是这么长出来的。 | R4 |
| D17 | 形态 | **组合**：薄 CLI（Rust，确定性部分）+ 一个 skill（`adapt`，交互部分）。选 Rust 的理由是 D8 要开源，单个可下载二进制是对陌生人最好的分发方式。 | R5 |
| D18 | 可见性规则 | **默认全给 + 例外排除。**manifest 只记例外（当前只有 3 行）。白名单被否决的理由是防绕过：每加一个 skill 都要编大表，编三次你就直接 `ln -s` 绕过工具，绕过一次工具就废了。 | R5 |
| D19 | 回滚 | **就是 git。**真身仓库 `git revert`/`checkout`，因为工具目录是软链，真身一变三个工具立刻全变，**不需要重新投影**。这是 D11 白送的——老架构需要 Bundle 是因为它选了"复制+组装"。 | R5 |
| D20 | v1 完成的定义 | **在两台真实机器上：Mac 改 `dlog/SKILL.md` 一行 → Windows 跑 sync → Windows 的 `~/.claude/skills/dlog/SKILL.md` 读到那一行，全程不超过两条命令。**在这条跑通前：不写 CI、不写安装包、不写 README、不写 LICENSE、不发布、不接第三台机器、不写 adapt。上次从第一天就在写英文 README / LICENSE / 三平台部署模板 / Web 登录页，而这条闭环一次都没跑通。 | R5 |
| D21 | 三条硬护栏 | **全部接受，写进新仓库 `CONTRIBUTING.md` 第一段。**(1) 禁止再写 `safe-fs`，文件操作直接 `std::fs`，出错就返回错误，不建事务层、不做原子替换、不碰 NT 路径。(2) 禁止 libgit2/gitoxide，所有 git 操作 shell out 给 `git` 命令。(3) 确定性部分 **1000 行硬上限**——这不是质量目标，是**绊线**：写到 1000 行就停下来重读本文，问"我是不是又在解决一个不存在的问题"。 | R6 |
| D22 | adapt 的职责 | **只有两件事，不加戏。**(1) 真身仓出现 manifest 没覆盖的新 skill → 问要不要排除某些工具；(2) 工具目录里发现仓库外的野生 skill → 问要不要收编。没有跨平台改写、没有内容适配、没有格式转换。它小到几乎不需要 AI，用 skill 做只是因为你本来就在 AI 里干活。 | R6 |
| D23 | 仓库结构与配置 | 真身仓 **根平铺**：skill 目录直接在仓库根，`skillstow.toml`（工具定义 + 例外表）也在根，格式 **TOML**。判断规则：**非隐藏、且含 `SKILL.md` 的目录才是 skill**，其余随便放。（原定 `skills/` 子目录已推翻——它和 D25 的 `~/skills` 撞成 `~/skills/skills/`，而子目录换来的好处是零：配置是文件、skill 是目录，撞不了；投影由 manifest 逐个驱动，根上的文件永远投不出去。）机器本地配置在 `~/.config/skillstow/config.toml`（Windows 走 `%APPDATA%`），**不进仓库**——本地配置进仓库，三台机器的路径差异就会变成 git 冲突；能不产生的冲突就别产生。本地配置只有三样：真身仓在哪、这台机器启用哪些工具、路径覆盖。 | R6 |
| D24 | 命令面 | **三条，一条不多。**`init [--import-from <dir>]` / `sync` / `status`。不加 `link`/`unlink`（多一条绕过 manifest 的路径，manifest 就不再是唯一真相，D18 废掉）；不加 `--dry-run`（`status` 就是）；不加 `rollback`（D19 说了就是 git，包了糖就会想给糖加参数）。 | R6 |
| D25 | 真身仓库位置 | 本地 **`~/skills`**（可见目录，不放隐藏目录，更**绝不放在任何 AI 工具的目录里**——那正是 D11 要逃离的东西），GitHub 私有仓 `HCID274/skills`。代码仓是 `HCID274/skillstow`，**两个仓互不嵌套，代码仓里不出现任何 skill 文件，也不需要 gitignore**。`~/skills` 只是默认值，本地配置第一项就是真身仓路径，任何人都能改。**选短路径是真的设计参数**：按 D11 真身是唯一编辑源，你天天要 `cd` 进去改 skill；路径一长你就会去改软链那头，改软链那头就绕过了真身。 | R7 |
| D26 | sync 时机与待办 | v1 **只有手动** `skillstow sync`（自动化不在 D20 范围）。但现在就定死三条设计约束，否则以后加自动化要改代码：**幂等、零交互、退出码有意义**（0 成功 / 非 0 失败且原因写 stderr）。满足这三条，cron / launchd / Windows 计划任务 / shell hook 以后全都能直接调。待办文件放**本地** `~/.config/skillstow/pending.md`——待决定的**过程**留本地（天天变，进仓库会制造大量无意义冲突），决定的**结果**进 manifest 全机器共享。 | R7 |
| D28 | 项目命名 | **skillstow**（原 SkillRiver）。理由：(1) **机制准确**——它就是给 AI skill 用的 GNU Stow，目标用户看名字就懂，不用读 README；(2) **唯一性极好**——GitHub 3 个同名全 0 star，crates.io 干净，搜这个词只会搜到你（对比 `skillsync` 有 2495 个同名）；(3) **隐喻不会把你往回拽**——river 暗示持续流动、有上下游、有中心水源，上一版的 Hub、长轮询、设备游标、流式对账正是这个词的自然产物；stow 是一次性动作。 | R8 |
| D27 | 迁移与备份 | `.system/` 那 6 个 Codex 自带 skill **不进真身仓库**，skillstow 明确忽略隐藏目录（同步它等于让三台机器互相覆盖对方的工具内置文件）。搬法：**先复制后切换**——`cp -a` → `git init` + 首次 commit → 验证一致 → 才把 `~/.codex/skills/` 原目录改名 `.bak` 并建链 → 一周后再删 `.bak`。**第一次 commit 完成那一刻之前所有操作不可逆，之后全都可逆。** | R7 |
| D16 | 旧仓库处置 | **原地重开 + 改名。**现有 80k 行打 `v0-archive` tag 推上去，然后清空重写；仓库同时从 `SkillRiver` 改名为 `skillstow`。GitHub 改名自动重定向旧 URL，且 0 star / 0 fork / 0 issue，没有任何人受影响。 | R4 / R8 |
| D12 | AI 何时出现 | **sync 绝不提问。**sync 纯确定性、只读规则、不产生规则，必须能无人值守跑（开机自启/定时/SSH）。遇到规则未覆盖的情况记一条待办继续跑完。`adapt` 是独立的、你主动发起的动作，只产生规则、不搬文件。 | R3 |

---

## 四、执行清单（决策已全部定完，可以动手）

### 阶段 0 — 先保住数据（唯一不可逆的部分，先做完）

- [ ] `mkdir -p ~/skills`，`cp -a` 把 `~/.codex/skills/` 下 23 个**非隐藏**目录复制过去（跳过 `.system/`），结果形如 `~/skills/dlog/SKILL.md`
- [ ] `cd ~/skills && git init && git add -A && git commit`
- [ ] GitHub 建私有仓 `HCID274/skills`，push
- [ ] 逐目录 diff 验证 `~/skills/` 与 `~/.codex/skills/` 内容一致

> 这四步做完，916 KB 第一次拥有历史和异地备份。D2 里"历史回滚"这个痛点在这一刻就已经解决了一半。

### 阶段 1 — 归档旧代码　✅ 已完成（2026-08-21）

- [x] 57 个未提交文件 + 64 个未跟踪条目全部提交（`f013a24`）
- [x] 全部历史打包成单文件 **`~/skillriver-v0-archive.bundle`**（1.3 MB，`git bundle verify` 确认完整）
      → 还原方式：`git clone ~/skillriver-v0-archive.bundle`
- [x] 清空项目目录（16 GB → 0）并删除 `.git`
- [x] `git init` 重开，首个提交 `fcb3746` 只含决策日志、行为契约、任务分派、三条护栏、可编译空骨架
- [ ] **待用户操作**：GitHub 删除 `HCID274/SkillRiver`，新建 `HCID274/skillstow`（public），
      新建 `HCID274/skills`（private）
- [ ] 拿到 URL 后 `git remote add origin` 并 push
- [ ] 本地目录 `SkillRiver` 改名为 `skillstow`（会改变本会话的工作目录，建议会话结束后再做）

> D16 已按此调整：原定"原地重开 + 改名"改为"彻底删除 + 全新仓库"，
> 理由是即使原地重开，`v0-archive` tag 仍在同一仓库里、`git clone` 默认会拉下来，
> 实习生 AI 探索时会撞见那 80,886 行并照着写。隔离靠仓库，不靠叮嘱。
> 历史不丢——它在 bundle 里。

### 阶段 2 — 写 v1（1000 行绊线随时生效）

- [ ] `CONTRIBUTING.md` 第一段写死 D21 的三条护栏
- [ ] `skillstow.toml` 模型（工具定义 + 例外表）与 `~/.config/skillstow/config.toml`
- [ ] `init` / `sync` / `status` 三条命令
- [ ] Mac 上切换投影：`~/.codex/skills` 原目录改名 `.bak` 后建 23 条链；`~/.claude/skills` 重建链；
      `~/.zcode/skills` 删掉整目录链、改成目录 + 逐个链

### 阶段 3 — 收线（D20，唯一的完成标志）

- [ ] Windows 机器上 `skillstow init`
- [ ] 跑验收：**Mac 改 `dlog/SKILL.md` 一行 → Windows 跑 sync → Windows 的
      `~/.claude/skills/dlog/SKILL.md` 里读到那一行，全程不超过两条命令**

### 阶段 4 — 只有阶段 3 通过后才允许开始

adapt skill、CI、安装包、README、LICENSE、发布、第三台机器。**一样都不许提前。**

## 五、未决问题

**无。**设计树已走完（7 轮访谈，D1–D27）。

如果后来发现某条决策不成立，改这份文件，并写清楚是哪条、为什么。
最可能被推翻的是 **D7（主轴是工具不是操作系统）**——如果哪天你真的有大量 skill
需要在不同 OS 上写不同内容，D7 就错了，整棵树要重算。
但 2026-08-21 的数据不支持这一点：23 个 skill 里只有 6 个沾平台，只有 1 个（`md2hci`）
是重度，而它的差异是"pandoc 装在哪"，属于环境配置。

## 六、补充事实（查证于 2026-08-21）

- `~/.codex/config.toml`、`~/.config/opencode/opencode.jsonc`、`~/.claude/settings.json`
  **都没有"自定义 skills 目录"的配置项**。三个工具的 skills 路径都写死了。
  → "一份真身 + N 个工具视图"只能靠文件系统实现（软链或复制），没有第三条路。
- GitHub 上的 `HCID274/SkillRiver`（将改名为 `skillstow`）是 **public，0 star / 0 fork / 0 watcher / 0 issue**，
  远端最后推送停在 2026-08-11。→ 没有任何外部使用者，重置仓库的成本为零。
- `~/.codex/skills/.system/` 有 508 KB、6 个 skill（imagegen / openai-docs / plugin-creator /
  review-agent / skill-creator / skill-installer），**是 Codex 自带并自行管理的**，
  不是用户写的，会随工具版本变。→ 不应进真身仓库。
