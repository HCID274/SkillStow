use anyhow::{Result, ensure};
use std::{
    fs,
    io::ErrorKind,
    path::{Component, Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq)]
pub enum State {
    Missing,
    Link(PathBuf),
    Directory,
    File,
}
// read_link 可返回相对路径；按链接所在目录解释，不能跟随悬空目标。
pub fn normalize(p: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            _ => out.push(c),
        }
    }
    out
}
pub fn classify(p: &Path) -> Result<State> {
    match fs::symlink_metadata(p) {
        Err(e) if e.kind() == ErrorKind::NotFound => Ok(State::Missing),
        Err(e) => Err(e.into()),
        Ok(m) if m.file_type().is_symlink() => {
            let t = fs::read_link(p)?;
            Ok(State::Link(normalize(&if t.is_absolute() {
                t
            } else {
                p.parent().unwrap().join(t)
            })))
        }
        Ok(m) if m.is_dir() => Ok(State::Directory),
        Ok(_) => Ok(State::File),
    }
}
pub fn create(target: &Path, dest: &Path) -> Result<()> {
    ensure!(target.is_dir(), "链接目标不存在：{}", target.display());
    #[cfg(unix)]
    std::os::unix::fs::symlink(target, dest)?;
    #[cfg(windows)]
    {
        let output = std::process::Command::new("cmd")
            .args(["/D", "/C", "mklink", "/J"])
            .arg(dest)
            .arg(target)
            .output()?;
        ensure!(
            output.status.success(),
            "mklink: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(())
}
pub fn remove(dest: &Path) -> Result<()> {
    ensure!(
        matches!(classify(dest)?, State::Link(_)),
        "只允许移除链接：{}",
        dest.display()
    );
    #[cfg(unix)]
    fs::remove_file(dest)?;
    #[cfg(windows)]
    fs::remove_dir(dest)?;
    Ok(())
}
