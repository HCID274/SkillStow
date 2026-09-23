use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::{Path, PathBuf},
};

// 本机配置只描述维护仓、设备名和明确安装的模块适配器；Skill 清单归内容仓的适配器解释。
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Local {
    pub repo: PathBuf,
    pub device: String,
    pub module_adapter: Vec<String>,
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
pub fn load(p: &Path) -> Result<Local> {
    let text = fs::read_to_string(p).with_context(|| format!("读取 {}", p.display()))?;
    let mut c: Local = toml::from_str(&text).with_context(|| format!("解析 {}", p.display()))?;
    c.repo = expand(&c.repo)?
        .canonicalize()
        .context("仓库不存在，请先 init")?;
    ensure!(!c.module_adapter.is_empty(), "本机未配置 module_adapter");
    safe_name(&c.device)?;
    Ok(c)
}
pub fn safe_name(s: &str) -> Result<()> {
    ensure!(
        !s.is_empty()
            && !s.starts_with('.')
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'),
        "无效设备名：{s}"
    );
    Ok(())
}
