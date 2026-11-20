"""Build, semantic comparison and non-destructive three-way patch preparation."""

from copy import deepcopy
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher, unified_diff
import json
from pathlib import Path

from bs4 import BeautifulSoup

from .markup import canonical, blocks, code_blocks
from .material import Material
from .project import Course, contained, read


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(course: Course, output: str | Path, scope: str | None = None) -> dict:
    steps = course.compile(scope)  # Validate all sources before producing files.
    output = Path(output)
    planned = {f"{i:03d}-{step['position']:02d}.step" for i, step in enumerate(steps, 1)}
    if any(p.name not in planned for p in output.glob("*.step")):
        raise ValueError("Output contains stale .step files; choose an empty output directory")
    exports = []
    for i, step in enumerate(steps, 1):
        # IDs are metadata, never filesystem paths.
        name = f"{i:03d}-{step['position']:02d}.step"
        write_json(output / name, dict(block=step["block"], has_review=False))
        exports.append(dict(file=name, id=step["id"], topic=step["topic"], position=step["position"]))
    snapshot = dict(version=1, steps=steps)
    write_json(output / "local-snapshot.json", snapshot)
    write_json(output / "index.json", exports)
    return snapshot


def semantic(step: dict) -> dict:
    block = step["block"]
    kind = block["name"]
    source = block.get("source") or {}
    if kind not in {"text", "choice", "matching"}:
        raise ValueError(f"Unsupported Stepik block: {kind}")
    result = dict(kind=kind, body=canonical(block["text"]), options=[], answers=[], pairs=[],
                  settings={k: v for k, v in source.items() if k not in {"options", "pairs"}},
                  feedback=[block.get("feedback_correct", ""), block.get("feedback_wrong", "")])
    if kind == "choice":
        if not isinstance(source.get("options"), list) or not source["options"]:
            raise ValueError("Choice source is incomplete; author step-sources access is required")
        if any(type(o.get("is_correct")) is not bool for o in source["options"]):
            raise ValueError("Choice source does not expose correct answers")
        result["options"] = [canonical(o["text"]) for o in source["options"]]
        result["answers"] = [i for i, o in enumerate(source["options"], 1) if o["is_correct"]]
        result["feedback"] += [o.get("feedback", "") for o in source["options"]]
    if kind == "matching":
        if not isinstance(source.get("pairs"), list) or not source["pairs"]:
            raise ValueError("Matching source does not expose pairs")
        result["pairs"] = [[canonical(p["first"]), canonical(p["second"])] for p in source["pairs"]]
    return result


def align(local: list[dict], snapshot: dict) -> tuple[dict, list[dict]]:
    if any(not s.get("stepik_id") for s in local):
        raise ValueError("Stable stepik_id mapping required; never infer identity from position. Use course.json.")
    lessons = {s["lesson"] for s in local}
    topics = {s["topic"] for s in local}
    remote, extras = {}, []
    local_ids = {s["stepik_id"] for s in local}
    seen, positions = set(), set()
    for s in snapshot["steps"]:
        rid = s.get("stepik_id")
        if not isinstance(rid, int) or rid <= 0 or rid in seen:
            raise ValueError("Remote snapshot has missing/duplicate/invalid Stepik IDs")
        seen.add(rid)
        if s.get("lesson") not in lessons and s.get("topic") not in topics and rid not in local_ids:
            continue
        if type(s.get("position")) is not int or s["position"] < 1:
            raise ValueError("Remote positions must be positive integers")
        position_key = (s.get("lesson"), s["position"])
        if position_key in positions:
            raise ValueError("Duplicate position in remote lesson")
        positions.add(position_key)
        semantic(s)
        if rid in local_ids:
            remote[rid] = s
        else:
            extras.append(s)
    return remote, extras


