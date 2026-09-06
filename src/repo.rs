use anyhow::{Context, Result, ensure};
use std::{
    path::Path,
    process::{Command, Stdio},
};

pub fn git(repo: &Path, args: &[&str]) -> Result<String> {
    let output = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .env("GIT_TERMINAL_PROMPT", "0")
        .env("GCM_INTERACTIVE", "never")
        .env(
            "GIT_SSH_COMMAND",
            "ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5 -o ServerAliveCountMax=2",
        )
        .env("GIT_EDITOR", "true")
        .stdin(Stdio::null())
        .output()
        .context("运行 git")?;
    ensure!(
        output.status.success(),
        "git {}\n{}{}",
        args.join(" "),
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    Ok(String::from_utf8(output.stdout)?.trim_end().into())
}
pub fn path(p: &Path) -> Result<&str> {
    p.to_str().context("路径不是 UTF-8")
}
pub fn dirty(p: &Path) -> Result<bool> {
    Ok(!git(p, &["status", "--porcelain", "--untracked-files=all"])?.is_empty())
}
pub fn check(p: &Path) -> Result<()> {
    ensure!(
        git(p, &["rev-parse", "--show-toplevel"])? == path(p)?,
        "必须指定 Git 仓库根目录"
    );
    ensure!(
        git(p, &["branch", "--show-current"])? == "main",
        "维护仓必须位于 main 分支"
    );
    for marker in [
        "rebase-merge",
        "rebase-apply",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
    ] {
        let m = git(p, &["rev-parse", "--git-path", marker])?;
        ensure!(
            !p.join(m).exists(),
            "Git 操作尚未完成；先解决冲突并完成/中止 rebase 或 merge，再重跑 sync"
        );
    }
    Ok(())
}
pub fn files(p: &Path) -> Result<()> {
    let tracked = git(p, &["ls-files", "--stage"])?;
    ensure!(
        !tracked
            .lines()
            .any(|line| line.starts_with("120000 ") || line.starts_with("160000 ")),
        "仓库包含符号链接或 submodule，必须固化完整内容"
    );
    Ok(())
}
pub fn commit(p: &Path, message: &str) -> Result<()> {
    if dirty(p)? {
        git(p, &["add", "-A"])?;
        files(p)?;
        git(p, &["commit", "-m", message])?;
    }
    Ok(())
}
pub fn fetch(p: &Path) -> Result<()> {
    git(
        p,
        &[
            "fetch",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
    )?;
    Ok(())
}
pub fn rebase(p: &Path) -> Result<()> {
    git(p, &["rebase", "origin/main"]).context(
        "到维护仓解决冲突并运行 git rebase --continue；放弃本次 rebase 用 git rebase --abort",
    )?;
    Ok(())
}
