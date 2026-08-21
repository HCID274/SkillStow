# skillstow 行为契约

配套文档：`docs/REPLAN.md`（为什么这么设计，28 条决策）、`CONTRIBUTING.md`（三条硬护栏）。
本文可以改。发现它错了或代价不成比例，直接改并说明理由。

---

## 1. 这个程序是什么

**给 AI skill 用的 GNU Stow。**

一个私有 git 仓库存放所有 skill 的真身，一条命令把它们软链投影到各个 AI 工具的
skills 目录。内容搬运全部交给 git，本程序只负责两件事：**建链**和**拆链**。

```
~/skills/                        真身仓（private git repo），唯一编辑源
  skillstow.toml                 工具定义 + 例外表
  dlog/SKILL.md
  grill-me/SKILL.md
  md2hci/SKILL.md
      │
      ├──→ ~/.claude/skills/dlog      符号链接
      ├──→ ~/.codex/skills/dlog       符号链接
      └──→ ~/.zcode/skills/dlog       符号链接

skillstow sync = git pull --rebase  →  刷新链  →  git push
```

**不做的事**（每条都是上一版做了并且失败了的）：不做内容改写、不做格式转换、
不做冲突合并、不做设备注册、不做通知、不做服务端、不做后台常驻、不做文件监听。

### 1.1 平台差异不由本程序处理

同一个 skill 在不同操作系统上确实可能需要不同行为（例：`md2hci/templates/gongwen.typ`
写死了 `Songti SC / Heiti SC`，这是 macOS 系统字体，Windows 上没有）。

**处理它的位置是 skill 内部，不是 skillstow。**skill 文件在所有机器上逐字节相同，
平台分支写进内容里，由**读这个 skill 的 AI** 在运行时选择——AI 天然知道自己跑在什么系统上。
用户的 skill 本来就在用渐进披露（`SKILL.md` 短，细节在 `references/`、`scripts/`、
`templates/`），加一个 `platform/windows.md` 让 AI 按需读，是顺理成章的写法。

**绝不允许的相反做法**：让 skillstow 往不同机器投不同版本的文件。
一旦投影不等于真身，下面这些立刻全部需要：投影脏没脏的检测、本机当前活跃版本的记录、
回滚时的重新组装——这正是上一版 `Bundle` / `Active` / `staged_bundle` 的全部来源。
D19「回滚就是 git checkout」是「投影逐字节等于真身」白送的，破坏这一条，礼物就没了。

如果某个 skill 在某台机器上完全没意义，用 SPEC 2.4 的 `skip` 把它挡掉，而不是改它的内容。

---

## 2. 数据模型

### 2.1 `~/skills/skillstow.toml`（进仓库，全机器共享）

```toml
# 工具定义。path 用 ~ 表示 home，程序负责展开。
[tools.claude]
path = "~/.claude/skills"

[tools.codex]
path = "~/.codex/skills"

[tools.zcode]
path = "~/.zcode/skills"

# 例外表。语义是「默认全给，这里只写排除」。
# key = skill 目录名，value = 不投给哪些工具。
[exclude]
luna-vision-worker    = ["claude"]
playwright-interactive = ["claude"]
```

- **没写进 `[exclude]` 的 skill，投给本机启用的全部工具。**这是 D18，不要改成白名单。
- `[exclude]` 里出现不存在的 skill 名或不存在的工具名：**警告，不报错**。
  （skill 可能在别的分支上，工具可能这台机器没启用。）

### 2.2 `~/.config/skillstow/config.toml`（不进仓库，每台机器不同）

Windows 路径为 `%APPDATA%\skillstow\config.toml`。

```toml
repo  = "~/skills"                    # 真身仓在哪
tools = ["claude", "codex", "zcode"]  # 这台机器启用哪些工具
skip  = []                            # 这台机器不要的 skill，见 2.4

# 可选：覆盖 skillstow.toml 里的 path。Windows 或非标准安装位置用。
[overrides]
codex = "D:\\codex\\skills"
```

- `tools` 里出现 `skillstow.toml` 未定义的工具名：**报错退出**（码 2）。这是拼写错误。
- 这个文件不进仓库的理由见 D23：三台机器的路径差异进仓库就会变成 git 冲突。

### 2.4 `skip`：这台机器不要哪些 skill

```toml
skip = ["md2hci", "coros-trainingcalendar-ops"]
```

