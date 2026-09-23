use crate::{
    Edit,
    config::{self, Local},
    repo,
};
use anyhow::{Context, Result, ensure};
use std::{
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

// 配置目录隔离各设备状态；Git worktree 保存已发布内容，编辑不会改变客户端正在读取的包。
fn state(p: &Path, name: &str) -> Result<PathBuf> {
    Ok(p.parent().context("配置路径缺少父目录")?.join(name))
}
struct Lock(PathBuf);
impl Drop for Lock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}
fn lock(p: &Path) -> Result<Lock> {
    let path = state(p, "sync.lock")?;
    fs::create_dir_all(path.parent().unwrap())?;
    fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .context("同步已在运行；若上次进程被强制结束，确认它已退出后移除 sync.lock")?;
    Ok(Lock(path))
}
fn receipt(c: &Local, sha: &str, applied: bool) -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    format!(
        "device = {:?}\ncommit = {sha:?}\napplied = {applied}\nchecked_at = {now}\n",
        c.device
    )
}
// 收据、发布目录和提交三者一致才算本机已应用该版本。
fn applied(p: &Path, sha: &str) -> Result<bool> {
    let active = state(p, "published")?;
    let receipt: toml::Value = fs::read_to_string(state(p, "receipt.toml")?)
        .ok()
        .and_then(|text| toml::from_str(&text).ok())
        .unwrap_or(toml::Value::Table(Default::default()));
    Ok(
        receipt.get("applied").and_then(toml::Value::as_bool) == Some(true)
            && receipt.get("commit").and_then(toml::Value::as_str) == Some(sha)
            && active.exists()
            && repo::git(&active, &["rev-parse", "HEAD"])? == sha
            && !repo::dirty(&active)?,
    )
}
fn activate(p: &Path, c: &Local, sha: &str) -> Result<()> {
    let active = state(p, "published")?;
    if active.exists() {
        ensure!(
            !repo::dirty(&active)?,
            "已发布目录存在外部修改；请移回维护仓处理：{}",
            active.display()
        );
        let common = repo::git(
            &active,
            &["rev-parse", "--path-format=absolute", "--git-common-dir"],
        )?;
        ensure!(
            Path::new(&common).canonicalize()?
                == Path::new(&repo::git(
                    &c.repo,
                    &["rev-parse", "--path-format=absolute", "--git-common-dir"]
                )?)
                .canonicalize()?,
            "发布目录属于其他仓库"
        );
        repo::git(&active, &["checkout", "--detach", sha])?;
    } else {
        repo::git(
            &c.repo,
            &["worktree", "add", "--detach", repo::path(&active)?, sha],
        )?;
    }
    fs::write(state(p, "receipt.toml")?, receipt(c, sha, false))?;
    ensure!(
        module_run(c, &active, &["apply", "--device", &c.device])? == 0,
        "提交已发布，本机应用尚未完成"
    );
    fs::write(state(p, "receipt.toml")?, receipt(c, sha, true))?;
    println!(
        "publication=published commit={sha} device={} application=applied",
        c.device
    );
    Ok(())
}
pub fn init(p: &Path, repo: PathBuf, device: String, adapter: Vec<String>) -> Result<i32> {
    ensure!(!p.exists(), "配置已存在；请编辑已有配置，不覆盖");
    config::safe_name(&device)?;
    let c = Local {
        repo: config::expand(&repo)?.canonicalize()?,
        device,
        module_adapter: adapter,
    };
    repo::check(&c.repo)?;
    fs::create_dir_all(p.parent().context("配置缺少父目录")?)?;
    fs::write(p, toml::to_string_pretty(&c)?)?;
    sync(p, "skillstow: 初始化", false, false)
}
fn perform(p: &Path, message: &str, approve_removals: bool, background: bool) -> Result<i32> {
    let c = config::load(p)?;
    repo::check(&c.repo)?;
    repo::fetch(&c.repo)?;
    // 后台每分钟调用：无本地修改、无远端更新且本机已应用时静默结束，不重复校验和应用。
    let head = repo::git(&c.repo, &["rev-parse", "HEAD"])?;
    if background
        && !repo::dirty(&c.repo)?
        && head == repo::git(&c.repo, &["rev-parse", "origin/main"])?
        && applied(p, &head)?
    {
        return Ok(0);
    }
    // 先验证本地候选；验证失败不创建提交，也不修改活动目录。
    validate(&c)?;
    repo::commit(&c.repo, message)?;
    for attempt in 0..3 {
        repo::rebase(&c.repo)?;
        repo::files(&c.repo)?;
        validate(&c)?;
        let removals = match module_run(&c, &c.repo, &["impact"])? {
            0 => false,
            3 => true,
            code => anyhow::bail!("模块影响分析失败：{code}"),
        };
        ensure!(
            !removals || approve_removals,
            "包含删除或范围收缩；核对 impact 并取得发起端授权后使用 --approve-removals"
        );
        let sha = repo::git(&c.repo, &["rev-parse", "HEAD"])?;
        // 接收已发布版本时只需应用，避免重复 push 和再次 fetch。
        if sha == repo::git(&c.repo, &["rev-parse", "origin/main"])? {
            ensure!(!repo::dirty(&c.repo)?, "应用前出现新修改，请继续同步");
            activate(p, &c, &sha)?;
            return Ok(0);
        }
        match repo::git(&c.repo, &["push", "origin", "HEAD:refs/heads/main"]) {
            Ok(_) => {
                // push 后再次确认 main 包含该提交；网络不确定时保留事务供重试。
                repo::fetch(&c.repo)?;
                repo::git(
                    &c.repo,
                    &["merge-base", "--is-ancestor", &sha, "origin/main"],
                )?;
                ensure!(
                    !repo::dirty(&c.repo)?,
                    "发布期间出现新修改，请继续同步；本次已发布 {sha}"
                );
                activate(p, &c, &sha)?;
                return Ok(0);
            }
            Err(e) => {
                if attempt == 2 {
                    return Err(e);
                }
                let previous = repo::git(&c.repo, &["rev-parse", "origin/main"])?;
                repo::fetch(&c.repo)?;
                if previous == repo::git(&c.repo, &["rev-parse", "origin/main"])? {
                    return Err(e);
                }
            }
        }
    }
    unreachable!()
}
pub fn sync(p: &Path, message: &str, background: bool, approve_removals: bool) -> Result<i32> {
    let _lock = lock(p)?;
    if state(p, "editing")?.exists() {
        if background {
            println!("editing: 后台同步暂停");
            return Ok(0);
        }
        anyhow::bail!("AI 维护尚未结束，请使用 edit finish 或 edit cancel");
    }
    if background && !quiet(p)? {
        println!("等待 60 秒静默窗口");
        return Ok(0);
    }
    perform(p, message, approve_removals, background)
}
pub fn edit(p: &Path, command: Edit) -> Result<i32> {
    let _lock = lock(p)?;
    let marker = state(p, "editing")?;
    match command {
        Edit::Begin => {
            ensure!(!marker.exists(), "已有维护任务；继续编辑后运行 edit finish");
            perform(p, "skillstow: 维护前同步", false, false)?;
            let c = config::load(p)?;
            fs::write(&marker, repo::git(&c.repo, &["rev-parse", "HEAD"])?)?;
            println!("edit_path={}", c.repo.display());
            Ok(0)
        }
        Edit::Finish {
            message,
            approve_removals,
        } => {
            ensure!(marker.exists(), "没有维护任务，请先 edit begin");
            perform(p, &message, approve_removals, false)?;
            fs::remove_file(marker)?;
            Ok(0)
        }
        Edit::Cancel => {
            ensure!(marker.exists(), "没有维护任务");
            // 取消不会删除修改；后台仍应暂停，直到用户明确完成或手动同步。
            fs::write(marker, "cancelled-with-changes\n")?;
            println!("修改已保留，后台暂停；继续时运行 edit finish");
            Ok(0)
        }
    }
}
pub fn status(p: &Path) -> Result<i32> {
    let c = config::load(p)?;
    repo::check(&c.repo)?;
    let dirty = repo::dirty(&c.repo)?;
    let sha = repo::git(&c.repo, &["rev-parse", "HEAD"])?;
    let applied = applied(p, &sha)?;
    let upstream = repo::git(&c.repo, &["rev-parse", "origin/main"])?;
    println!(
        "device={} head={sha} local_changes={dirty} applied={applied} editing={}\n远端状态仅为最近 fetch；其他设备应用状态未知。",
        c.device,
        state(p, "editing")?.exists()
    );
    Ok(if !dirty && applied && upstream == sha {
        0
    } else {
        1
    })
}
pub fn impact(p: &Path) -> Result<i32> {
    let c = config::load(p)?;
    let code = module_run(&c, &c.repo, &["impact"])?;
    ensure!(code == 0 || code == 3, "模块影响分析失败：{code}");
    println!("相对最近 fetch 的 origin/main；未跟踪文件将在同步提交后纳入最终影响分析。");
    Ok(0)
}

