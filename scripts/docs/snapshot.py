"""Copy a documentation tree out of a git commit, and compare a copy with it.

The library preview.py and versions.py share; it has no command of its own.
Ported from snapshot.mjs (agent-fabric ADR-040 rule 10, Wave 10).

A snapshot holds ordinary files only: a tree entry that is not a 100644 blob
(an executable, a symlink, a submodule) is refused, and so is a file in the
snapshot that is not a regular file or directory, so a link can never carry
a published page outside the tree it claims to copy.

Every failure is a DocsError; a git command that fails raises
subprocess.CalledProcessError with git's stderr captured; run() reports
either as exit 1.
"""
from __future__ import annotations

import os
import posixpath
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class DocsError(Exception):
    """A documentation snapshot or manifest that does not hold its contract."""


Git = Callable[..., "str | bytes"]


def create_git(repo_root: Path) -> Git:
    def git(args: list[str], *, binary: bool = False) -> str | bytes:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        )
        if binary:
            return completed.stdout
        return completed.stdout.decode("utf-8", errors="surrogateescape")

    return git


def resolve_commit(git: Git, ref: str) -> str:
    return git(["rev-parse", f"{ref}^{{commit}}"]).strip()


def git_path_exists(git: Git, ref: str, path: str) -> bool:
    try:
        git(["cat-file", "-e", f"{ref}:{path}"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


def git_trees_equal(git: Git, ref: str, left: str, right: str) -> bool:
    try:
        git(["diff", "--quiet", f"{ref}:{left}", f"{ref}:{right}"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


@dataclass(frozen=True)
class GitEntry:
    mode: str
    type: str
    object: str
    path: str


def list_git_entries(git: Git, ref: str, root: str) -> list[GitEntry]:
    entries = []
    for line in git(["ls-tree", "-r", "-z", ref, "--", root]).split("\0"):
        if not line:
            continue
        header, path = line.split("\t", 1)
        mode, kind, obj = header.split(" ")
        entries.append(GitEntry(mode, kind, obj, path))
    return entries


def extract_git_tree(git: Git, ref: str, source_root: str, destination_root: Path) -> None:
    entries = list_git_entries(git, ref, source_root)
    if not entries:
        raise DocsError(f"{ref}:{source_root} contains no files")

    remove_tree(destination_root)
    for entry in entries:
        assert_ordinary_file(entry, ref)
        relative_path = snapshot_relative_path(source_root, entry.path)
        destination = destination_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(git(["cat-file", "blob", entry.object], binary=True))


def compare_git_tree(git: Git, ref: str, source_root: str, snapshot_root: Path) -> None:
    expected_entries = list_git_entries(git, ref, source_root)
    if not expected_entries:
        raise DocsError(f"{ref}:{source_root} contains no files")

    expected: dict[str, GitEntry] = {}
    for entry in expected_entries:
        assert_ordinary_file(entry, ref)
        expected[snapshot_relative_path(source_root, entry.path)] = entry
    expected_paths = sorted(expected)
    if list_documentation_paths(snapshot_root) != expected_paths:
        raise DocsError(f"{snapshot_root} file list differs from {ref}:{source_root}")

    for relative_path in expected_paths:
        entry = expected[relative_path]
        expected_content = git(["cat-file", "blob", entry.object], binary=True)
        if (snapshot_root / relative_path).read_bytes() != expected_content:
            raise DocsError(f"{relative_path} differs from {ref}:{entry.path}")


def list_documentation_paths(root: Path) -> list[str]:
    """Every regular file under root, as a sorted list of /-separated paths.

    lstat does not follow links, so a symlink (or a Windows junction) is
    neither a directory nor a file here and is refused rather than walked.
    A missing root raises FileNotFoundError: a published version without its
    documentation directory is a failure, not an empty snapshot.
    """
    paths: list[str] = []

    def walk(directory: Path, prefix: str) -> None:
        for name in os.listdir(directory):
            path = directory / name
            mode = os.lstat(path).st_mode
            if stat.S_ISDIR(mode):
                walk(path, f"{prefix}{name}/")
            elif stat.S_ISREG(mode):
                paths.append(f"{prefix}{name}")
            else:
                raise DocsError(f"{path} is not an ordinary documentation file")

    walk(root, "")
    return sorted(paths)


def remove_tree(path: Path) -> None:
    """Remove path whatever it is, and nothing when it does not exist."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return
    if stat.S_ISDIR(mode):
        shutil.rmtree(path)
    else:
        path.unlink()


def assert_ordinary_file(entry: GitEntry, ref: str) -> None:
    if entry.type != "blob" or entry.mode != "100644":
        raise DocsError(f"{ref}:{entry.path} is not an ordinary documentation file")


def is_schema_version_one(value: object) -> bool:
    # JSON true is not the schema version 1, though Python's True == 1.
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value == 1


def repo_root_from_environment(script: Path) -> Path:
    override = os.environ.get("HERDR_DOCS_REPO_ROOT")
    if override:
        return Path(os.path.abspath(override))
    # abspath, not resolve: like the .mjs, a symlinked checkout keeps its path.
    return Path(os.path.abspath(script)).parent.parent.parent


def run(main: Callable[[list[str]], None], argv: list[str]) -> int:
    """Run a command's main, reporting a failure on stderr as exit 1."""
    try:
        main(argv)
    except subprocess.CalledProcessError as error:
        command = " ".join(error.cmd)
        detail = error.stderr.decode("utf-8", errors="replace") if error.stderr else ""
        print(f"error: Command failed: {command}\n{detail}".rstrip(), file=sys.stderr)
        return 1
    except (DocsError, OSError, ValueError) as error:
        # ValueError covers a manifest that is not JSON (JSONDecodeError).
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def snapshot_relative_path(source_root: str, path: str) -> str:
    # git names tree paths with "/" on every platform, so the relation is
    # computed as POSIX paths, never with the host's separator.
    relative_path = posixpath.relpath(path, source_root)
    if not relative_path or relative_path == "." or relative_path == ".." or relative_path.startswith("../"):
        raise DocsError(f"unsafe snapshot path {path}")
    return relative_path
