"""Use the same author dialect for building, comparison and a real pull round trip."""

import subprocess
from pathlib import Path

import pytest

from stepik_author_tools import load_course, load_settings, read_snapshot
from stepik_author_tools.cli import main
from stepik_author_tools.course.project import Course
from tests.helpers import DEMO, source_of


def test_custom_dialect_survives_cli_pull_and_rebuild(
    project: Course,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "author.toml"
    config.write_text(
        r"""[project]
manifest_name = "syllabus.JSON"
[markdown]
condition = ["Question"]
[markdown.author_sections]
editorial = ["Internal review"]
[markdown.patterns]
numbered_item = '(?m)^(?P<number>\d+)(?:\.|::) +'
[markdown.format]
numbered_item = "{number}:: {text}"
[diff.fields]
answers = "Ключ изменён"
""",
        encoding="utf-8",
    )
    assert project.manifest_path
    project.manifest_path.rename(project.root / "syllabus.JSON")
    path = project.root / "single.md"
    material = path.read_text(encoding="utf-8").replace("### Condition", "### Question")
    material = material.replace(
        "### Options", "### Internal review\n\nLocal reviewer note.\n\n### Options"
    )
    path.write_text(material.replace("2. ", "2:: "), encoding="utf-8")
    args = [str(project.root), "--config", str(config)]
    output = tmp_path / "build"
    assert main(["build", *args, "--out", str(output)]) == 0
    built = read_snapshot(output / "local-snapshot.json")
    assert all("Local reviewer note." not in row.block.text for row in built.steps)
    remote = read_snapshot(DEMO / "remote-edited.json")
    source_of(remote.steps[1].block).options[2].text = "<code>[5]</code>"
    remote_file = tmp_path / "online.json"
    remote_file.write_text(remote.model_dump_json(exclude_unset=True), encoding="utf-8")
    args += ["--remote", str(remote_file)]
    assert main(["diff", *args]) == 1
    assert "Ключ изменён" in capsys.readouterr().out
    patch = tmp_path / "proposal.patch"
    assert main(["pull", *args, "--base", str(DEMO / "baseline.json"), "--out", str(patch)]) == 0
    subprocess.run(["git", "init", "-q"], cwd=project.root, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=project.root, check=True)
    updated = path.read_text(encoding="utf-8")
    assert "Local reviewer note." in updated and "3:: <code>[5]</code>" in updated
    assert (
        main(["--config", str(config), "diff", str(project.root), "--remote", str(remote_file)])
        == 0
    )
    course = load_course(project.root, settings=load_settings(config))
    assert course.manifest_path == project.root / "syllabus.JSON"