fn quiet(p: &Path) -> Result<bool> {
    use std::hash::{Hash, Hasher};
    let c = config::load(p)?;
    if !repo::dirty(&c.repo)? {
        return Ok(true);
    }
    let mut h = std::collections::hash_map::DefaultHasher::new();
    repo::git(&c.repo, &["diff", "--binary", "HEAD"])?.hash(&mut h);
    for file in repo::git(
        &c.repo,
        &["ls-files", "--others", "--exclude-standard", "-z"],
    )?
    .split('\0')
    .filter(|s| !s.is_empty())
    {
        file.hash(&mut h);
        fs::read(c.repo.join(file))?.hash(&mut h);
    }
    let fingerprint = h.finish().to_string();
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    let stamp = state(p, "quiet")?;
    if let Ok(old) = fs::read_to_string(&stamp)
        && let Some((hash, time)) = old.split_once(' ')
        && hash == fingerprint
    {
        return Ok(now.saturating_sub(time.parse::<u64>()?) >= 60);
    }
    fs::write(stamp, format!("{fingerprint} {now}"))?;
    Ok(false)
}

fn validate(c: &Local) -> Result<()> {
    ensure!(
        module_run(c, &c.repo, &["validate"])? == 0,
        "模块校验失败，未发布"
    );
    Ok(())
}
// 只执行本机安装并明确配置的适配器，不执行内容仓中的任意程序。
fn module_run(c: &Local, repo: &Path, args: &[&str]) -> Result<i32> {
    Ok(std::process::Command::new(&c.module_adapter[0])
        .args(&c.module_adapter[1..])
        .arg("--repo")
        .arg(repo)
        .args(args)
        .stdin(std::process::Stdio::null())
        .status()
        .with_context(|| format!("运行模块适配器 {}", c.module_adapter[0]))?
        .code()
        .unwrap_or(2))
}
pub fn module(p: &Path, args: &[&str]) -> Result<i32> {
    let c = config::load(p)?;
    module_run(&c, &c.repo, args)
}
