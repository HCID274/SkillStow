mod cmd;
mod config;
mod link;
mod plan;
mod repo;
use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(version, about = "完整 Skills 包的多设备 Git 同步")]
struct Cli {
    #[arg(long, global = true)]
    config: Option<PathBuf>,
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    Init {
        #[arg(long)]
        repo: PathBuf,
        #[arg(long)]
        device: String,
        #[arg(long, value_delimiter = ',')]
        tools: Vec<String>,
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
                tools,
            } => cmd::init(&p, repo, device, tools),
            Action::Sync {
                message,
                background,
                approve_removals,
            } => cmd::sync(&p, &message, background, approve_removals),
            Action::Status => cmd::status(&p),
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