@dataclass
class Change:
    step_id: str
    position: int
    field: str
    before: object
    after: object
    message: str
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def compare(course: Course, remote: dict, scope: str | None = None) -> list[Change]:
    local = course.compile(scope)
    aligned, extras = align(local, remote)
    changes = []
    labels = dict(kind="step type changed", body="student text or markup changed", options="answer options/order changed",
                  answers="correct answer changed", pairs="matching pairs changed", settings="exercise settings changed", feedback="feedback changed")
    for step in local:
        other = aligned.get(step["stepik_id"])
        if other is None:
            changes.append(Change(step["id"], step["position"], "missing", step["stepik_id"], None, "step missing remotely"))
            continue
        for field in ("position", "lesson"):
            if step[field] != other.get(field):
                changes.append(Change(step["id"], step["position"], field, step[field], other.get(field),
                                      f"step moved: {field} {step[field]} -> {other.get(field)}"))
        a, b = semantic(step), semantic(other)
        for field in a:
            if a[field] != b[field]:
                label = labels[field]
                detail = ""
                if field == "body":
                    old_code, new_code = code_blocks(a[field]), code_blocks(b[field])
                    if old_code != new_code:
                        label = "code changed (including literal whitespace)"
                        detail = "\n".join(unified_diff("\n".join(old_code).splitlines(), "\n".join(new_code).splitlines(), "local code", "Stepik code", lineterm=""))
                    else:
                        detail = "\n".join(unified_diff(blocks(a[field]), blocks(b[field]), "local HTML", "Stepik HTML", lineterm=""))
                else:
                    detail = f"{json.dumps(a[field], ensure_ascii=False)} -> {json.dumps(b[field], ensure_ascii=False)}"
                changes.append(Change(step["id"], step["position"], field, a[field], b[field], label, detail))
    for other in extras:
        changes.append(Change(str(other["stepik_id"]), other["position"], "added", None, other["stepik_id"], "unmapped step added remotely"))
    return changes


def save_baseline(course: Course, remote: dict, path: str | Path, scope: str | None = None) -> dict:
    if compare(course, remote, scope):
        raise ValueError("Cannot establish baseline: local and remote differ")
    baseline = dict(version=1, kind="verified-baseline", steps=course.compile(scope))
    write_json(Path(path), baseline)
    return baseline


def merge_value(base, local, remote):
    if local == remote or remote == base:
        return local, False
    if local == base:
        return remote, False
    return local, True


def merge_body(base: str, local: str, remote: str) -> tuple[str, bool]:
    value, conflict = merge_value(base, local, remote)
    if not conflict:
        return value, False
    original = blocks(base)
    edits = []
    for changed in (blocks(local), blocks(remote)):
        edits.append([(a, b, changed[c:d]) for op, a, b, c, d in SequenceMatcher(None, original, changed, autojunk=False).get_opcodes() if op != "equal"])
    combined = list(edits[0])
    for edit in edits[1]:
        if edit in combined:
            continue
        a, b, _ = edit
        for x, y, _ in combined:
            # Insertions at an edited boundary are conservative conflicts.
            if max(a, x) < min(b, y) or (a == b and x <= a <= y) or (x == y and a <= x <= b):
                return local, True
        combined.append(edit)
    for a, b, replacement in sorted(combined, key=lambda e: (e[0], e[1]), reverse=True):
        original[a:b] = replacement
    return "".join(original), False


@dataclass
class PullResult:
    patch: str
    conflicts: list[dict]
    changed_files: list[str]