被 skip 的 skill 在这台机器上一条链都不建；已经建了的会被拆掉。它仍然在真身仓里、
仍然有历史、仍然同步到本机磁盘，只是不投影给任何工具。

**为什么放在本机配置而不是共享清单里：**你真正要表达的是「**这台机器**上不要这个」，
「平台」只是它的代理变量——同样是 Windows，装了 pandoc 的那台就该有 `md2hci`。
把 OS 作为维度写进共享清单，是四层 Profile 的第一块砖（D7 明确拒绝了这条路）。
代价是每台机器各写一次；对个人几台机器的规模，这个代价比引入一个新维度小得多。

`skip` 里写了不存在的 skill 名：**警告，不报错**（可能在别的分支上）。

### 2.3 `~/.config/skillstow/pending.md`（不进仓库，本机待办）

由 sync 每次**整体重写**（不是追加）。没有待办时写一个空标题即可。格式：

```markdown
# skillstow 待决定  （生成于 2026-08-21 15:04）

## 野生 skill：工具目录里有，真身仓没有
- `~/.claude/skills/show-then-tell`
  要收编就手动执行： mv ~/.claude/skills/show-then-tell ~/skills/ && cd ~/skills && git add -A && git commit

## 工具目录被占用，无法投影
- `~/.zcode/skills` 本身是一个符号链接，不是目录。删掉它并建成普通目录后重跑 sync。
```

待办**不影响 sync 的退出码**。sync 成功投影完就是 0，只在 stdout 提示「有 N 条待办」。
理由：以后 sync 要挂在 cron 上（D26），有待办就报错会天天误报警。

---

## 3. 核心算法：投影计划

这是整个程序唯一有逻辑的部分。三步，纯函数，好测。

### 3.1 枚举 skill

扫描 `repo` 根目录的直接子项，满足**全部**条件的算一个 skill：

1. 是目录（符号链接指向的目录也算）
2. 名字不以 `.` 开头（排除 `.git`、`.github`；这也是 D27 说的忽略隐藏目录）
3. 目录内直接包含 `SKILL.md` 文件

其余一律忽略，不警告。`skillstow.toml` 是文件，天然被排除。

### 3.2 算出「应该存在的链」

```
desired = {}
for tool in config.tools:
    tool_dir = overrides[tool] or skillstow.toml.tools[tool].path   # 展开 ~
    for skill in skills:
        if skill in config.skip: continue                 # 本机不要（SPEC 2.4）
        if tool in exclude.get(skill, []): continue       # 清单里的工具例外
        desired[tool_dir / skill] = repo / skill
```

### 3.3 对比现状，得到动作表

对每个启用的工具，先检查 `tool_dir` 本身：

| tool_dir 的状态 | 动作 |
| --- | --- |
| 不存在 | `create_dir_all`，继续 |
| 是普通目录 | 继续 |
| **是符号链接** | **跳过这个工具**，写进 pending.md（`~/.zcode/skills` 现在就是这种） |
| 是普通文件 | 跳过这个工具，写进 pending.md |

然后逐项对比 `tool_dir` 下的条目：

| 现状 | desired 里有 | desired 里没有 | 动作 |
| --- | --- | --- | --- |
| 不存在 | ✓ | | **建链** |
| 是链，且指向 `repo` 内部 | ✓ | | **拆掉重建**（不读取链目标，见 7.2） |
| 是链，且指向 `repo` 内部 | | ✓ | **拆链**（这是我们建的，现在不该有了） |
| 是链，指向 `repo` 外部 | 任意 | 任意 | **不动**，写进 pending.md |
| 是真实目录或文件 | 任意 | 任意 | **不动**，写进 pending.md（野生 skill） |

**判断「这条链是不是我们建的」的唯一判据：它指向 `repo` 内部。**
不用数据库、不用标记文件、不用 xattr。这条判据是整个程序能保持简单的关键，不要改。

**「拆掉重建」而不是「读目标比对」的理由见 7.2。**它让程序完全不需要读取链目标，
从而绕开 Windows junction 的全部麻烦。拆链不碰目标内容，安全且幂等。

---

## 4. 三条命令

### 4.1 `skillstow init`

```
skillstow init --repo <git-url|本地路径> [--tools claude,codex,zcode] [--import-from <dir>]
```

