# Agent guide — Nobius

Authoring instructions and repo conventions for AI coding agents (Claude Code, Cursor, Codex, etc.) working in this repository. Human-facing usage docs live in [README.md](README.md) and [docs/](docs/).

## What this repo is

Python package that converts hand-authored JSON (`SheetInfo.json` + `Question*.json` files in a sheet directory) into Mobius-importable course modules, local HTML previews, and PDF/LaTeX output. Sheet sources live outside this repo, typically in a sibling `Questions/` directory.

## Authoring or modifying sheet JSON

Use the `authoring-nobius-sheets` skill at [.claude/skills/authoring-nobius-sheets/SKILL.md](.claude/skills/authoring-nobius-sheets/SKILL.md). It documents the file structure, every supported response mode, the LaTeX rules for statements, and the catalogue of gotchas that cause Mobius "Application Error" or silently mis-grade questions. Do not write JSON without consulting it — the gotchas are non-obvious and have all been observed in production.

Reference exemplars when in doubt: `Questions/Exam2024/`, `Questions/Exam2025/`, `tests/fixtures/RoundTrip/`, `tests/fixtures/mobius_exports/RoundTripDemo.zip`.

## Pre-render lint: `precheck.py`

Before running any export or preview, run `python precheck.py <sheet>`. It enforces structural rules that the per-file JSON schemas can't catch (cross-file consistency, filename-on-disk presence, mode-vs-answer-format validity). The export and preview entry points call it automatically and abort on failure — but agents should run it explicitly when iterating, since the error messages pinpoint the exact JSON path.

When a new failure mode is identified, add an entry to [tests/test_precheck.py](tests/test_precheck.py) and (if structurally enforceable) extend [precheck.py](precheck.py). The test file is the canonical inventory of known-bad patterns.

## Render commands for Mobius-bound output

```bash
python precheck.py "<sheet>"            # always first
python export_mobius.py "<sheet>"       # default mode + profile = correct for Mobius
```

**Defaults are correct.** Do not pass `--profile html_preview` for Mobius-bound output (uses test theme, breaks formatting). Do not use `--render-mode exercise` for exam content (exposes solutions/help to students). Both warnings are explained in detail in the skill.

For HTML previews during authoring, use `preview_html.py`. For PDF/LaTeX output, `export_pdf.py`.

## Validation flow

| Layer | Where | What it catches |
|---|---|---|
| JSON schema | [validation/schemas/](validation/schemas/) | Missing required fields, type errors, value patterns (e.g. `media_folder` no-whitespace) |
| Defaults | [validation/defaults/response_areas.json](validation/defaults/response_areas.json) | Fills in safe response-area defaults (`name`, `negStyle`, etc.) |
| Precheck | [precheck.py](precheck.py) | Cross-file rules and filename-on-disk presence |
| Templates | [templates/](templates/) | Render-time XML structure (round-trippable with `import_mobius.py`) |
| Tests | [tests/](tests/) | Unit + regression tests; gotcha inventory in `test_precheck.py` |

When tightening any of these layers, run `python -m pytest tests/ -q` and verify the count is non-decreasing. Existing 180 tests are the safety net.

## Important constraints when editing templates

The Jinja templates under [templates/](templates/) are exercised by the round-trip tests against fixtures in [tests/fixtures/mobius_exports/](tests/fixtures/mobius_exports/). Round-trip support (parse a Mobius export → re-render → produce structurally equivalent output) was the rationale for the post-`6e6882e` template refactor. Changes that look like simplifications often break round-trip. Always run the full test suite before committing template edits, and read the existing template macro structure (`question_template.xml`, `part_template.xml`, `manifests/*.xml`) rather than rewriting from scratch.

## Profiles and render modes

Defined in [nobius.json](nobius.json) (profiles) and [cli_common.py](cli_common.py) (render modes). Profile controls theme + scripts location (`exam` vs `html_preview`); render mode controls manifest shape + question layout (`assignment` vs `exercise`). Most tasks use defaults — only deviate with a clear reason.

## Style and tooling

- `python -m ruff check .` — lint
- `python -m pytest tests/ -q` — test suite
- Match the Jinja indentation, JSON ordering, and field naming used by neighbouring files. Do not introduce new dependencies without justification.
- UIDs are stable identities. Never regenerate them (`--reset-uid`) without explicit instruction; use `--write-missing-uids` only on first render of new content.

## Common pitfalls observed in past sessions

See the gotcha catalogue in [.claude/skills/authoring-nobius-sheets/SKILL.md](.claude/skills/authoring-nobius-sheets/SKILL.md). Highlights:

- Whitespace in `media_folder` or `media[]` filenames — silent Mobius import failure
- Stale `media[]` references (file removed but JSON still lists it) — broken image in Mobius
- `input_symbols` placed inside an individual `responses[i]` instead of at part level — silently dropped
- `Multiple Selection` with single-index answer — semantically wrong (use `Non Permuting Multiple Choice`)
- Long inline equations (`\(...\)`) that should be display (`\[...\]`)
- TeX-only constructs (`~` for nbsp, `\'e` for accents, `\addpoints`, equation environments) leaking into JSON statements

Each is documented with symptom and fix in the skill.
