use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Component, Path, PathBuf},
};

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Local {
    pub repo: PathBuf,
    pub device: String,
    pub tools: Vec<String>,
    #[serde(default)]
    pub after_apply: Vec<String>,
    #[serde(default)]
    pub before_publish: Vec<String>,
    #[serde(default)]
    pub module_adapter: Vec<String>,
    #[serde(default)]
    pub overrides: BTreeMap<String, PathBuf>,
}
#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    #[serde(default)]
    pub tools: BTreeMap<String, Tool>,
    #[serde(default)]
    pub exclude: BTreeMap<String, Vec<String>>,
    #[serde(default)]
    pub skills: BTreeMap<String, Skill>,
    #[serde(default)]
    pub devices: BTreeMap<String, Device>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Tool {
    pub path: PathBuf,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Skill {
    #[serde(default)]
    pub requires: Vec<String>,
    pub variants: BTreeMap<String, Variant>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Variant {
    pub path: PathBuf,
    pub platform: Option<String>,
    pub device: Option<String>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Device {
    pub platform: String,
    pub enabled: Vec<String>,
    #[serde(default)]
    pub variants: BTreeMap<String, String>,
}
pub fn config_path() -> Result<PathBuf> {
    if let Some(p) = std::env::var_os("SKILLSTOW_CONFIG") {
        return Ok(p.into());
    }
    Ok(dirs::config_dir()
        .context("找不到配置目录")?
        .join("skillstow/config.toml"))
}
pub fn expand(p: &Path) -> Result<PathBuf> {
    if let Ok(rest) = p.strip_prefix("~") {
        return Ok(dirs::home_dir().context("找不到 home")?.join(rest));
    }
    Ok(p.to_path_buf())
}
pub fn read<T: serde::de::DeserializeOwned>(p: &Path) -> Result<T> {
    toml::from_str(&fs::read_to_string(p).with_context(|| format!("读取 {}", p.display()))?)
        .with_context(|| format!("解析 {}", p.display()))
}
pub fn load(p: &Path) -> Result<Local> {
    let mut c: Local = read(p)?;
    c.repo = expand(&c.repo)?
        .canonicalize()
        .context("仓库不存在，请先 init")?;
    Ok(c)
}
pub fn safe_name(s: &str) -> Result<()> {
    ensure!(
        !s.is_empty()
            && !s.starts_with('.')
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'),
        "无效逻辑名称：{s}"
    );
    Ok(())
}
pub fn package(root: &Path, p: &Path) -> Result<()> {
    ensure!(
        !p.as_os_str().is_empty() && p.components().all(|c| matches!(c, Component::Normal(_))),
        "包路径必须是仓库内相对路径：{}",
        p.display()
    );
    let mut cursor = root.to_path_buf();
    for part in p.components() {
        cursor.push(part);
        ensure!(
            !fs::symlink_metadata(&cursor)?.file_type().is_symlink(),
            "包路径不允许链接：{}",
            cursor.display()
        );
    }
    ensure!(
        cursor.join("SKILL.md").is_file(),
        "缺少 SKILL.md：{}",
        cursor.display()
    );
    validate_files(&cursor)
}
fn validate_files(p: &Path) -> Result<()> {
    let mut names = BTreeSet::new();
    for e in fs::read_dir(p)? {
        let e = e?;
        let name = e
            .file_name()
            .into_string()
            .map_err(|_| anyhow::anyhow!("非 UTF-8 文件名"))?;
        ensure!(
            names.insert(name.to_lowercase()),
            "大小写碰撞：{}",
            e.path().display()
        );
        let stem = name.split('.').next().unwrap_or("").to_uppercase();
        let reserved = ["CON", "PRN", "AUX", "NUL"].contains(&stem.as_str())
            || (1..=9).any(|n| stem == format!("COM{n}") || stem == format!("LPT{n}"));
        ensure!(
            !reserved
                && !name.ends_with(['.', ' '])
                && !name.chars().any(|c| c < ' ' || "<>:\"\\|?*".contains(c)),
            "Windows 不兼容名称：{name}"
        );
        let t = e.file_type()?;
        ensure!(
            !t.is_symlink() && (t.is_dir() || t.is_file()),
            "请固化链接或移除特殊文件：{}",
            e.path().display()
        );
        if t.is_dir() {
            validate_files(&e.path())?;
        }
    }
    Ok(())
}
impl Manifest {
    pub fn resolve(&self, device: &str) -> Result<BTreeMap<String, PathBuf>> {
        let d = self
            .devices
            .get(device)
            .with_context(|| format!("未定义设备 {device}；先在 skillstow.toml 中添加设备清单"))?;
        ensure!(
            ["macos", "windows", "linux"].contains(&d.platform.as_str()),
            "未知平台 {}",
            d.platform
        );
        let mut out = BTreeMap::new();
        let mut visiting = BTreeSet::new();
        for s in &d.enabled {
            self.visit(s, device, d, &mut visiting, &mut out)?;
        }
        for s in d.variants.keys() {
            ensure!(out.contains_key(s), "override 引用了未启用的 Skill：{s}");
        }
        Ok(out)
    }
    fn visit(
        &self,
        name: &str,
        device: &str,
        d: &Device,
        visiting: &mut BTreeSet<String>,
        out: &mut BTreeMap<String, PathBuf>,
    ) -> Result<()> {
        if out.contains_key(name) {
            return Ok(());
        }
        ensure!(visiting.insert(name.into()), "依赖循环：{name}");
        let s = self
            .skills
            .get(name)
            .with_context(|| format!("不存在的 Skill：{name}"))?;
        let compatible = |v: &&Variant| {
            v.platform.as_ref().is_none_or(|p| p == &d.platform)
                && v.device.as_ref().is_none_or(|id| id == device)
        };
        let v = if let Some(id) = d.variants.get(name) {
            let v = s.variants.get(id).context("不存在的 variant override")?;
            ensure!(compatible(&v), "override 与设备不兼容：{name}/{id}");
            v
        } else {
            let mut candidates: Vec<_> = s.variants.values().filter(compatible).collect();
            let priority = |v: &Variant| {
                if v.device.is_some() {
                    2
                } else {
                    v.platform.is_some() as u8
                }
            };
            candidates.sort_by_key(|v| priority(v));
            let v = candidates
                .pop()
                .with_context(|| format!("设备 {device} 没有兼容版本：{name}"))?;
            if let Some(other) = candidates.last() {
                ensure!(priority(v) != priority(other), "同层 variant 冲突：{name}");
            }
            v
        };
        for dep in &s.requires {
            self.visit(dep, device, d, visiting, out)?;
        }
        visiting.remove(name);
        out.insert(name.into(), v.path.clone());
        Ok(())
    }
    pub fn validate(&self, root: &Path) -> Result<()> {
        let mut names = BTreeSet::new();
        let mut roots: Vec<PathBuf> = Vec::new();
        for (name, skill) in &self.skills {
            safe_name(name)?;
            ensure!(
                names.insert(name.to_lowercase()),
                "Skill 名大小写碰撞：{name}"
            );
            ensure!(!skill.variants.is_empty(), "Skill 没有版本：{name}");
            for dep in &skill.requires {
                ensure!(self.skills.contains_key(dep), "缺失依赖：{dep}");
            }
            for (id, v) in &skill.variants {
                safe_name(id)?;
                package(root, &v.path)?;
                ensure!(
                    roots
                        .iter()
                        .all(|p| !p.starts_with(&v.path) && !v.path.starts_with(p)),
                    "包目录重复或重叠：{}",
                    v.path.display()
                );
                roots.push(v.path.clone());
                if let Some(p) = &v.platform {
                    ensure!(
                        ["macos", "windows", "linux"].contains(&p.as_str()),
                        "未知平台：{p}"
                    );
                }
                if let Some(d) = &v.device {
                    ensure!(self.devices.contains_key(d), "未知 variant 设备：{d}");
                }
            }
        }
        for d in self.devices.keys() {
            safe_name(d)?;
            self.resolve(d)?;
        }
        for (s, tools) in &self.exclude {
            ensure!(self.skills.contains_key(s), "exclude 引用了未知 Skill：{s}");
            for tool in tools {
                ensure!(
                    self.tools.contains_key(tool),
                    "exclude 引用了未知工具：{tool}"
                );
            }
        }
        Ok(())
    }
}