1. 若 `--repo` 是 URL 且本地目标路径不存在 → `git clone`。若是本地已有仓库 → 直接用。
2. 写 `~/.config/skillstow/config.toml`。`--tools` 缺省时，
   **自动探测**：`skillstow.toml` 里定义的工具，其 `path` 的父目录存在就算装了。
3. `--import-from <dir>`：把 `<dir>` 下符合 3.1 判定的目录 `cp -a` 进 repo，
   然后 `git add -A && git commit -m "skillstow: import from <dir>"`。
   **已存在同名 skill 时报错退出（码 2），不覆盖。**
4. 最后跑一次和 `sync` 相同的投影逻辑。

init **可以交互**（它一辈子只跑一次）。sync 不可以。

### 4.2 `skillstow sync`

```
skillstow sync [-m <commit message>]
```

严格按顺序，任何一步失败立即停止并返回对应退出码，**不执行后续步骤**：

1. **本地有未提交改动 → 自动提交。**
   `git add -A && git commit -m "<-m 的值，或默认 'skillstow: <hostname> <ISO时间>'>"`
   > 判断题说明：真身仓是你随手编辑 skill 的地方，要求手动 commit 会让 sync 经常失败，
   > 而且等于要求所有用户懂 git 流程。自动提交产生的历史是「每次 sync 一个点」，
   > 足够满足 D2 的回滚需求。想要好的 commit message，sync 前自己 commit 即可。
2. `git pull --rebase`。
   - 冲突 → **退出码 3**，把 git 的原始 stderr 原样打印，再加一句：
     `到 <repo> 手动解决冲突后重跑 skillstow sync；想放弃这次 rebase 就跑 git rebase --abort`。
     **不自动 abort**（D10：冲突甩给人，不要替人做决定）。
3. **刷新链**（第 3 节的算法）。失败 → 退出码 4，**不 push**。下次 sync 重试即可（幂等）。
4. `git push`。
   - 因远端前进而被拒 → 回到第 2 步重来，**最多重试 2 次**，仍失败则退出码 3。
5. 重写 `pending.md`，stdout 打印摘要。退出码 0。

**sync 必须满足（D26，这三条决定了以后能不能挂 cron，不要破坏）：**
- **幂等**：连跑两次，第二次不产生任何变更。
- **零交互**：任何情况下都不等待输入。
- **退出码有意义**：见第 5 节。

### 4.3 `skillstow status`

只读，不修改任何东西。等价于 sync 的 dry-run。输出：

```
仓库  ~/skills  分支 main  干净  与 origin/main 同步
工具  claude   23 应有 / 23 正确 / 0 缺失 / 0 多余 / 1 野生
工具  codex    23 应有 / 23 正确
工具  zcode    跳过：~/.zcode/skills 本身是符号链接
待办  2 条      ~/.config/skillstow/pending.md
```

退出码：全部一致且仓库干净 → 0；有任何不一致 → 1。方便脚本判断。

### 4.4 明确不提供的命令

`link` / `unlink`（改 `skillstow.toml` 再 sync；多一条命令就多一条绕过 manifest 的路径，
manifest 一旦不是唯一真相 D18 就废了）、`--dry-run`（`status` 就是）、
`rollback`（D19：就是 `git checkout`，包了糖就会想给糖加参数）、
`adopt`（阶段 4 才考虑，现在 pending.md 里写手动命令）。

---

## 5. 退出码

| 码 | 含义 | 谁用 |
| --- | --- | --- |
| 0 | 成功 | 全部 |
| 1 | 状态不一致（不是错误） | status |
| 2 | 配置或参数错误 | 全部 |
| 3 | git 冲突或推送失败，需要人处理 | sync |
| 4 | 文件系统操作失败 | sync / init |

错误信息全部写 stderr，正常输出写 stdout。

---

## 6. 模块与行数预算

护栏三：**确定性代码 1000 行硬上限，不含测试**。预算已排满。

| 文件 | 职责 | 预算 |
| --- | --- | --- |
| `src/main.rs` | clap 解析、分派、把 Result 翻译成退出码 | 120 |
| `src/config.rs` | 两个 toml 的读写、`~` 展开、overrides 合并 | 150 |
| `src/repo.rs` | shell out git：status / commit / pull --rebase / push / clone | 150 |
| `src/plan.rs` | 第 3 节的算法。**纯函数，输入是路径快照，输出是动作表** | 200 |
| `src/link.rs` | 平台链接原语：`create` / `remove` / `classify` | 150 |
| `src/cmd.rs` | init / sync / status 的编排与输出 | 200 |
| | | **970** |

