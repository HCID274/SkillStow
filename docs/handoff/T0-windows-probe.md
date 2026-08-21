# T0 交接提示词 · Windows 链接行为探针

> 用法：把下面「---」之间的全部内容复制，发给那台 Windows 机器上的 AI。
> 它自带全部上下文，不需要看本仓库。

---

你在一台 Windows 机器上。我需要你做一次**只读性质的行为探测**，不是开发任务。

## 背景

有个叫 skillstow 的小工具（Rust，跨平台 CLI），作用是把一个 git 仓库里的
skill 目录，用符号链接投影到各个 AI 工具的 skills 目录下——本质上就是
「给 AI skill 用的 GNU Stow」。

它在 Windows 上打算用 **junction（`mklink /J`）**而不是真符号链接，因为 junction
不需要管理员权限也不需要开启开发者模式。但这个方案里有四条关键假设**没有人验证过**，
而其中一条如果是错的，程序第一次运行就会**删光用户的真实数据**。

你的任务就是验证这四条。**不要写产品代码，不要建仓库，不要装任何东西（除了 Rust 工具链）。**

## 安全边界（必须遵守）

- **全部实验只在一个临时目录里做**，比如 `%TEMP%\sstest`。
- **绝对不要**碰 `~/.claude`、`~/.codex`、`~/.zcode`、`~/skills` 或任何看起来像真实数据的目录。
- 实验 2 会测试删除行为。**必须用你自己刚造的假文件**，内容随便写，比如三个写着
  `dummy1` / `dummy2` / `dummy3` 的 txt。
- 做完把临时目录删掉。

## 环境准备

```powershell
mkdir $env:TEMP\sstest
cd $env:TEMP\sstest
mkdir target
"dummy1" | Out-File target\a.txt
"dummy2" | Out-File target\b.txt
"dummy3" | Out-File target\c.txt
```

确认有 Rust：`rustc --version`。没有就用 rustup 装，或者告诉我没有、改用 PowerShell 验证能验的部分。

---

## 实验 0 — 不提权能不能建 junction

**这条决定整个 Windows 方案。**

以**普通用户身份**（不要用管理员 PowerShell）执行：

```powershell
cmd /c mklink /J $env:TEMP\sstest\link_j $env:TEMP\sstest\target
echo "exit=$LASTEXITCODE"
```

然后用 Rust 试真符号链接：

```rust
// probe0.rs
use std::os::windows::fs::symlink_dir;
fn main() {
    let t = std::env::var("TEMP").unwrap();
    let r = symlink_dir(format!("{t}\\sstest\\target"), format!("{t}\\sstest\\link_s"));
    println!("symlink_dir -> {:?}", r);
}
```

`rustc probe0.rs && .\probe0.exe`

**要回答**：mklink /J 成功了吗？`symlink_dir` 成功还是报什么错（错误码多少）？
你这台机器的开发者模式是开着还是关着（设置 → 隐私和安全性 → 开发者选项）？

---

## 实验 1 — junction 在 Rust 里被识别成什么

```rust
// probe1.rs
use std::fs;
fn main() {
    let t = std::env::var("TEMP").unwrap();
    for name in ["link_j", "link_s", "target"] {
        let p = format!("{t}\\sstest\\{name}");
        match fs::symlink_metadata(&p) {
            Ok(m) => println!("{name}: symlink_metadata is_symlink={} is_dir={}",
                              m.file_type().is_symlink(), m.file_type().is_dir()),
            Err(e) => println!("{name}: symlink_metadata 失败 {e}"),
        }
        match fs::metadata(&p) {
            Ok(m) => println!("{name}: metadata is_dir={}", m.file_type().is_dir()),
            Err(e) => println!("{name}: metadata 失败 {e}"),
        }
        println!("{name}: read_link -> {:?}", fs::read_link(&p));
        println!();
    }
}
```

**要回答**：对 junction，`is_symlink()` 返回 true 还是 false？`read_link` 返回目标路径还是报错？
（程序要靠这个区分「我们建的链」和「用户自己放的真实目录」，返回值不对整个判据就要重设计。）

---

## 实验 2 — 删除 junction 会不会连目标内容一起删（最高风险）

**做之前再确认一次：`target` 里只有你刚造的三个 dummy 文件。**

```rust
// probe2.rs
use std::fs;
fn count(t: &str) -> usize {
    fs::read_dir(format!("{t}\\sstest\\target")).map(|d| d.count()).unwrap_or(9999)
}
fn main() {
    let t = std::env::var("TEMP").unwrap();
    println!("删除前 target 文件数 = {}", count(&t));
    println!("remove_dir(link_j) -> {:?}", fs::remove_dir(format!("{t}\\sstest\\link_j")));
    println!("删除后 target 文件数 = {}", count(&t));
}
```

跑完再用 `mklink /J` 重建一个 junction，然后测 `remove_dir_all`：

```rust
println!("remove_dir_all(link_j) -> {:?}", fs::remove_dir_all(format!("{t}\\sstest\\link_j")));
println!("之后 target 文件数 = {}", count(&t));
```

**要回答**：两种删除方式，`target` 里的文件数各自变了没有？
如果删除后变成 0，说明它递归删掉了目标内容——**这是必须在正式实现里明确禁止的做法**，
请在报告里用醒目的方式写出来。

---

## 实验 3 — git 怎么处理仓库里的符号链接

```powershell
cd $env:TEMP\sstest
git init repo-src; cd repo-src
mkdir realdir; "hi" | Out-File realdir\x.txt
git add -A; git -c user.email=t@t commit -m init
git config core.symlinks   # 看看默认值是什么
```

如果你有办法造一个含符号链接条目的提交（比如从 Linux/Mac 端推一个过来，或者用
`git update-index --add --cacheinfo 120000,<blob>,<name>`），就在 `core.symlinks=false`
下 clone 出来看看那个条目变成了什么。做不到就直接说做不到。

**要回答**：`core.symlinks` 在这台机器上的默认值是什么？

---

## 输出格式

用 markdown 回一份报告，四个实验各一节，每节包含：

1. 你实际跑的命令 / 代码
2. **真实的终端输出**（原样粘贴，不要复述、不要总结、不要美化）
3. 一句结论

最后加一节「意外发现」，写任何你觉得反常的东西。

**如果某个实验跑不起来，就写跑不起来和报错原文。不要猜测结果，不要为了让报告完整而编造输出。**
这份报告会直接决定一个会删用户数据的函数怎么写，猜错的代价很大。

---
