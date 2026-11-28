"""Exercise the installed console command, including expected nonzero diff status."""

import json
import subprocess
import sys
import sysconfig
from pathlib import Path

from stepik_author_tools.course.project import Course
from tests.helpers import DEMO


def _run_cli(arguments: list[str], cwd: Path, expected: int = 0) -> str:
    name = "stepik-author.exe" if sys.platform == "win32" else "stepik-author"
    executable = Path(sysconfig.get_path("scripts")) / name
    result = subprocess.run(
        [str(executable), *arguments], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result.stdout


def test_module_entry_point_from_tests_directory() -> None:
    # IDE runners can put the test tree ahead of the installed package on sys.path
    subprocess.run(
        [sys.executable, "-m", "stepik_author_tools.cli", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        check=True,
    )


def test_installed_cli_build_diff_pull(project: Course, tmp_path: Path) -> None:
    output = tmp_path / "import"
    _run_cli(["build", str(project.root), "--out", str(output)], tmp_path)
    assert len(list(output.glob("*.step"))) == 7
    differences = _run_cli(
        ["diff", str(project.root), "--remote", str(DEMO / "remote-edited.json"), "--json"],
        tmp_path,
        expected=1,
    )
    assert len(json.loads(differences)) == 5
    patch = tmp_path / "review.patch"
    _run_cli(
        [
            "pull",
            str(project.root),
            "--remote",
            str(DEMO / "remote-edited.json"),
            "--base",
            str(DEMO / "baseline.json"),
            "--out",
            str(patch),
        ],
        tmp_path,
    )
    report = json.loads(patch.with_suffix(".patch.json").read_text(encoding="utf-8"))
    assert report["conflicts"] == [] and len(report["changed_files"]) == 3
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=project.root, check=True)
