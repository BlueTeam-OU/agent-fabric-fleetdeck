#!/usr/bin/env python3
"""Publish, archive and validate the stable releases' documentation.

Ported from versions.mjs (agent-fabric ADR-040 rule 10, Wave 10). The
contract callers rely on (the release, preview and distribution workflows,
`just`):

    python3 scripts/docs/versions.py publish <tag>
        Snapshot docs/next/website/src/content/docs (and its config
        reference) at <tag> into docs/versions/<version>/website/ and record
        it in docs/versions/manifest.json. A version newer than the current
        one becomes current, its tagged docs/next README files replace the
        root ones, and stdout says "published documentation snapshot <tag>";
        an older one is archived without changing current ("archived
        documentation snapshot <tag> without changing current <version>").
        Publishing the current or an archived version again changes nothing
        and says it is "already published" or "already archived"; a commit
        that no longer matches its recorded provenance fails.
    python3 scripts/docs/versions.py backfill
        Snapshot every v* tag the manifest lacks, from docs/next when its
        tree differs from the legacy website/ one, and take current from
        distribution/latest.json. stdout: "snapshotted <tag>" per tag.
    python3 scripts/docs/versions.py check
        Validate the manifest against distribution/latest.json, the tags'
        commits and the snapshots on disk. stdout: "validated <n>
        documentation versions".
    python3 scripts/docs/versions.py current
        Print the manifest's current version, or an empty line.

A version is "0.7.5" or "v0.7.5"; the manifest is written as two-space JSON
with a final newline, its versions newest first.

Environment: HERDR_DOCS_REPO_ROOT, when set and not empty, is the repository
to work on (the tests' fixtures); otherwise the checkout holding this file.

Exit 0 on success. Exit 1 on any failure, with the reason on stderr: a usage
error ("usage: python3 scripts/docs/versions.py backfill | check | current |
publish <tag>"), a contract violation, or a git command that failed (its
command and stderr). The .mjs printed a Node stack trace around the same
message; the message is the contract, the trace was not. There is no help
flag.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__:
    from . import snapshot
else:
    import snapshot

DocsError = snapshot.DocsError

NEXT_ROOT = "docs/next/website/src/content/docs"
LEGACY_ROOT = "website/src/content/docs"
SOURCES = (LEGACY_ROOT, NEXT_ROOT)
FULL_SHA = re.compile(r"[0-9a-f]{40}")
# [0-9], not \d: \d also matches non-ASCII digits in Python.
VERSION_PATTERN = re.compile(r"v?([0-9]+\.[0-9]+\.[0-9]+)")
# FleetDeck has published no stable release, and the documentation versions
# here are all Herdr's, inherited at the fork (docs/fleetdeck/UPSTREAM.md).
NO_STABLE_RELEASE = "0.0.0"
USAGE = "usage: python3 scripts/docs/versions.py backfill | check | current | publish <tag>"


def normalize_version(value: object) -> str:
    match = VERSION_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise DocsError(f"version must look like 0.7.5 or v0.7.5, got {value}")
    return match.group(1)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def sort_versions_newest_first(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # sorted() is stable with reverse=True too, as the .mjs's sort was.
    return sorted(versions, key=lambda entry: _version_key(entry["version"]), reverse=True)


def _stable_source(manifest: dict[str, Any]) -> Any:
    source = manifest.get("stable_source")
    return "legacy" if source is None else source


class Versions:
    """One repository's documentation versions."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.versions_dir = repo_root / "docs/versions"
        self.manifest_path = self.versions_dir / "manifest.json"
        self.latest_manifest_path = repo_root / "distribution/latest.json"
        self.git = snapshot.create_git(repo_root)

    def read_manifest(self) -> dict[str, Any]:
        try:
            text = self.manifest_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"schema_version": 1, "stable_source": "legacy", "current": None, "versions": []}
        manifest = json.loads(text)
        if not isinstance(manifest, dict):
            raise DocsError(f"{self.manifest_path} has an unsupported schema")
        return manifest

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        manifest["versions"] = [_manifest_entry(entry) for entry in sort_versions_newest_first(manifest["versions"])]
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n", encoding="utf-8")

    def latest_version(self) -> Any:
        return json.loads(self.latest_manifest_path.read_text(encoding="utf-8")).get("version")

    def release_metadata(self, tag: str) -> dict[str, Any]:
        version = normalize_version(tag)
        normalized_tag = f"v{version}"
        return {"version": version, "tag": normalized_tag, "commit": snapshot.resolve_commit(self.git, normalized_tag)}

    def snapshot_tag(self, tag: str, source_root: str) -> dict[str, Any]:
        metadata = {**self.release_metadata(tag), "source": source_root}
        destination = self.versions_dir / metadata["version"]
        snapshot.remove_tree(destination)
        # The tag as given, not the normalized one, as the .mjs did: publish
        # and backfill always pass the v-prefixed tag.
        snapshot.extract_git_tree(self.git, tag, source_root, destination / "website/src/content/docs")

        reference_source = (
            "docs/next/website/src/data/config-reference.json"
            if "docs/next/" in source_root
            else "website/src/data/config-reference.json"
        )
        if snapshot.git_path_exists(self.git, tag, reference_source):
            reference_destination = destination / "website/src/data/config-reference.json"
            reference_destination.parent.mkdir(parents=True, exist_ok=True)
            reference_destination.write_bytes(self.git(["show", f"{tag}:{reference_source}"], binary=True))
        return metadata

    def backfill(self) -> None:
        tags = [tag for tag in self.git(["tag", "--list", "v*", "--sort=v:refname"]).split("\n") if tag]
        manifest = self.read_manifest()
        entries = {entry["version"]: entry for entry in manifest["versions"]}

        for tag in tags:
            version = normalize_version(tag)
            if version in entries:
                continue
            has_next = snapshot.git_path_exists(self.git, tag, NEXT_ROOT)
            has_legacy = snapshot.git_path_exists(self.git, tag, LEGACY_ROOT)
            if not has_next and not has_legacy:
                continue
            source_root = (
                NEXT_ROOT
                if has_next and (not has_legacy or not snapshot.git_trees_equal(self.git, tag, LEGACY_ROOT, NEXT_ROOT))
                else LEGACY_ROOT
            )
            metadata = self.snapshot_tag(tag, source_root)
            entries[metadata["version"]] = metadata
            print(f"snapshotted {tag}")

        current = self.latest_version()
        self.write_manifest({
            "schema_version": 1,
            "stable_source": _stable_source(manifest),
            "current": normalize_version(current),
            "versions": list(entries.values()),
        })

    def check(self) -> None:
        manifest = self.read_manifest()
        stable_source = _stable_source(manifest)
        if (
            not snapshot.is_schema_version_one(manifest.get("schema_version"))
            or not isinstance(manifest.get("current"), str)
            or stable_source not in ("legacy", "snapshot")
        ):
            raise DocsError(f"{self.manifest_path} has an unsupported schema")
        current = manifest["current"]
        versions = manifest["versions"]

        latest = self.latest_version()
        if normalize_version(latest) != NO_STABLE_RELEASE and current != normalize_version(latest):
            raise DocsError(f"docs current version {current} does not match distribution latest {latest}")

        expected_order = [entry["version"] for entry in sort_versions_newest_first(versions)]
        if [entry["version"] for entry in versions] != expected_order:
            raise DocsError("documentation versions are not sorted newest first")

        seen: set[str] = set()
        for entry in versions:
            version = entry["version"]
            if version in seen:
                raise DocsError(f"duplicate docs version {version}")
            seen.add(version)
            if normalize_version(entry.get("tag")) != version:
                raise DocsError(f"docs version {version} has mismatched tag {entry.get('tag')}")
            commit = entry.get("commit")
            requires_commit = entry.get("source") == NEXT_ROOT or (stable_source == "snapshot" and version == current)
            if requires_commit and not commit:
                raise DocsError(f"docs version {version} is missing commit provenance")
            if commit:
                if not isinstance(commit, str) or not FULL_SHA.fullmatch(commit):
                    raise DocsError(f"docs version {version} has invalid commit {commit}")
                tagged_commit = snapshot.resolve_commit(self.git, entry["tag"])
                if tagged_commit != commit:
                    raise DocsError(f"docs version {version} tag {entry['tag']} moved from {commit} to {tagged_commit}")
            if entry.get("source") not in SOURCES:
                raise DocsError(f"docs version {version} has unsupported source {entry.get('source')}")

            version_root = self.versions_dir / version / "website"
            documentation_paths = snapshot.list_documentation_paths(version_root / "src/content/docs")
            if "index.md" not in documentation_paths and "index.mdx" not in documentation_paths:
                raise DocsError(f"docs version {version} has no root index")

            # A version may predate the config reference; one it has must parse.
            try:
                json.loads((version_root / "src/data/config-reference.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                pass

        if current not in seen:
            raise DocsError(f"current docs version {current} has no snapshot")
        print(f"validated {len(versions)} documentation versions")

    def publish(self, tag: str) -> None:
        release = self.release_metadata(tag)
        if not snapshot.git_path_exists(self.git, tag, NEXT_ROOT):
            raise DocsError(f"{tag} does not contain staged website documentation")

        manifest = self.read_manifest()
        existing = next((entry for entry in manifest["versions"] if entry["version"] == release["version"]), None)
        current = manifest.get("current")
        if current == release["version"]:
            if _stable_source(manifest) == "legacy":
                print(f"documentation {release['tag']} is already published with the legacy stable source")
                return
            if not existing or not existing.get("commit") or existing["commit"] != release["commit"]:
                raise DocsError(f"published documentation {release['version']} has mismatched commit provenance")
            print(f"documentation {release['tag']} is already published")
            return
        if current and _version_key(release["version"]) < _version_key(current):
            if existing:
                if existing.get("tag") != release["tag"]:
                    raise DocsError(f"version {release['version']} is already associated with {existing.get('tag')}")
                if existing.get("commit") and existing["commit"] != release["commit"]:
                    raise DocsError(f"version {release['version']} has mismatched commit provenance")
                print(f"documentation {release['tag']} is already archived")
                return
            archived = self.snapshot_tag(tag, NEXT_ROOT)
            archived_entries = {entry["version"]: entry for entry in manifest["versions"]}
            archived_entries[archived["version"]] = archived
            self.write_manifest({**manifest, "versions": list(archived_entries.values())})
            print(f"archived documentation snapshot {release['tag']} without changing current {current}")
            return
        if existing:
            raise DocsError(f"version {release['version']} already has published documentation")

        metadata = self.snapshot_tag(tag, NEXT_ROOT)

        for readme in ("README.md", "README.zh-CN.md"):
            next_readme = f"docs/next/{readme}"
            if snapshot.git_path_exists(self.git, tag, next_readme):
                (self.repo_root / readme).write_bytes(self.git(["show", f"{tag}:{next_readme}"], binary=True))

        entries = {entry["version"]: entry for entry in manifest["versions"]}
        entries[metadata["version"]] = metadata
        self.write_manifest({
            "schema_version": 1,
            "stable_source": "snapshot",
            "current": metadata["version"],
            "versions": list(entries.values()),
        })
        print(f"published documentation snapshot {metadata['tag']}")

    def current(self) -> None:
        current = self.read_manifest().get("current")
        print("" if current is None else current)


def _manifest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    # The .mjs rebuilt each entry as {version, tag, commit if set, source},
    # which dropped every other field and any field that was absent.
    kept: dict[str, Any] = {}
    for field in ("version", "tag"):
        if field in entry:
            kept[field] = entry[field]
    if entry.get("commit"):
        kept["commit"] = entry["commit"]
    if "source" in entry:
        kept["source"] = entry["source"]
    return kept


def main(argv: list[str]) -> None:
    command = argv[0] if argv else None
    value = argv[1] if len(argv) > 1 else None
    versions = Versions(snapshot.repo_root_from_environment(Path(__file__)))
    if command == "backfill" and not value:
        versions.backfill()
    elif command == "publish" and value:
        versions.publish(value)
    elif command == "check" and not value:
        versions.check()
    elif command == "current" and not value:
        versions.current()
    else:
        raise DocsError(USAGE)


if __name__ == "__main__":
    sys.exit(snapshot.run(main, sys.argv[1:]))
