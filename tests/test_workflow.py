from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from stepik_author_tools import load_course, build, compare, prepare_pull, read_snapshot, save_baseline
from stepik_author_tools.cli import main
from stepik_author_tools.markup import canonical
from stepik_author_tools.material import Material
from stepik_author_tools.operations import merge_body

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


@pytest.fixture
def project(tmp_path):
    target = tmp_path / "demo"
    shutil.copytree(DEMO, target)
    return load_course(target)


def snapshot(course):
    return dict(version=1, steps=course.compile())


def baseline(course):
    return dict(snapshot(course), kind="verified-baseline")


def apply(course, result):
    patch = course.root / "proposal.patch"
    patch.write_text(result.patch, encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q", str(course.root)], check=True)
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=course.root, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=course.root, check=True)


def test_build_keys_order_code_and_privacy(project, tmp_path):
    built = build(project, tmp_path / "out")
    assert len(list((tmp_path / "out").glob("*.step"))) == 7
    blocks = [s["block"] for s in built["steps"]]
    assert [b["name"] for b in blocks] == ["text", "choice", "choice", "matching", "text", "text", "text"]
    assert [o["is_correct"] for o in blocks[2]["source"]["options"]] == [True, False, True, False]
    assert blocks[1]["source"]["preserve_order"] is True
    assert "language-python" in blocks[4]["text"]
    assert "return value * 2" in blocks[4]["text"]
    assert "assert increment(-1)" in blocks[5]["text"]
    assert all("LOCAL AUTHOR NOTE" not in b["text"] and "PRIVATE DEMO KEY" not in b["text"] for b in blocks)
    assert "return value + 1" not in blocks[5]["text"]
    assert all(b["feedback_correct"] == b["feedback_wrong"] == "" for b in blocks)


def test_diff_names_real_changes_and_ignores_editor_noise(project):
    changes = compare(project, read_snapshot(DEMO / "remote-edited.json"))
    assert {(c.step_id, c.field) for c in changes} == {("single", "body"), ("single", "answers"), ("code", "body"), ("code", "position"), ("practice", "position")}
    assert any("print(twice(4))" in c.detail for c in changes)


def test_remote_paragraph_local_explanation_and_reorder_merge(project):
    base = baseline(project)
    path = project.root / "single.md"
    path.write_text(path.read_text() + "\nNew local author explanation.\n", encoding="utf-8")
    remote = read_snapshot(DEMO / "remote-edited.json")
    proposal = prepare_pull(project, remote, base)
    assert not proposal.conflicts
    assert "a string?" not in path.read_text()  # Proposal only.
    apply(project, proposal)
    assert "New local author explanation." in path.read_text()
    assert "LOCAL AUTHOR NOTE" in path.read_text()
    assert "a string?" in path.read_text()
    assert not compare(load_course(project.root), remote)


def test_same_paragraph_conflict_preserves_local_and_author_notes(project):
    base = baseline(project)
    path = project.root / "single.md"
    path.write_text(path.read_text().replace("an integer?", "a list?") + "\nLocal note.\n", encoding="utf-8")
    proposal = prepare_pull(project, read_snapshot(DEMO / "remote-edited.json"), base)
    assert any(c["step_id"] == "single" and c["field"] == "body" for c in proposal.conflicts)
    apply(project, proposal)
    assert "a list?" in path.read_text() and "Local note." in path.read_text()
    assert Material(path.read_text()).compile()["source"]["options"][0]["is_correct"]


def test_disjoint_paragraphs_and_overlapping_code():
    b = "<p>One</p><p>Two</p>"
    assert merge_body(b, "<p>Local</p><p>Two</p>", "<p>One</p><p>Remote</p>") == ("<p>Local</p><p>Remote</p>", False)
    assert merge_body("<pre>a\nb</pre>", "<pre>A\nb</pre>", "<pre>a\nB</pre>")[1]


def test_html_semantics():
    assert canonical('<div class="editor"><p id="x">A <span>B</span></p>\n<p>C</p></div>') == canonical("<p>A B</p><p>C</p>")
    assert canonical("<p><b>Bold</b>&nbsp;text</p>") == canonical("<p><strong>Bold</strong> text</p>")
    for a, b in [("x = 'a b'", "x = 'ab'"), ("    x", "  x")]:
        assert canonical(f"<pre><code>{a}</code></pre>") != canonical(f"<pre><code>{b}</code></pre>")
    assert canonical('<a href="/one">link</a>') != canonical('<a href="/two">link</a>')
    assert canonical('<img src="a" alt="one"/>') != canonical('<img src="a" alt="two"/>')
    assert canonical('<p style="color:red">x</p>') != canonical('<p style="color:blue">x</p>')


def test_baseline_refuses_edited_remote(project, tmp_path):
    with pytest.raises(ValueError, match="differ"):
        save_baseline(project, read_snapshot(DEMO / "remote-edited.json"), tmp_path / "base.json")
    assert not (tmp_path / "base.json").exists()
    assert save_baseline(project, snapshot(project), tmp_path / "base.json")["kind"] == "verified-baseline"
    with pytest.raises(ValueError, match="baseline"):
        prepare_pull(project, snapshot(project), snapshot(project))


