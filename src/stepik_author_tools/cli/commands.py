"""CLI handlers that translate typed library results into files and terminal output."""

import json
from pathlib import Path

from ..api.client import StepikClient
from ..config import load_settings
from ..course.project import Course, load_course
from ..domain.models import Change, Snapshot
from ..serialization.files import JSON_SUFFIX, protect_inputs, read_snapshot, write_json
from ..serialization.outputs import staged_outputs
from ..sync.build import build, save_baseline
from ..sync.comparison import compare
from ..sync.pull import prepare_pull
from .arguments import Arguments


def _required_path(value: Path | None, option: str) -> Path:
    if value is None:
        raise ValueError(f"Missing {option}")
    return value


def _print_changes(changes: list[Change], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([change.to_dict() for change in changes], ensure_ascii=False, indent=2))
        return
    for change in changes:
        print(f"Step {change.position} [{change.step_id}]: {change.message}")
        if change.detail:
            print(change.detail)
    if not changes:
        print("No semantic differences.")


def _diff(course: Course, remote: Snapshot, args: Arguments) -> int:
    changes = compare(course, remote, args.scope)
    if args.save_baseline:
        protect_inputs([args.save_baseline], _input_paths(course, args))
        save_baseline(course, remote, args.save_baseline, args.scope)
    _print_changes(changes, as_json=args.json)
    return 1 if changes else 0


def _pull(course: Course, remote: Snapshot, args: Arguments) -> int:
    baseline = read_snapshot(_required_path(args.base, "--base"))
    result = prepare_pull(course, remote, baseline, args.scope)
    output = _required_path(args.out, "--out")
    report = output.with_name(output.name + JSON_SUFFIX)
    protect_inputs([output, report], _input_paths(course, args))
    with staged_outputs(output.parent, [output.name, report.name]) as stage:
        (stage / output.name).write_text(result.patch, encoding="utf-8", newline="\n")
        write_json(
            stage / report.name,
            {
                "conflicts": [c.to_dict() for c in result.conflicts],
                "changed_files": [*result.changed_files],
            },
        )
    print(
        f"Prepared patch: {len(result.changed_files)} files; "
        f"{len(result.conflicts)} conflicts. Sources unchanged."
    )
    for conflict in result.conflicts:
        print(f"CONFLICT [{conflict.step_id}]: {conflict.field} — {conflict.reason}")
    return 1 if result.conflicts else 0


def _input_paths(course: Course, args: Arguments) -> list[Path]:
    return course.input_paths() + [
        path for path in (args.remote, args.base, args.config) if path is not None
    ]


def run(args: Arguments) -> int:
    """Execute one command; all synchronization behavior lives in the library."""
    course = load_course(args.project, settings=load_settings(args.config))
    if args.command == "build":
        output = _required_path(args.out, "--out")
        result = build(
            course, output, args.scope, extra_inputs=[args.config] if args.config else []
        )
        print(f"Built {len(result.steps)} .step files in {output}")
        return 0
    remote = (
        read_snapshot(args.remote)
        if args.remote
        else StepikClient(settings=course.settings.api).snapshot(course, args.scope)
    )
    if args.command == "diff":
        return _diff(course, remote, args)
    return _pull(course, remote, args)
