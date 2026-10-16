use std::process::Command;

/// A `git` command for tests that make commits or tags in temporary
/// repositories. The account's own global and system git config (commit
/// signing, its identity) must not reach a test: a signing account would
/// otherwise fail every commit made here.
pub(crate) fn command() -> Command {
    let mut command = Command::new("git");
    command
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_CONFIG_SYSTEM", "/dev/null")
        .env("GIT_AUTHOR_NAME", "FleetDeck Test")
        .env("GIT_AUTHOR_EMAIL", "herdr@example.invalid")
        .env("GIT_COMMITTER_NAME", "FleetDeck Test")
        .env("GIT_COMMITTER_EMAIL", "herdr@example.invalid")
        .args(["-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]);
    command
}
