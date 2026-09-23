mod cmd;
mod config;
mod repo;
use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(version, about = "个人 Skills 模块的多设备 Git 同步")]
struct Cli {
    #[arg(long, global = true)]
    config: Option<PathBuf>,
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    /// 写入本机配置并首次同步；`--` 之后是模块适配器 argv。
    Init {
        #[arg(long)]
        repo: PathBuf,
        #[arg(long)]
        device: String,
        #[arg(last = true, required = true)]
        adapter: Vec<String>,
    },
    Sync {
        #[arg(short, long, default_value = "skillstow: 同步 Skills")]
        message: String,
        #[arg(long)]
        background: bool,
        #[arg(long)]
        approve_removals: bool,
    },
    Status,
    Locate {
        skill: String,
    },
    Fleet,
    Impact,
    Edit {
        #[command(subcommand)]
        command: Edit,
    },
}
#[derive(Subcommand)]
enum Edit {
    Begin,
    Finish {
        #[arg(short, long, default_value = "skillstow: 更新 Skills")]
        message: String,
        #[arg(long)]
        approve_removals: bool,
    },
    Cancel,
}
fn main() {
    let cli = Cli::parse();
    let result = (|| {
        let p = cli.config.map(Ok).unwrap_or_else(config::config_path)?;
        match cli.command {
            Action::Init {
                repo,
                device,
                adapter,
            } => cmd::init(&p, repo, device, adapter),
            Action::Sync {
                message,
                background,
                approve_removals,
            } => cmd::sync(&p, &message, background, approve_removals),
            Action::Status => cmd::status(&p),
            Action::Locate { skill } => cmd::module(&p, &["locate", &skill]),
            Action::Fleet => cmd::module(&p, &["fleet"]),
            Action::Impact => cmd::impact(&p),
            Action::Edit { command } => cmd::edit(&p, command),
        }
    })();
    match result {
        Ok(code) => std::process::exit(code),
        Err(e) => {
            eprintln!("{e:#}");
            std::process::exit(2);
        }
    }
}