def test_id_not_position_and_missing_answers(project):
    remote = snapshot(project)
    remote["steps"][0]["stepik_id"] = 999999
    changes = compare(project, remote)
    assert {c.field for c in changes} == {"added", "missing"}
    remote = snapshot(project)
    del remote["steps"][1]["block"]["source"]["options"][0]["is_correct"]
    with pytest.raises(ValueError, match="correct answers"):
        compare(project, remote)


def test_scope_and_cli_exit_codes(project, tmp_path):
    assert len(build(project, tmp_path / "out", "recap")["steps"]) == 1
    assert not compare(project, read_snapshot(DEMO / "remote-edited.json"), "recap")
    assert main(["diff", str(project.root), "--remote", str(DEMO / "remote-edited.json")]) == 1
    assert main(["diff", str(project.root), "--remote", str(DEMO / "remote-base.json")]) == 0
    assert main(["build", str(project.root), "--scope", "missing", "--out", str(tmp_path / "none")]) == 2


def test_matching_options_and_settings_changes(project):
    remote = snapshot(project)
    pairs = remote["steps"][3]["block"]["source"]["pairs"]
    pairs[0]["second"], pairs[1]["second"] = pairs[1]["second"], pairs[0]["second"]
    remote["steps"][1]["block"]["source"]["options"][2]["text"] = "<code>[4, 5]</code>"
    proposal = prepare_pull(project, remote, baseline(project))
    assert not proposal.conflicts
    apply(project, proposal)
    assert not compare(project, remote)
    remote["steps"][1]["block"]["source"]["preserve_order"] = False
    proposal = prepare_pull(project, remote, baseline(project))
    assert any("settings" in c["field"] for c in proposal.conflicts)


def test_invalid_paths_duplicate_ids(project):
    manifest = project.manifest
    manifest["topics"][0]["steps"][0]["path"] = "../escape.md"
    project.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        load_course(project.root)


def test_russian_map_multifile_and_fenced_headings(tmp_path):
    (tmp_path / "intro.md").write_text("# Welcome\n", encoding="utf-8")
    topic = tmp_path / "Тема 1. Test"
    topic.mkdir()
    (topic / "body.md").write_text("More text.\n", encoding="utf-8")
    (topic / "README.md").write_text("| 1 | [A](<../intro.md>) и [B](<body.md>) | text |", encoding="utf-8")
    assert "More text" in load_course(topic).compile()[0]["block"]["text"]
    task = Material("## Task\n\n### Condition\n\n```python\n### Explanation\nprint(1)\n```\n\n### Correct answer\n\nSECRET\n\n### Explanation\n\nAUTHOR\n")
    block = task.compile()
    assert "print(1)" in block["text"] and "SECRET" not in block["text"] and "AUTHOR" not in block["text"]


def test_concurrent_reorder_conflict(project):
    base = baseline(project)
    steps = project.manifest["topics"][0]["steps"]
    steps[0], steps[1] = steps[1], steps[0]
    proposal = prepare_pull(project, read_snapshot(DEMO / "remote-edited.json"), base)
    assert any(c["field"] == "order" for c in proposal.conflicts)


def test_unsupported_programming_and_text_entry_never_publish_solutions():
    for kind in ("программирование", "ввод текста", "заполнение пропусков"):
        material = Material(f"## Задание\n\n**Тип:** {kind}\n\n### Условие\n\nTask\n\n### Правильное решение\n\nSECRET")
        with pytest.raises(ValueError, match="Unsupported"):
            material.compile()
    with pytest.raises(ValueError, match="Condition"):
        Material("# Task\n\n### Правильный ответ\n\nSECRET").compile()


def test_bold_answer_compatibility():
    material = Material("## Task\n\n### Condition\n\nPick\n\n### Options\n\n1. A\n2. B\n\n### Correct answer\n\n**2.** B")
    assert material.compile()["source"]["options"][1]["is_correct"]


def test_multiline_options_and_bullet_keys():
    material = Material('## Task\n\n### Condition\n\nPick\n\n### Options\n\nOption 1:\n\n```python\nprint(1)\n```\n\nOption 2:\n\n```python\nprint(2)\n```\n\n### Correct answers\n\n- **1.** First\n- **2.** Second\n')
    source = material.compile()["source"]
    assert source["is_multiple_choice"]
    assert all(o["is_correct"] for o in source["options"])
    assert "<pre>" in source["options"][0]["text"]


def test_stale_build_fails_without_leaving_mixed_scope(project, tmp_path):
    build(project, tmp_path / "out")
    with pytest.raises(ValueError, match="stale"):
        build(project, tmp_path / "out", "recap")


def test_deletion_and_cross_topic_moves_are_review_only(project):
    remote = snapshot(project)
    remote["steps"].pop(1)
    remote["steps"][0]["lesson"] = 999999
    proposal = prepare_pull(project, remote, baseline(project))
    assert len(proposal.conflicts) == 2 and not proposal.patch
