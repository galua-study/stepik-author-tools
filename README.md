# stepik-author-tools

Build `.step` files from Markdown, inspect semantic differences against Stepik,
and prepare a three-way Git patch without overwriting local author notes.
Python 3.11+, tested on Windows with PowerShell. Version 0.1 is read-only on Stepik.

## Quick start (no account)

```powershell
git clone https://github.com/galua-study/stepik-author-tools.git
cd stepik-author-tools
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\stepik-author.exe build examples/demo --out out/import
.\.venv\Scripts\stepik-author.exe diff examples/demo --remote examples/demo/remote-edited.json
.\.venv\Scripts\stepik-author.exe pull examples/demo --remote examples/demo/remote-edited.json --base examples/demo/baseline.json --out out/stepik.patch
git apply --check --directory=examples/demo out/stepik.patch
git apply --directory=examples/demo out/stepik.patch
```

`diff` exits **1** when differences exist (expected in this demo), **0** for equality.
`pull` exits **1** for conflicts, **0** for a conflict-free proposal. All commands
exit **2** on invalid input/access errors. `pull` never applies a patch: inspect it
and its `.patch.json` report first. Patch paths are relative to the project root
(the directory containing `course.json`). Omit `--directory` when that is your Git root.

The synthetic course covers text, single/multiple choice, matching and local
self-check exercises. Its numeric platform IDs are **fictional**, for offline use
only. The edited snapshot changes a question and its correct answer, changes a
Python line and moves steps 5 and 6. The author explanation stays intact.

## Source format and identity

See [`examples/demo/course.json`](examples/demo/course.json). A manifest contains
`version: 1`, topics (`id`, `module`, `lesson_id`) and ordered `steps`. Each step
has a stable local `id`, a relative `path` (or `paths` for combined introductions),
and its real `stepik_id` after import. Paths must stay inside the project root;
one source file cannot belong to several steps. Topic/step IDs must be unique.

`--scope values` selects one topic; `--scope module-1` selects a module. Without
it all topics are used. Array order is authoritative. A Stepik lesson URL ending
in `/step/4` gives a **position**, not a stable step ID. Obtain IDs from
`GET /api/lessons/{id}` and inspect the corresponding `step-sources`; record the
mapping deliberately. The tool never matches questions by position or fuzzy text.
Update `path` when renaming files, keeping the same `id` and `stepik_id`.

`build` also accepts existing Russian topic/module directories containing ordered
README tables (`[title](<relative.md>)`), including a map row that combines two
introductions. This adapter reads the course without modifying it. Use an explicit
manifest for synchronization; auto-generated path IDs are intended for building.
For courses without maps, write a manifest rather than guessing lesson order.

Task Markdown uses `### Condition`, `Options`, `Correct answer(s)`, `Explanation`,
or their Russian equivalents `Условие`, `Варианты ответа`, `Правильный ответ`,
`Правильные ответы`, `Объяснение`. Matching uses numbered `Left column` /
`Левая колонка`, lettered `Right column` / `Правая колонка` and `1 — B, 2 — A` keys.
Use consecutive option numbers starting at 1; correct-answer lists start with
numbers, for example `2. explanation` or `1, 3`. Explicit `multiple` / `несколько`
in task metadata supports a multiple-choice question with only one correct option.

Student content ends before answer/option/author sections. Self-check instructions
between Condition and Correct answer remain visible in a text step. Author notes
and reference solutions stay in Markdown; choice keys go only into `block.source`;
feedback stays empty. Options retain order. Markdown tables, HTML, lists and fenced
code are supported. Local images/relative links are retained, **not uploaded**;
use accessible absolute asset URLs for imported lessons.

Unsupported exercise types/layouts (including sorting and custom matching layouts)
fail explicitly. This release does not infer custom grading scripts.

## Live comparison and the merge baseline

Set `STEPIK_TOKEN` in your local process to an OAuth bearer token with author access.
Do not put credentials in the manifest or command arguments. The client only calls
GET endpoints at `https://stepik.org`; it refuses redirects and uses timeouts.

```powershell
stepik-author diff path/to/course.json --scope module-1 --live
# Once the imported source and remote source are equal:
stepik-author diff path/to/course.json --live --save-baseline .stepik/base.json
# Later, after edits on either side:
stepik-author pull path/to/course.json --live --base .stepik/base.json --out out/review.patch
```

