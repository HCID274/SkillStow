use crate::{
    Edit,
    config::{self, Local, Manifest},
    link::{self, State},
    plan::{self, Action},
    repo,
};
use anyhow::{Context, Result, ensure};
use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

// 配置目录隔离各设备状态；Git worktree 保存已发布内容，编辑不会改变工具正在读取的包。
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
fn manifest(root: &Path) -> Result<Manifest> {
    let m: Manifest = config::read(&root.join("skillstow.toml"))?;
    m.validate(root)?;
    Ok(m)
}
fn validate_local(c: &Local, m: &Manifest) -> Result<()> {
    let d = m.devices.get(&c.device).context("本设备未登记在共享清单")?;
    ensure!(
        d.platform == std::env::consts::OS,
        "本设备平台与清单不符：{}",
        d.platform
    );
    for t in &c.tools {
        ensure!(m.tools.contains_key(t), "未知工具：{t}");
    }
    for t in c.overrides.keys() {
        ensure!(c.tools.contains(t), "override 工具未启用：{t}");
    }
    Ok(())
}
fn actions(c: &Local, m: &Manifest, active: &Path) -> Result<Vec<Action>> {
    let selected = m.resolve(&c.device)?;
    let mut current = BTreeMap::new();
    let mut desired = BTreeMap::new();
    let mut blocked = Vec::new();
    for tool in &c.tools {
        let dir = config::expand(c.overrides.get(tool).unwrap_or(&m.tools[tool].path))?;
        ensure!(dir.is_absolute(), "工具路径必须是绝对路径或 ~/ 路径");
        ensure!(
            !dir.starts_with(&c.repo)
                && !c.repo.starts_with(&dir)
                && !dir.starts_with(active)
                && !active.starts_with(&dir),
            "工具目录不能与维护仓或发布目录重叠"
        );
        match link::classify(&dir)? {
            State::Missing => {}
            State::Directory => {
                for e in fs::read_dir(&dir)? {
                    let e = e?;
                    // 宿主 .system、插件等隐藏目录不归个人 Skills 同步管理。
                    if !e.file_name().to_string_lossy().starts_with('.') {
                        current.insert(e.path(), link::classify(&e.path())?);
                    }
                }
            }
            _ => {
                blocked.push(Action::Blocked(dir));
                continue;
            }
        }
        for (name, path) in &selected {
            if !m.exclude.get(name).is_some_and(|ts| ts.contains(tool)) {
                desired.insert(dir.join(name), active.join(path));
            }
        }
    }
    blocked.extend(plan::compare(active, &current, &desired));
    Ok(blocked)
}
fn activate(p: &Path, c: &Local, sha: &str) -> Result<usize> {
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
    let m = manifest(&active)?;
    let mut published = config::load(p)?;
    published.repo = active.clone();
    let plan = actions(&published, &m, &active)?;
    let mut pending = String::from("# SkillStow 待处理\n\n");
    let mut count = 0;
    for a in plan {
        match a {
            Action::Create(dest, target) => {
                fs::create_dir_all(dest.parent().unwrap())?;
                link::create(&target, &dest)?;
            }
            Action::Remove(dest) => link::remove(&dest)?,
            Action::Blocked(dest) => {
                count += 1;
                pending.push_str(&format!("- 保留未受管路径，尚未应用：{}\n", dest.display()));
            }
        }
    }
    fs::write(state(p, "pending.md")?, pending)?;
    fs::write(
        state(p, "receipt.toml")?,
        format!("commit = {sha:?}\napplied = false\n"),
    )?;
    if count == 0 {
        hook(&c.after_apply, &active).context("提交已发布，本机应用尚未完成")?;
    }
    let receipt = format!(
        "device = {:?}\ncommit = {:?}\napplied = {}\nchecked_at = {}\n",
        c.device,
        sha,
        count == 0,
        SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs()
    );
    fs::write(state(p, "receipt.toml")?, receipt)?;
    println!(
        "publication=published commit={sha} device={} application={} pending={count}",
        c.device,
        if count == 0 { "applied" } else { "blocked" }
    );
    Ok(count)
}
pub fn init(p: &Path, repo: PathBuf, device: String, tools: Vec<String>) -> Result<i32> {
    ensure!(!p.exists(), "配置已存在；请编辑已有配置，不覆盖");
    config::safe_name(&device)?;
    let c = Local {
        repo: config::expand(&repo)?.canonicalize()?,
        device,
        tools,
        overrides: BTreeMap::new(),
        after_apply: Vec::new(),
        before_publish: Vec::new(),
    };
    repo::check(&c.repo)?;
    let m = manifest(&c.repo)?;
    validate_local(&c, &m)?;
    fs::create_dir_all(p.parent().context("配置缺少父目录")?)?;
    fs::write(p, toml::to_string_pretty(&c)?)?;
    sync(p, "skillstow: 初始化", false, false)
}
fn perform(p: &Path, message: &str, approve_removals: bool) -> Result<i32> {
    let c = config::load(p)?;
    repo::check(&c.repo)?;
    // 先验证在线和本地契约；验证失败不创建提交，也不修改活动目录。
    repo::fetch(&c.repo)?;
    let m = manifest(&c.repo)?;
    validate_local(&c, &m)?;
    hook(&c.before_publish, &c.repo)?;
    repo::commit(&c.repo, message)?;
    for attempt in 0..3 {
        repo::rebase(&c.repo)?;
        let m = manifest(&c.repo)?;
        validate_local(&c, &m)?;
        repo::files(&c.repo)?;
        for skill in m.skills.values() {
            for v in skill.variants.values() {
                ensure!(
                    repo::git(
                        &c.repo,
                        &[
                            "ls-files",
                            "--others",
                            "--ignored",
                            "--exclude-standard",
                            "--",
                            repo::path(&v.path)?
                        ]
                    )?
                    .is_empty(),
                    "包内资源被 gitignore 排除：{}",
                    v.path.display()
                );
            }
        }
        hook(&c.before_publish, &c.repo)?;
        let removals = report_impact(&c, &m)?;
        ensure!(
            !removals || approve_removals,
            "包含删除或版本替换；核对 impact 并取得发起端授权后使用 --approve-removals"
        );
        let sha = repo::git(&c.repo, &["rev-parse", "HEAD"])?;
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
                let pending = activate(p, &c, &sha)?;
                return Ok(if pending == 0 { 0 } else { 1 });
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
    perform(p, message, approve_removals)
}
pub fn edit(p: &Path, command: Edit) -> Result<i32> {
    let _lock = lock(p)?;
    let marker = state(p, "editing")?;
    match command {
        Edit::Begin => {
            ensure!(!marker.exists(), "已有维护任务；继续编辑后运行 edit finish");
            let code = perform(p, "skillstow: 维护前同步", false)?;
            ensure!(code == 0, "本机应用尚有阻塞，请先处理 pending.md");
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
            let code = perform(p, &message, approve_removals)?;
            if code == 0 {
                fs::remove_file(marker)?;
            }
            Ok(code)
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
    let m = manifest(&c.repo)?;
    validate_local(&c, &m)?;
    let pending = actions(&c, &m, &state(p, "published")?)?;
    let dirty = repo::dirty(&c.repo)?;
    let sha = repo::git(&c.repo, &["rev-parse", "HEAD"])?;
    let active = state(p, "published")?;
    let receipt: toml::Value = fs::read_to_string(state(p, "receipt.toml")?)
        .ok()
        .and_then(|text| toml::from_str(&text).ok())
        .unwrap_or(toml::Value::Table(Default::default()));
    let applied = receipt.get("applied").and_then(toml::Value::as_bool) == Some(true)
        && receipt.get("commit").and_then(toml::Value::as_str) == Some(sha.as_str())
        && active.exists()
        && repo::git(&active, &["rev-parse", "HEAD"])? == sha
        && !repo::dirty(&active)?;
    let upstream = repo::git(&c.repo, &["rev-parse", "origin/main"])?;
    println!(
        "device={} head={sha} local_changes={dirty} applied={applied} planned_actions={} editing={}\n远端状态仅为最近 fetch；其他设备应用状态未知。",
        c.device,
        pending.len(),
        state(p, "editing")?.exists()
    );
    for a in &pending {
        println!("{a:?}");
    }
    Ok(
        if !dirty && applied && pending.is_empty() && upstream == sha {
            0
        } else {
            1
        },
    )
}

fn report_impact(c: &Local, candidate: &Manifest) -> Result<bool> {
    let old: Manifest = toml::from_str(&repo::git(
        &c.repo,
        &["show", "origin/main:skillstow.toml"],
    )?)?;
    let changed = repo::git(&c.repo, &["diff", "--name-only", "-z", "origin/main", "--"])?;
    let deleted = repo::git(
        &c.repo,
        &[
            "diff",
            "--name-only",
            "--diff-filter=D",
            "origin/main",
            "--",
        ],
    )?;
    let devices: std::collections::BTreeSet<_> =
        old.devices.keys().chain(candidate.devices.keys()).collect();
    let mut destructive = false;
    for device in devices {
        let before = if old.devices.contains_key(device) {
            old.resolve(device)?
        } else {
            BTreeMap::new()
        };
        let after = if candidate.devices.contains_key(device) {
            candidate.resolve(device)?
        } else {
            BTreeMap::new()
        };
        let touches = |paths: &str| {
            paths.split('\0').filter(|s| !s.is_empty()).any(|file| {
                before
                    .values()
                    .chain(after.values())
                    .any(|root| Path::new(file).starts_with(root))
            })
        };
        let removal = before.iter().any(|(s, p)| after.get(s) != Some(p)) || touches(&deleted);
        let affected = before != after || touches(&changed);
        if affected {
            println!("impact device={device} removal_or_replacement={removal}");
        }
        destructive |= removal;
    }
    Ok(destructive)
}
pub fn impact(p: &Path) -> Result<i32> {
    let c = config::load(p)?;
    let m = manifest(&c.repo)?;
    report_impact(&c, &m)?;
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

fn hook(args: &[String], cwd: &Path) -> Result<()> {
    if let Some(program) = args.first() {
        ensure!(
            std::process::Command::new(program)
                .args(&args[1..])
                .current_dir(cwd)
                .stdin(std::process::Stdio::null())
                .status()?
                .success(),
            "本机校验/应用钩子失败：{program}"
        );
    }
    Ok(())
}
