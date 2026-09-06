use crate::link::State;
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
};

#[derive(Debug, PartialEq)]
pub enum Action {
    Create(PathBuf, PathBuf),
    Remove(PathBuf),
    Blocked(PathBuf),
}
pub fn compare(
    root: &Path,
    current: &BTreeMap<PathBuf, State>,
    desired: &BTreeMap<PathBuf, PathBuf>,
) -> Vec<Action> {
    let keys: BTreeSet<_> = current.keys().chain(desired.keys()).collect();
    let mut out = Vec::new();
    for p in keys {
        let want = desired.get(p);
        match current.get(p).unwrap_or(&State::Missing) {
            State::Missing => {
                if let Some(t) = want {
                    out.push(Action::Create(p.clone(), t.clone()));
                }
            }
            State::Link(t) if t.starts_with(root) && t != root => {
                if want != Some(t) {
                    out.push(Action::Remove(p.clone()));
                    if let Some(t) = want {
                        out.push(Action::Create(p.clone(), t.clone()));
                    }
                }
            }
            _ => out.push(Action::Blocked(p.clone())),
        }
    }
    out
}
