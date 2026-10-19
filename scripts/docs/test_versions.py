import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.docs import snapshot, versions
from scripts.neutral_git_env import isolate_git


class NormalizeVersionTest(unittest.TestCase):
    def test_normalizes_with_and_without_prefix(self):
        for value, expected in (("0.7.5", "0.7.5"), ("v0.7.5", "0.7.5")):
            with self.subTest(value=value):
                self.assertEqual(versions.normalize_version(value), expected)

    def test_rejects_non_release_refs(self):
        # "0.7.5\n": Python's $ would match before a final newline; fullmatch does not.
        for value in ("preview-123", "v0.7", "0.7.5-rc1", "0.7.5\n", "٠.٧.٥", None):
            with self.subTest(value=value), self.assertRaises(snapshot.DocsError):
                versions.normalize_version(value)


class SortVersionsTest(unittest.TestCase):
    def test_sorts_semantic_versions_numerically(self):
        entries = [{"version": v} for v in ("0.6.10", "0.7.2", "0.7.10", "0.5.12")]
        self.assertEqual(
            [entry["version"] for entry in versions.sort_versions_newest_first(entries)],
            ["0.7.10", "0.7.2", "0.6.10", "0.5.12"],
        )


class SchemaVersionTest(unittest.TestCase):
    def test_json_true_is_not_schema_version_one(self):
        self.assertTrue(snapshot.is_schema_version_one(1))
        self.assertTrue(snapshot.is_schema_version_one(1.0))
        self.assertFalse(snapshot.is_schema_version_one(True))
        self.assertFalse(snapshot.is_schema_version_one("1"))


class ManifestWriteTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_writes_two_space_json_newest_first_with_only_known_fields(self):
        repo = versions.Versions(self.root)
        repo.write_manifest({
            "schema_version": 1,
            "stable_source": "snapshot",
            "current": "1.0.0",
            "versions": [
                {"version": "0.9.0", "tag": "v0.9.0", "commit": "", "source": "website/src/content/docs", "extra": 1},
                {"source": "s", "commit": "c" * 40, "tag": "v1.0.0", "version": "1.0.0"},
            ],
        })
        text = repo.manifest_path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "versions": [\n    {\n      "version": "1.0.0",', text)
        self.assertEqual(
            json.loads(text)["versions"],
            [
                {"version": "1.0.0", "tag": "v1.0.0", "commit": "c" * 40, "source": "s"},
                {"version": "0.9.0", "tag": "v0.9.0", "source": "website/src/content/docs"},
            ],
        )

    def test_missing_manifest_reads_as_empty_legacy(self):
        self.assertEqual(
            versions.Versions(self.root).read_manifest(),
            {"schema_version": 1, "stable_source": "legacy", "current": None, "versions": []},
        )


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        isolate_git(self)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git = snapshot.create_git(self.root)

    def commit(self, files, executable=()):
        for path, content in files.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            if path in executable:
                target.chmod(0o755)
        if not (self.root / ".git").exists():
            self.git(["init", "-q"])
        self.git(["add", "."])
        self.git(["commit", "-qm", "fixture"])
        return snapshot.resolve_commit(self.git, "HEAD")

    def test_extract_then_compare_round_trips_and_replaces_stale_files(self):
        commit = self.commit({"docs/a.md": "a\n", "docs/sub/b.md": "b\n"})
        destination = self.root / "out"
        (destination / "stale").mkdir(parents=True)
        snapshot.extract_git_tree(self.git, commit, "docs", destination)
        self.assertEqual(snapshot.list_documentation_paths(destination), ["a.md", "sub/b.md"])
        snapshot.compare_git_tree(self.git, commit, "docs", destination)

        (destination / "sub/b.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(snapshot.DocsError, "sub/b.md differs"):
            snapshot.compare_git_tree(self.git, commit, "docs", destination)

    def test_refuses_an_executable_in_the_tree(self):
        commit = self.commit({"docs/run.sh": "#!/bin/sh\n"}, executable={"docs/run.sh"})
        with self.assertRaisesRegex(snapshot.DocsError, "is not an ordinary documentation file"):
            snapshot.extract_git_tree(self.git, commit, "docs", self.root / "out")

    def test_refuses_an_empty_source(self):
        commit = self.commit({"other/a.md": "a\n"})
        with self.assertRaisesRegex(snapshot.DocsError, "contains no files"):
            snapshot.extract_git_tree(self.git, commit, "docs", self.root / "out")

    def test_listing_refuses_a_symlink_and_a_missing_root(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/index.md").write_text("x\n", encoding="utf-8")
        (self.root / "docs/linked.md").symlink_to("index.md")
        with self.assertRaisesRegex(snapshot.DocsError, "is not an ordinary documentation file"):
            snapshot.list_documentation_paths(self.root / "docs")
        with self.assertRaises(FileNotFoundError):
            snapshot.list_documentation_paths(self.root / "missing")

    def test_a_path_outside_the_source_root_is_unsafe(self):
        for path in ("docs", "other/a.md"):
            with self.subTest(path=path), self.assertRaisesRegex(snapshot.DocsError, "unsafe snapshot path"):
                snapshot.snapshot_relative_path("docs", path)
        self.assertEqual(snapshot.snapshot_relative_path("docs", "docs/a/b.md"), "a/b.md")

    def test_a_joined_path_must_stay_under_its_root(self):
        root = self.root / "out"
        self.assertEqual(snapshot.contained_path(root, "a/b.md", "x"), root / "a/b.md")
        for relative_path in ("../x", "a/../../x", ".", "/etc/passwd"):
            with self.subTest(relative_path=relative_path), self.assertRaisesRegex(snapshot.DocsError, "unsafe snapshot path x"):
                snapshot.contained_path(root, relative_path, "x")

    def test_json_is_read_as_json_parse_read_it(self):
        self.assertEqual(snapshot.load_json('{"a": [1, "b"]}'), {"a": [1, "b"]})
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), self.assertRaisesRegex(snapshot.DocsError, "is not valid JSON"):
                snapshot.load_json(f'{{"a": {constant}}}')

    def test_git_failure_reaches_run_as_exit_one(self):
        def main(argv):
            snapshot.resolve_commit(self.git, "no-such-ref")

        self.git(["init", "-q"])
        with self.assertRaises(subprocess.CalledProcessError):
            main([])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(snapshot.run(main, []), 1)
        self.assertIn("error: Command failed: git rev-parse no-such-ref^{commit}", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
