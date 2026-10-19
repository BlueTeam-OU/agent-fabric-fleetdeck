#!/usr/bin/env python3
"""Snapshot and validate the active preview's documentation.

Ported from preview.mjs (agent-fabric ADR-040 rule 10, Wave 10). The contract
callers rely on (the preview, release and distribution workflows, `just`):

    python3 scripts/docs/preview.py snapshot <commit>
        Replace docs/preview/website/ with docs/next/website/ as it is in
        <commit>. <commit> must contain the staged website documentation and
        config reference. stdout: "snapshotted preview documentation from
        <full sha>".
    python3 scripts/docs/preview.py check
        Validate distribution/preview.json (schema_version 1, channel
        preview, a full commit SHA, its active build's commit and its
        "preview-<build_id>" tag) and that docs/preview/website/ is exactly
        docs/next/website/ at that commit. stdout: "validated preview
        documentation snapshot <sha>".

Environment: HERDR_DOCS_REPO_ROOT, when set and not empty, is the repository
to work on (the tests' fixtures); otherwise the checkout holding this file.

Exit 0 on success. Exit 1 on any failure, with the reason on stderr: a usage
error ("usage: python3 scripts/docs/preview.py check | snapshot <commit>"),
a contract violation, or a git command that failed (its command and stderr).
The .mjs printed a Node stack trace around the same message; the message is
the contract, the trace was not. There is no help flag.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if __package__:
    from . import snapshot
else:
    import snapshot

SOURCE_ROOT = "docs/next/website"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
USAGE = "usage: python3 scripts/docs/preview.py check | snapshot <commit>"


def snapshot_preview(repo_root: Path, ref: str) -> None:
    git = snapshot.create_git(repo_root)
    commit = snapshot.resolve_commit(git, ref)
    _require_staged_docs(git, commit)
    snapshot.extract_git_tree(git, commit, SOURCE_ROOT, _snapshot_root(repo_root))
    print(f"snapshotted preview documentation from {commit}")


def check_preview(repo_root: Path) -> None:
    git = snapshot.create_git(repo_root)
    manifest_path = repo_root / "distribution/preview.json"
    manifest = snapshot.load_json(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not snapshot.is_schema_version_one(manifest.get("schema_version")) or manifest.get("channel") != "preview":
        raise snapshot.DocsError(f"{manifest_path} has an unsupported schema")
    commit = manifest.get("commit")
    if not isinstance(commit, str) or not FULL_SHA.fullmatch(commit):
        raise snapshot.DocsError(f"{manifest_path} must contain a full preview commit SHA")
    builds = manifest.get("builds")
    build_id = manifest.get("build_id")
    build = builds.get(_js_key(build_id)) if isinstance(builds, dict) else None
    if not isinstance(build, dict) or build.get("commit") != commit:
        raise snapshot.DocsError(f"{manifest_path} active build does not match its preview commit")
    expected_tag = f"preview-{_js_key(build_id)}"
    if build.get("tag") != expected_tag:
        raise snapshot.DocsError(f"{manifest_path} active build tag does not match {expected_tag}")
    _require_staged_docs(git, commit)
    snapshot.compare_git_tree(git, commit, SOURCE_ROOT, _snapshot_root(repo_root))
    print(f"validated preview documentation snapshot {commit}")


def _require_staged_docs(git: snapshot.Git, commit: str) -> None:
    if not snapshot.git_path_exists(git, commit, f"{SOURCE_ROOT}/src/content/docs"):
        raise snapshot.DocsError(f"{commit} does not contain staged website documentation")
    if not snapshot.git_path_exists(git, commit, f"{SOURCE_ROOT}/src/data/config-reference.json"):
        raise snapshot.DocsError(f"{commit} does not contain the staged config reference")


def _snapshot_root(repo_root: Path) -> Path:
    return repo_root / "docs/preview/website"


def _js_key(value: object) -> str:
    # The .mjs indexed builds and built the tag with JavaScript's string
    # conversion of build_id; a missing or null id names no build.
    if value is None:
        return "undefined"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def main(argv: list[str]) -> None:
    command = argv[0] if argv else None
    value = argv[1] if len(argv) > 1 else None
    repo_root = snapshot.repo_root_from_environment(Path(__file__))
    if command == "snapshot" and value:
        snapshot_preview(repo_root, value)
    elif command == "check" and not value:
        check_preview(repo_root)
    else:
        raise snapshot.DocsError(USAGE)


if __name__ == "__main__":
    sys.exit(snapshot.run(main, sys.argv[1:]))