`plan.rs` 必须是纯函数（不碰文件系统，输入是一个"目录快照"结构体）。
这是唯一值得写单元测试的地方，也是唯一能跨平台测试的地方。

依赖只允许：`clap`、`serde` + `toml`、`anyhow` 或 `thiserror`、`dirs`。
**不允许**：tokio、libgit2/gitoxide、notify、任何 HTTP 客户端、任何加密库。

---

## 7. 平台链接语义

### 7.1 建链

| 平台 | 做法 |
| --- | --- |
| Unix | `std::os::unix::fs::symlink(target, link)` |
| Windows | 先试 `std::os::windows::fs::symlink_dir`（开发者模式或管理员下可成功）；
失败则 shell out `cmd /C mklink /J <link> <target>` 建 junction |

D14 定的是 **junction 优先、零提权**。真符号链接只是"能用就用"的加分项，不是前提。
**不要**去检测开发者模式的注册表键——直接试，失败就退化，这样代码少一半。

### 7.2 四处必须先验证的未知（T0 任务）

我不确定下面三条在 Windows 上的实际行为。**不要照着我的猜测写代码**，
先用 5 行的实验程序验证，把结果写进 `docs/PLATFORM_NOTES.md`，再写正式实现。

0. **不提权能不能建 junction？`std::os::windows::fs::symlink_dir` 在没开发者模式时是什么错误？**
   D14 整个「Junction 为主、零提权」的决策建立在这条假设上。假设错了，D14 要重做，
   要么改成要求开发者模式（对 D8 开源是实打实的流失），要么改成 Windows 上一律复制。

1. **`std::fs::symlink_metadata(p).file_type().is_symlink()` 对 junction 返回什么？**
   本规范假设返回 `true`。如果返回 `false`，第 3.3 节区分「链」和「真实目录」的判据就要改，
   届时的替代方案是 `std::fs::metadata` 与 `symlink_metadata` 的 `file_type` 不一致即为链。
2. **`std::fs::remove_dir(p)` 对 junction 的行为？**
   本规范假设它只删除 junction 本身、不递归删除目标内容。
   **这条如果错了会删掉用户的真身数据**，必须在一个临时目录里实测确认，这是全项目最高风险的一处。
3. **`git pull` 在 Windows 上把仓库里的符号链接 checkout 成什么？**
   真身仓里的 skill 是真实目录，理论上不涉及。但 `~/.claude/skills/show-then-tell` 这类
   如果被收编，仓库里可能出现符号链接条目。确认 `core.symlinks=false` 时的表现。

### 7.3 跨平台路径

`skillstow.toml` 里的 path 一律用 `~/...` 和正斜杠书写，程序展开成本平台路径。
Windows 上的 `%APPDATA%` 通过 `dirs` crate 取，不手写环境变量解析。

---

## 8. 边界情况清单

实现时逐条对照，每条都要有对应行为，**不许有"未定义"**：

| 情况 | 行为 |
| --- | --- |
| repo 路径不存在 | 退出码 2，提示先跑 init |
| repo 不是 git 仓库 | 退出码 2 |
| `skillstow.toml` 不存在 | 当成"零工具定义"，sync 只做 git 部分并警告 |
| `skillstow.toml` 语法错误 | 退出码 2，打印 toml 解析器的原始错误 |
| repo 里一个 skill 都没有 | 正常，拆掉所有旧链，退出 0 |
| skill 名含空格或非 ASCII | 允许，原样建链 |
| skill 名在不同工具目录下已被真实目录占用 | 不动，写 pending，其他 skill 照常投影 |
| 同一个 skill 被排除给全部工具 | 允许（相当于只在真身仓里存着） |
| `tool_dir` 在只读文件系统上 | 退出码 4，报明是哪个工具 |
| 没网 | `git pull` 失败 → 退出码 3。**已经做的自动提交保留**，不回滚 |
| 同一台机器并发跑两个 sync | 不处理。**不加锁**（护栏一：不建事务层）。git 自己会因为 index.lock 失败 |
| repo 处于 rebase / merge 中途 | 退出码 3，提示先处理完 |