def prepare_pull(course: Course, remote: dict, baseline: dict, scope: str | None = None) -> PullResult:
    if baseline.get("kind") != "verified-baseline":
        raise ValueError("pull requires a baseline saved by diff --save-baseline after a zero diff")
    local = course.compile(scope)
    aligned, extras = align(local, remote)
    base = {s["id"]: s for s in baseline["steps"]}
    conflicts, proposed = [], {}

    def conflict(step, field, b=None, l=None, r=None):
        conflicts.append(dict(step_id=step["id"], field=field, base=b, local=l, remote=r))

    for step in local:
        before = base.get(step["id"])
        other = aligned.get(step["stepik_id"])
        if before is None or before.get("stepik_id") != step["stepik_id"]:
            conflict(step, "missing baseline or changed identity")
            continue
        if other is None:
            conflict(step, "remote deletion; review manually")
            continue
        if other.get("lesson") != step["lesson"]:
            conflict(step, "cross-topic move; review manually", before.get("lesson"), step["lesson"], other.get("lesson"))
            continue
        b, l, r = semantic(before), semantic(step), semantic(other)
        if l["kind"] != r["kind"] or b["kind"] != l["kind"]:
            conflict(step, "step type change", b["kind"], l["kind"], r["kind"])
            continue
        merged = deepcopy(l)
        conflicts_before = len(conflicts)
        for field in l:
            value, clash = (merge_body if field == "body" else merge_value)(b[field], l[field], r[field])
            if clash:
                conflict(step, field, b[field], l[field], r[field])
            elif field in {"settings", "feedback"} and value != l[field]:
                conflict(step, field + " has no editable Markdown representation", b[field], l[field], r[field])
            else:
                merged[field] = value
        if len(conflicts) != conflicts_before:
            # Do not combine a disputed condition with an undisputed new key.
            # The whole step remains local; other steps can still be proposed.
            continue
        if merged == l:
            continue
        if len(step["paths"]) != 1:
            conflict(step, "combined source files require manual boundary review")
            continue
        path = contained(course.root, step["paths"][0])
        material = Material(read(path))
        try:
            if merged["body"] != l["body"]:
                body = merged["body"]
                if material.task:
                    soup = BeautifulSoup(body, "html.parser")
                    old = BeautifulSoup(l["body"], "html.parser")
                    if not soup.contents or canonical(str(soup.contents[0])) != canonical(str(old.contents[0])):
                        raise ValueError("Exercise title change requires manual review")
                    soup.contents[0].extract()
                    body = str(soup)
                # A pre block must start on its own line: CommonMark's ordinary
                # HTML blocks terminate at blank lines, even inside a later pre.
                material.replace_body("\n\n".join(blocks(body)))
            if merged["options"] != l["options"]:
                material.replace("options", "\n".join(f"{i}. {v}" for i, v in enumerate(merged["options"], 1)))
            if merged["answers"] != l["answers"]:
                material.replace("answer", ", ".join(map(str, merged["answers"])))
            if merged["pairs"] != l["pairs"]:
                pairs = merged["pairs"]
                if len(pairs) > 26:
                    raise ValueError("More than 26 matching pairs require manual review")
                material.replace("left", "\n".join(f"{i}. {p[0]}" for i, p in enumerate(pairs, 1)))
                material.replace("right", "\n".join(f"- **{chr(65+i)}** — {p[1]}" for i, p in enumerate(pairs)))
                material.replace("answer", ", ".join(f"{i+1} — {chr(65+i)}" for i in range(len(pairs))))
            if semantic(dict(block=material.compile())) != merged:
                raise ValueError("Round-trip check failed; source needs manual review")
            proposed[path] = material.text
        except ValueError as error:
            conflict(step, str(error))
    for extra in extras:
        conflict(dict(id=str(extra["stepik_id"])), "unmapped remote addition; review manually")

    # Merge topic ordering by stable IDs, never by the old position of each file.
    manifest = deepcopy(course.manifest)
    order_changed = False
    for topic in course.topics(scope):
        current = [s for s in local if s["topic"] == topic["id"]]
        old = sorted([s for s in baseline["steps"] if s.get("topic") == topic["id"]], key=lambda s: s["position"])
        remote_order = sorted([aligned[s["stepik_id"]] for s in current if s["stepik_id"] in aligned], key=lambda s: s["position"])
        b = [s["stepik_id"] for s in old]
        l = [s["stepik_id"] for s in current]
        r = [s["stepik_id"] for s in remote_order]
        if set(b) != set(l) or set(l) != set(r) or any(s.get("lesson") != topic.get("lesson_id") for s in remote_order):
            continue
        order, clash = merge_value(b, l, r)
        if clash:
            conflict(dict(id=topic["id"]), "order", b, l, r)
        elif order != l:
            if course.manifest_path is None:
                conflict(dict(id=topic["id"]), "order requires an explicit course.json", b, l, r)
            else:
                target = next(t for t in manifest["topics"] if t["id"] == topic["id"])
                by_id = {s["stepik_id"]: s for s in target["steps"]}
                target["steps"] = [by_id[rid] for rid in order]
                order_changed = True
    if order_changed:
        proposed[course.manifest_path] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    patches, names = [], []
    for path, after in proposed.items():
        before = read(path)
        if before == after:
            continue
        name = path.relative_to(course.root).as_posix()
        # Git accepts quoted UTF-8 filenames, including spaces and tabs.
        a, b = json.dumps("a/" + name, ensure_ascii=False), json.dumps("b/" + name, ensure_ascii=False)
        diff = list(unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=a, tofile=b))
        for line in diff:
            patches.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        names.append(name)
    return PullResult("".join(patches), conflicts, names)
