"""Shared source admission rejects revision drift and dirty snapshots before staging."""
from pathlib import Path
import subprocess

import pytest

from scripts.build.source import git, require_commit, require_source, version_at


@pytest.fixture
def admitted_source(tmp_path: Path):
    source = tmp_path / "source with spaces"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "pyproject.toml").write_text('[project]\nversion="1.2.3"\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=source, check=True)
    return source, git(source, "rev-parse", "HEAD")


def test_admitted_revision_is_clean_and_version_is_read_from_that_revision(admitted_source):
    source, revision = admitted_source
    require_source(source, revision)
    (source / "pyproject.toml").write_text('[project]\nversion="9.9.9"\n', encoding="utf-8")
    assert version_at(source, revision) == "1.2.3"


def test_revision_drift_is_rejected(admitted_source):
    source, revision = admitted_source
    other = "a" * 40 if revision != "a" * 40 else "b" * 40
    with pytest.raises(ValueError, match="changed revision"):
        require_source(source, other)


@pytest.mark.parametrize("relative", ["pyproject.toml", "untracked.txt"])
def test_tracked_and_untracked_changes_are_rejected(admitted_source, relative):
    source, revision = admitted_source
    (source / relative).write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean source checkout"):
        require_source(source, revision)


@pytest.mark.parametrize("revision", [None, "abc", "G" * 40, "A" * 40, " " + "a" * 40])
def test_commit_admission_requires_exact_lowercase_sha(revision):
    with pytest.raises(ValueError, match="40-character SHA"):
        require_commit(revision)
    assert require_commit("a" * 40) == "a" * 40