A baseline is saved only after a zero semantic diff. Keep it until the next agreed
synchronization point; `build` writes a local snapshot but never advances the merge
baseline. After applying a patch, resolving conflicts and reconciling any remaining
local changes on Stepik, run `diff --save-baseline` again. Never replace the baseline
with a snapshot of only one edited side. Keep baseline scope sufficient for the
next pull. Scope-limited saves contain only that scope.

Offline `--remote` accepts a version-1 snapshot (see demo) or a complete
`{"step-sources": [...]}` API export. It must contain the entire selected lesson(s),
including stable IDs, positions, lesson IDs and author `block.source` data. Missing
steps are reported as missing/deleted, not silently ignored. A student-visible
`steps` response is insufficient for checking answer keys.

HTML comparison ignores editor IDs/classes, data attributes and harmless wrappers,
but retains links, images, structure, styling and literal whitespace in code.
Reports distinguish content/code, options/order, keys, pairs, feedback, settings
and moves. `--json` produces structured differences for callers.

Pull merges body blocks and exercise fields against the saved base. Separate
paragraph edits can merge; two edits to the same paragraph/code block conflict.
An edited student paragraph and a new local Explanation merge independently.
Changed text is written as **raw HTML inside Markdown** to preserve platform
formatting; it is not prettified or lossily converted back to Markdown. Unchanged
author sections are kept. Every proposed material is rebuilt and checked against
the intended merged semantic result before entering the patch.

Conflicts are explicit records with base/local/remote values. Independent changes
to other steps may still appear in the patch; a conflicting step retains its
entire local content, so a disputed question cannot acquire a different answer key.
Settings without a Markdown representation, type changes, added/deleted steps,
cross-topic moves, edited titles and combined-source edits require manual review.
Within-topic moves update the manifest; concurrent incompatible order changes
conflict. Options/keys/pairs are atomic fields; conflicting edits within one such
field are deliberately not guessed. No baseline means no three-way pull.

## Library and future MCP

```python
from stepik_author_tools import (
    load_course,
    build,
    read_snapshot,
    compare,
    prepare_pull,
    StepikClient,
)

course = load_course("examples/demo")
build(course, "out/import")
remote = read_snapshot("examples/demo/remote-edited.json")
changes = compare(course, remote, scope="module-1")
proposal = prepare_pull(course, remote, read_snapshot("examples/demo/baseline.json"))
print(proposal.patch, proposal.conflicts)
# For live reads: remote = StepikClient().snapshot(course, scope="module-1")
```

These operations do not depend on argparse, subprocesses or a running CLI. A future
MCP server can expose them for: **“Compare the first module with the draft on Stepik
and prepare a patch.”** (“Сравни первый модуль с черновиком на Stepik и подготовь
патч”.) The intended sequence is resolve scope → read author sources → compare →
prepare reviewable patch. MCP transport and direct REST writes are outside v0.1.

## API evidence and verification

The [official API repository](https://github.com/StepicOrg/Stepik-API) documents
OAuth, flat resource lists and pagination. Its
[export example](https://github.com/StepicOrg/Stepik-API/blob/master/examples/export_course.py)
reads course → sections → units → lessons → steps → author step-sources and writes
`.step` objects containing `block`. Its
[creation example](https://github.com/StepicOrg/Stepik-API/blob/master/examples/create_content.py)
documents choice fields and POST/PUT author operations. Those writes are deliberately
absent here. Refer also to [Stepik API docs](https://stepik.org/api/docs/).

See [VALIDATION.md](VALIDATION.md) for the actual verification boundary. Synthetic
tests are not evidence of live editor acceptance or live author authorization.

## Development

Implementation is separated into packages under `src/stepik_author_tools`:
`domain`, `serialization`, `markdown`, `course`, `sync`, `api` and `cli`.
See [the architecture guide](docs/architecture.md) for responsibilities, dependencies
and the merge invariants. Public library calls and CLI arguments remain compatible.

```powershell
.\.venv\Scripts\python.exe -m pip install '.[dev]'
.\scripts\check.ps1
```

The check script runs `ruff check .`, `ruff format --check .`, strict `mypy` and
`pytest`. All four checks are required in CI. Ruff also enforces documented public
functions, annotations and limits on function complexity. Type checking includes
the source packages, demo script and tests; downstream users receive `py.typed`.

Keep real course manifests, `.step` files, snapshots, patches and tokens outside
public repositories. They may contain unpublished lessons and answer keys.
Ignored `out/`, `private/` and `.stepik/` are suitable local working directories.
Only the original synthetic example is checked into this repository.
