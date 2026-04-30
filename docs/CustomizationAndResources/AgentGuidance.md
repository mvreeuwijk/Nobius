# Agent guidance and Claude skills

Authoring instructions for AI coding agents working in this repository.
Human-facing usage documentation lives in the rest of this docs site;
this page describes the machine-readable companion files that travel
with the repo.

## `AGENTS.md` (repo root)

The universal entry point for any AI coding tool — Claude Code, Cursor,
Codex, Aider, etc. Orients an agent landing in the repo with:

- What this codebase is.
- Where authoring guidance lives.
- The pre-render lint flow (`python precheck.py`).
- Render commands for Mobius-bound output and what flags to avoid.
- Validation layer responsibilities (schemas, defaults, precheck,
  templates, tests).
- The round-trip invariant for template edits.
- Common pitfalls observed in past sessions.

`CLAUDE.md` is a one-line stub pointing at `AGENTS.md` so the same
guidance applies under either filename convention.

## Skills (`.claude/skills/`)

Two project-local Claude Code skills ship with the repo. Both are markdown
documents with YAML frontmatter that describes when the skill should
activate; they're discovered automatically by Claude Code when working
inside the repo.

### `authoring-nobius-sheets`

Activates on requests to create exams, problem sheets, tutorials, or
otherwise touch JSON files under `Questions/` or `tests/fixtures/`.
Documents:

- Directory layout for a sheet.
- Every supported response mode (`Numeric`, `Maple`,
  `Non Permuting Multiple Choice`, `Multiple Selection`, `List`, `Essay`)
  with its required and conditional fields.
- LaTeX/MathJax rules for `master_statement` and part `statement` strings.
- Algorithm DSL syntax (`range(...)`, `maple("fsolve(...)")`, the constant
  `Pi`, etc.).
- The render-and-verify workflow (precheck → first render with
  `--write-missing-uids` → preview → production render → upload).
- Reference exemplars in this repo (`Questions/Exam2025/`,
  `tests/fixtures/RoundTrip/`,
  `tests/fixtures/mobius_exports/RoundTripDemo.zip`).
- A gotcha catalogue: every Mobius failure mode observed in production
  with symptom and fix.

Read or extend this skill when documenting a new authoring pattern.

### `debugging-mobius-imports`

Activates when a Mobius import fails with the generic "Application
Error" or any opaque server-side error. Encodes the bisection workflow
that has localised every failure so far:

1. Run `precheck.py` first.
2. Confirm render flags (theme + mode).
3. Compare manifest structure against
   `tests/fixtures/mobius_exports/RoundTripDemo.zip`.
4. Build per-question test ZIPs with fresh UIDs and identify which
   questions fail.
5. Within a failing question, strip features (media, algorithm,
   exotic Unicode) until the smallest failing variant remains.

Includes a known failure-cause taxonomy keyed on observed symptoms.

## Maintaining the agent layer

When a new failure mode or authoring pattern is discovered:

1. Add a regression test in `tests/test_precheck.py` (if mechanically
   enforceable).
2. Update the gotcha catalogue in
   `.claude/skills/authoring-nobius-sheets/SKILL.md`.
3. If it changes the user-facing workflow (e.g. a new render flag,
   profile, or check), also update `AGENTS.md`.

Skills, `AGENTS.md`, and the precheck rule set should evolve together
with the codebase — they encode hard-won knowledge that's expensive to
re-derive from session to session.
