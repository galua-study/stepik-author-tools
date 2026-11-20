# Verification record

Verified on 2026-11-20, Windows / PowerShell, CPython 3.12.

The package was built as wheel and sdist. The wheel was installed into a second,
fresh virtual environment (not an editable checkout); `pip check` succeeded,
all **22 tests passed**, and build/diff/pull ran using the installed CLI. The demo
pull produced three file changes and zero conflicts; `git apply --check` passed.

## Offline and local checks

- The standalone synthetic course builds seven `.step` files covering text,
  single choice, multiple choice, matching, fenced Python and local self-check.
- All three CLI commands run without credentials. Diff identifies a changed
  question/key, an exact changed Python line and moves between positions 5 and 6.
- Git applies the proposed patch; rebuilding the patched sources yields a zero
  semantic diff against the edited fixture. Local author explanations survive.
- Concurrent edits to the same student paragraph produce a conflict and retain
  the entire local step, including its answer key. Independent paragraph edits
  merge. Conflicting order changes, missing steps and cross-topic moves are reported.
- Tests also cover HTML noise versus real code/link/style changes, matching pairs,
  options, answer privacy, path containment, stable identity, baseline validation,
  unsupported exercise rejection, stale output protection, CLI exit codes and
  mocked paginated/authentication-error API responses.
- Read-only compatibility check of two real Flask topics: 22 steps built outside
  this repository; all 21 steps available in previous local exports match
  semantically, including source settings. The older export lacks the final step
  of one topic, so that step's comparison could not be performed.
- Read-only parsing of 335 real Typed Python exercises: all 42 choice exercises
  compile. 291 programming/text-entry/fill-in exercises and two custom matching
  layouts are explicitly rejected; they are outside the supported v0.1 formats.
  No real source material, answer key or export is included in this repository.

## Live API boundary

Using the implemented client without a token, GET requests successfully traversed
a public course through `courses`, `sections`, `units` and `lessons`; a populated
lesson's `steps` endpoint returned a text step. An author `step-sources` request
returned HTTP 403, which the client surfaced without falling back to student data.

Author-authorized reads of real drafts were **not** tested. HTTP pagination was
tested with synthetic responses, not a multi-page live export. No POST/PUT/DELETE
request was sent to Stepik. `.step` shape/settings were checked against official
examples and previous local successful-import exports; importing this release's
synthetic files through the live editor was **not** performed. No claim is made
that direct REST writes or a new editor import have been verified.

The public API references are linked in the README. The project intentionally
provides read-only network access and reviewable local patches.
