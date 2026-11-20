"""Release gates and artifact handling through the same commands used in CD."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / ".github" / "scripts"


def run_script(
    name: str, directory: Path, *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Exercise command exit codes with assertions disabled, as release gates must still run."""
    return subprocess.run(
        [sys.executable, "-O", str(SCRIPTS / name), *arguments],
        cwd=directory,
        env=os.environ | (environment or {}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize(("tag", "expected"), [("v1.2.3", 0), ("v1.2.4", 1)])
@pytest.mark.parametrize("use_environment", [False, True])
def test_release_tag_gate(tmp_path: Path, tag: str, expected: int, use_environment: bool) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    result = run_script(
        "check_release_tag.py",
        tmp_path,
        *([] if use_environment else [tag]),
        environment={"RELEASE_TAG": tag},
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert "v1.2.3" in result.stdout + result.stderr


def test_checksums_are_correct_repeatable_and_exclude_other_files(tmp_path: Path) -> None:
    (tmp_path / "demo.whl").write_bytes(b"abc")
    (tmp_path / "demo.tar.gz").write_bytes(b"")
    (tmp_path / "build.log").write_text("not a distribution", encoding="utf-8")
    (tmp_path / "nested.whl").mkdir()
    expected = (
        b"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  demo.tar.gz\n"
        b"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  demo.whl\n"
    )
    for _ in range(2):
        result = run_script("write_checksums.py", tmp_path, ".")
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "SHA256SUMS").read_bytes() == expected


def test_empty_checksum_input_does_not_replace_existing_manifest(tmp_path: Path) -> None:
    output = tmp_path / "SHA256SUMS"
    output.write_bytes(b"existing manifest")
    result = run_script("write_checksums.py", tmp_path, ".")
    assert result.returncode == 1 and "No wheel" in result.stderr
    assert output.read_bytes() == b"existing manifest"


@pytest.mark.parametrize("count", [0, 2])
def test_install_refuses_missing_or_ambiguous_artifacts(tmp_path: Path, count: int) -> None:
    for index in range(count):
        (tmp_path / f"demo-{index}.whl").write_bytes(b"not a wheel")
    result = run_script("install_distribution.py", tmp_path, "*.whl", "--directory", ".")
    assert result.returncode == 1 and "Expected exactly one" in result.stderr
    assert "Traceback" not in result.stderr


def test_verify_install_rejects_source_tree_imports(tmp_path: Path) -> None:
    package = tmp_path / "stepik_author_tools"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    result = run_script("verify_install.py", tmp_path, environment={"PYTHONPATH": str(tmp_path)})
    assert result.returncode == 1 and "outside the Python environment" in result.stderr
