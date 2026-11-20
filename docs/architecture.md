# Package boundaries

All implementation packages live under `src/stepik_author_tools`. The public entry
points in `__init__.py` retain their existing names and JSON-compatible return
shapes. The old top-level `material`, `markup`, `project`, `operations` and `remote`
modules are compatibility facades only; they contain no duplicate implementation.

| Package | Responsibility | Dependencies within this project |
| --- | --- | --- |
| `domain` | Typed manifest/snapshot records, semantic values, changes, conflicts | None |
| `serialization` | UTF-8/JSON boundaries, runtime field validation, path containment | `domain` |
| `markdown` | Section spans, exercise keys, Markdown rendering and HTML normalization | `domain` |
| `course` | Source loading, identity checks, legacy topic-map adapter | `domain`, `serialization`, `markdown` |
| `sync` | Build, comparison, three-way merge and patch proposals | `domain`, `serialization`, `markdown`, `course` |
| `api` | Read-only HTTP transport and complete author snapshots | `domain`, `serialization` |
| `cli` | Arguments, terminal output, command dispatch | Public operation packages |

The API and synchronization packages do not import one another. The CLI supplies
either a live or offline snapshot to the same library operations. A future MCP
adapter can do the same without importing argparse or the CLI.

## Data contracts

`TypedDict` records describe JSON-compatible input/output shapes. `SemanticStep`
and `Change` are frozen dataclasses with explicit fields, so merging cannot
accidentally assign an answer list to an HTML body. Generic merge functions retain
the type of the value being merged.

JSON decoding is confined to the serialization and HTTP boundaries. Runtime
validators check declared fields before treating incoming objects as typed records;
the few casts are confined to the schema adapter and follow those checks. Unknown
Stepik source settings are retained and compared, not discarded by a narrow schema.
The package ships `py.typed` for downstream type checkers.

## Synchronization pipeline

`sync/semantic.py` normalizes content and aligns stable platform IDs.
`comparison.py` describes changes and produces human-readable detail.
`build.py` writes imports and only saves a baseline after an equal comparison.

Pull is coordinated by `sync/pull.py`, with each stage kept separate:

1. Validate identity and establish the local/base/remote triple.
2. `merge.py` merges atomic fields and non-overlapping HTML blocks without I/O.
3. `projection.py` changes only the relevant Markdown sections and recompiles the
   result to verify an exact semantic round trip.
4. `ordering.py` merges topic ordering by stable IDs in a copied manifest.
5. `patches.py` formats a Git patch without changing any source file.

Any conflict in a step preserves that entire step, including its answer key.
Code blocks remain atomic and retain literal whitespace. Author explanations stay
outside the student-content span. These rules are documented at their enforcement
points because weakening them can corrupt course content while still producing
syntactically valid Markdown.

## Quality gates

Ruff checks imports, annotations, documentation, common mistakes and complexity.
The configured limits are cyclomatic complexity 10, 12 branches and 50 statements
per function. Formatting is checked separately. mypy runs in strict mode over the
entire library, CLI, demo script and tests; there are no ignored modules or blanket
type suppressions. Tool versions are pinned in the `dev` extra.

Tests cover behavior and public output compatibility, including applying actual
Git patches. HTTP tests inject the `Transport` protocol; an automatic fixture blocks
the default live transport. This makes accidental network access a test failure.
GitHub Actions runs quality gates plus tests on Windows/Ubuntu and Python 3.11–3.13.

Run `scripts/check.ps1` from the repository root after installing `.[dev]`.
