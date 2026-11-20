import argparse
import json
from pathlib import Path
import sys

from . import load_course, build, compare, prepare_pull, save_baseline, StepikClient, read_snapshot
from .operations import write_json


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build Stepik imports, compare, and prepare safe local patches")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "diff", "pull"):
        p = sub.add_parser(name)
        p.add_argument("project", type=Path, help="course.json, project directory, or topic/module map directory")
        p.add_argument("--scope", help="exact topic or module ID")
        if name == "build":
            p.add_argument("--out", type=Path, required=True)
        else:
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--remote", type=Path, help="offline snapshot or step-sources response")
            group.add_argument("--live", action="store_true", help="read Stepik using optional STEPIK_TOKEN")
            if name == "diff":
                p.add_argument("--json", action="store_true")
                p.add_argument("--save-baseline", type=Path)
            else:
                p.add_argument("--base", type=Path, required=True)
                p.add_argument("--out", type=Path, required=True, help="patch path; conflicts written alongside as .json")
    args = parser.parse_args(argv)
    try:
        course = load_course(args.project)
        if args.command == "build":
            result = build(course, args.out, args.scope)
            print(f"Built {len(result['steps'])} .step files in {args.out}")
            return 0
        remote = read_snapshot(args.remote) if args.remote else StepikClient().snapshot(course, args.scope)
        if args.command == "diff":
            changes = compare(course, remote, args.scope)
            if args.save_baseline:
                save_baseline(course, remote, args.save_baseline, args.scope)
            if args.json:
                print(json.dumps([c.to_dict() for c in changes], ensure_ascii=False, indent=2))
            else:
                for c in changes:
                    print(f"Step {c.position} [{c.step_id}]: {c.message}")
                    if c.detail:
                        print(c.detail)
                if not changes:
                    print("No semantic differences.")
            return 1 if changes else 0
        result = prepare_pull(course, remote, read_snapshot(args.base), args.scope)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result.patch, encoding="utf-8", newline="\n")
        write_json(Path(str(args.out) + ".json"), dict(conflicts=result.conflicts, changed_files=result.changed_files))
        print(f"Prepared patch: {len(result.changed_files)} files; {len(result.conflicts)} conflicts. Sources unchanged.")
        for conflict in result.conflicts:
            print(f"CONFLICT [{conflict['step_id']}]: {conflict['field']}")
        return 1 if result.conflicts else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
