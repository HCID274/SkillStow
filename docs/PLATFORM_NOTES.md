# Windows 平台行为实测结论（T0）

测得于 2026-08-21，`Lin_ITX\50428` 普通用户会话（非管理员），
`rustc 1.98.0 (88d9e12ae 2026-08-18)`，`stable-x86_64-pc-windows-msvc`。
完整报告见交接记录；本文只保留结论和它们改变了哪条规范。

## 0. 不提权能建 junction，但不能建真符号链接

```
mklink /J  →  Junction created ... exit=0
symlink_dir → Err(Os { code: 1314, message: "客户端没有所需的特权。" })
reg query HKLM/HKCU ...\AppModelUnlock → 找不到指定的注册表键
```

**结论：D14「Junction 为主、零提权」成立。**开发者模式在这台机器上是关的（注册表键缺失，
且 1314 = `ERROR_PRIVILEGE_NOT_HELD`），而 junction 照样建得出来。

**改了规范**：SPEC 7.1 原本写「先试 `symlink_dir`，失败退化 junction」。
现在改成 **Windows 一律直接 `mklink /J`**。理由：真符号链接对本程序没有任何额外好处
（我们只链本地目录），而那个分支意味着在绝大多数机器上每建一条链都要先失败一次
系统调用——24 个 skill × 3 个工具 = 72 次注定失败的调用，换来零收益。少一个分支，少一段代码。

## 1. junction 在 Rust 里能被正确识别，而且 read_link 可用

```
link_j: symlink_metadata is_symlink=true  is_dir=false
link_j: metadata is_dir=true
link_j: read_link -> Ok("C:\\...\\sstest\\target")

target: symlink_metadata is_symlink=false is_dir=true
target: read_link -> Err(code: 4390, "此文件或目录不是一个重分析点。")
```

**结论比原假设更好。**`is_symlink()` 对 junction 返回 `true`（假设正确），
而且 **`read_link()` 能拿到目标路径**——原规范曾担心这条不可用。

**改了规范**：SPEC 3.3 原本为了绕开「可能读不到链目标」而规定「拆掉重建，不读取链目标」。
现在改成**读链目标比对**：目标已经正确就跳过，真正做到零 churn 的幂等，
而不是每次 sync 都把 72 条链拆了重建一遍。

**给实现者的坑（实测意外发现）**：junction 的 `symlink_metadata().is_dir()` 返回 **false**。
要判断「链指向的是不是目录」必须用跟随链接的 `metadata()`。只看 `symlink_metadata` 会误判。

## 2. 删除 junction 不会碰目标内容（两种删法都不会）

```
删除前 target 文件数 = 3
remove_dir(link_j)     -> Ok(())     删除后 target 文件数 = 3
remove_dir_all(link_j) -> Ok(())     之后   target 文件数 = 3
```

**结论：全项目最高风险的那条假设成立**，Rust 1.98 对 junction 的两种删除都只删链本身。

**但规范仍然规定只准用 `remove_dir`，禁止 `remove_dir_all`。**理由不是这次的实测结果，
而是失败方向：万一 `classify` 判错、把一个真实的非空目录当成了链，
`remove_dir` 会安全地失败（目录非空），`remove_dir_all` 会把用户的数据删光。
**一个 fail-safe，一个 fail-dangerous。**在会删东西的路径上，永远选前者。

## 3. `core.symlinks` 默认 false，符号链接条目会退化成文本文件

```
git config core.symlinks             → false
git ls-files -s linked-dir           → 120000 e63e225... linked-dir
Get-Item linked-dir                  → LinkType 空, Length 7
Get-Content -Raw linked-dir          → realdir
```

**结论：仓库里任何 `120000` 模式的条目，在 Windows 上会被检出成一个内容为目标路径的普通文本文件。**
对 skill 来说就是彻底失效。

**这条当场抓到一个真问题。**当时 `~/skills/pua` 是一个指向 `~/.codex/pua/skills/pua`
的符号链接，已被以 120000 提交——29 个文件、204 KB **实际没有入库、没有备份**。
已在提交 `abb2ce5` 固化为真实内容。

**改了规范**：新增硬规则——**真身仓禁止出现符号链接条目**，
`init --import-from` 必须固化（deref）而不是保存链接。见 SPEC 2.5。

## 其他实测发现

- `git hash-object --stdin` 从 PowerShell 管道取输入会被附加换行。与本程序无关，
  但任何在 Windows 上用 PowerShell 管道喂二进制/精确内容的脚本都要注意。
- Windows 上 `.git/objects` 里的对象文件是只读属性，直接删目录会 `Access denied`，
  要先清只读位。本程序不删仓库，但清理脚本会踩到。
