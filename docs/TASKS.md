# skillstow 任务分派

给实习生 AI 用。每个任务：**独占的文件范围 + 可执行的验收命令**。
文件范围互斥，所以可以并行；但 T0 必须最先单独完成。

动手前必读：`CONTRIBUTING.md`（三条硬护栏）、`docs/SPEC.md`（行为契约）。
`docs/REPLAN.md` 是背景，读不读随你，但**不要读 `v0-archive` 里的旧代码**——
那 80,886 行是反面教材，照着写就是重蹈覆辙。

---

## T0 — 平台探针　✅ 已完成（2026-08-21）

结论见 `docs/PLATFORM_NOTES.md`。它改动了 SPEC 3.3、7.1、7.2 并新增了 2.5，
**写 `link.rs` 前必须先读**。下面保留原任务描述作为记录。

<details><summary>原任务</summary>


**这个任务不写产品代码。**产出一份 `docs/PLATFORM_NOTES.md`。

在一台 Windows 机器上，用最小的实验程序（每个 5 到 10 行）验证 `SPEC.md` 7.2 的四个问题：

0. 不提权能不能 `mklink /J` 建 junction？`std::os::windows::fs::symlink_dir`
   在没开发者模式时报什么错？（D14「Junction 为主、零提权」整个建立在这条上）
1. `std::fs::symlink_metadata(p).file_type().is_symlink()` 对 junction 返回 true 还是 false？
2. **`std::fs::remove_dir(p)` 对 junction 是只删链本身，还是会递归删掉目标里的内容？**
3. `git` 在 `core.symlinks=false` 时把仓库里的符号链接 checkout 成什么？

**第 2 条是全项目最高风险的一处**：如果它会递归删除，第 3.3 节的「拆掉重建」策略
会删光用户的真身 skill。**必须在一个塞了假数据的临时目录里实测，确认之后才允许写 `link.rs`。**

- 独占文件：`docs/PLATFORM_NOTES.md`
- 验收：四个问题各有一段实验代码、一段实际输出、一句结论。
  结论与 SPEC 假设不符的，直接改 SPEC 7.2 并说明。

</details>

---

## T1 — 配置读写

- 独占文件：`src/config.rs`
- 内容：SPEC 2.1 / 2.2 的两个 toml 的 serde 模型、`~` 展开、`overrides` 合并、
  SPEC 8 里所有和配置相关的错误分支（缺文件、语法错、工具名拼错）。
- 预算：150 行
- 验收：
  ```
  cargo test -p skillstow config::
  ```
  覆盖：正常读取、`~` 展开正确、overrides 生效、`tools` 里有未定义工具名 → 错误、
  toml 语法错 → 错误里带原始解析信息。

---

## T2 — 平台链接原语（T0 已完成，可以开工）

- 独占文件：`src/link.rs`
- 内容：`create(target, link)` / `remove(link)` / `classify(path) -> Missing | OurLink | ForeignLink | RealDir | RealFile`。
  `classify` 判断 `OurLink` 的唯一依据是**链指向 repo 内部**（SPEC 3.3）。
  Windows 建链一律 `mklink /J`，**不要**试 `symlink_dir`（SPEC 7.1）。
  拆链只准 `remove_dir`，**禁止 `remove_dir_all`**（SPEC 7.2）。
  注意 junction 的 `symlink_metadata().is_dir()` 是 false，判目录性质要用 `metadata()`。
  **动手前先读 `docs/PLATFORM_NOTES.md`。**
- 预算：150 行
- 验收：在 macOS 和 Windows 各跑一遍
  ```
  cargo test -p skillstow link::
  ```
  必须包含一条测试：**建链 → remove → 确认目标目录里的文件仍然存在**。

---

## T3 — git 外壳

- 独占文件：`src/repo.rs`
- 内容：shell out `git`，封装 `is_repo` / `is_dirty` / `commit_all` / `pull_rebase` /
  `push` / `clone` / `branch_status`。每个函数返回结构化结果，
  失败时**把 git 的原始 stderr 原样带出来**（SPEC 4.2 第 2 步要原样打印）。
  区分「冲突」和「其他失败」——冲突要能被 `cmd.rs` 识别成退出码 3。
- 预算：150 行
- 验收：
  ```
  cargo test -p skillstow repo::
  ```
  在临时目录里 `git init` 造真仓库来测，不要 mock。至少覆盖：干净/脏、
  正常 pull、制造一次真冲突并确认被识别为冲突。

---

## T4 — 投影计划（纯函数，依赖 T1 的类型）

- 独占文件：`src/plan.rs`
- 内容：SPEC 第 3 节。**不碰文件系统**——输入是一个"目录快照"结构体
  （每个路径的 `classify` 结果），输出是动作表（Create / Remove / Skip + 原因）。
- 预算：200 行
- 验收：
  ```
  cargo test -p skillstow plan::
  ```
  **这是全项目唯一值得堆测试的地方，也是唯一能在 Mac 上测出 Windows 行为的地方。**
  SPEC 3.3 的表格每一行都要有一个测试，SPEC 第 8 节的边界清单逐条对应。

---

## T5 — 命令编排（依赖 T1–T4）

- 独占文件：`src/main.rs`、`src/cmd.rs`
- 内容：SPEC 第 4 节三条命令的顺序与错误处理、SPEC 第 5 节的退出码、
  `pending.md` 的生成、status 的输出格式。
- 预算：320 行（main 120 + cmd 200）
- 验收：
  ```
  cargo run -- status            # 退出码 0 或 1，不修改任何文件
  cargo run -- sync && cargo run -- sync   # 第二次必须零变更（幂等）
  echo $?                        # 退出码符合 SPEC 第 5 节
  ```
  另外必须验证**零交互**：`cargo run -- sync < /dev/null` 不能挂起。

---

## T6 — 端到端验收（D20，唯一的完成标志）

在两台真实机器上：

```
[Mac]      改 ~/skills/dlog/SKILL.md 的一行
[Mac]      skillstow sync
[Windows]  skillstow sync
[Windows]  确认 ~/.claude/skills/dlog/SKILL.md 里有那一行
```

**全程不超过两条命令。**这条跑通之前，不许开始 CI、安装包、README、LICENSE、
发布、第三台机器、adapt skill。

---

## 随时生效的绊线

```
find src -name '*.rs' -not -name '*test*' | xargs wc -l
```

超过 1000 就停下来重读 `docs/REPLAN.md`，问：我是不是又在解决一个不存在的问题。
