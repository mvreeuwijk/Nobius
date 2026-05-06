---
name: authoring-nobius-sheets
description: Use when authoring or modifying Nobius sheet JSON (SheetInfo.json + Question*.json) that needs to import successfully into Mobius — covers the file layout, every supported response mode with required fields, and the non-obvious gotchas that cause Mobius "Application Error" or grade questions incorrectly. Trigger on requests to "create a new exam", "add a question", "convert a TeX exam to Nobius JSON", "build a problem sheet", and any work inside `Questions/`, `tests/fixtures/`, or sibling sheet directories.
---

# Authoring Nobius sheet JSON for Mobius import

This skill encodes how to write `SheetInfo.json` + `Question*.json` files that render into a Mobius-importable course module via `python export_mobius.py <sheet>`. Every rule below has a concrete failure mode tied to it — this is not abstract style guidance.

Before producing any output, **always run `python precheck.py <sheet>` after writing JSON files**. Precheck catches the gotchas listed here with specific error messages; if it errors, fix the source before rendering.

## Directory layout for a sheet

```
<SheetFolder>/
  SheetInfo.json
  Question1.json
  Question2.json
  ...
  media/                 (only if any question references media)
    fig_q1.png
    fig_q2.jpg
    ...
```

The `SheetFolder` name itself does not need to follow any convention; the rendered Mobius media path is controlled by the `media_folder` field in `SheetInfo.json` (see below), not by the directory name.

## SheetInfo.json — minimal valid example

```json
{
    "name": "CIVE40008 Exam 2025-2026",
    "number": 1,
    "description": "",
    "questions": ["Question1", "Question2", "Question3"],
    "uid": "<run --write-missing-uids on first render to populate>",
    "media_folder": "CIVE40008_Exam_2025_2026"
}
```

Required fields (per `validation/schemas/sheet_info.json`): `name`, `number`, `description`, `questions`, `uid`.

`media_folder` rules:
- Must contain **no whitespace**. The schema's `pattern: "^\\S+$"` enforces this.
- Required whenever any referenced question has a `media` array (the precheck enforces this cross-file rule).
- Why: Mobius URL-encodes the `__BASE_URI__<media_folder>/<file>` path into `__BASE_URI__CIVE40008%20Exam%202025-2026/...`; the `%20` segment causes a generic "Application Error" at import time with no diagnostic. Any whitespace here is fatal.
- The renderer's default falls back to the `name` field when `media_folder` is missing — and `name` typically has spaces. Always set `media_folder` explicitly when there is media.

`questions` is a list of basenames (without `.json`). For each entry `"QuestionN"` there must be a corresponding `QuestionN.json` file in the same folder.

## Question.json — minimal structure

```json
{
    "title": "Question 1",
    "master_statement": "A rectangular basin of width \\(W\\) m ...",
    "media": ["fig_q1.png"],
    "parts": [
        {
            "statement": "Calculate the restraining force \\(F_T\\).",
            "pre_response_text": "\\(F_T = \\)",
            "response": {
                "mode": "Numeric",
                "weighting": 12,
                "showUnits": true,
                "grading": "toler_perc",
                "perc": 5.0,
                "answer": {"num": "$FT", "units": "N"}
            },
            "post_response_text": "[12 MARKS]"
        }
    ],
    "algorithm": "$W = range(2, 4, 0.5); $h = range(2.5, 3.5, 0.25); $rho = 1000; $g = 9.81; $FT = 0.5*$rho*$g*$W*$h^2;",
    "uid": "<populated by --write-missing-uids on first render>"
}
```

Required fields: `title`, `parts`, `uid`. Each part requires `statement`. UIDs are auto-generated on first render with `--write-missing-uids`.

A part has either a single `response` object or a list `responses` (for multi-response groups under one shared statement). Never both.

`input_symbols` (used by Maple parts to render the symbol palette) belongs at the **part level**, sibling of `response`/`responses` — not inside an individual response. The renderer silently ignores it in the wrong place. Precheck catches this.

### Marks: `weighting` is the actual Mobius score

`weighting` on each `response` is the **mark value Mobius uses to score that response**. It is *not* cosmetic. The visible `[N MARKS]` text in `post_response_text` is purely for the student — Mobius does not parse it.

When converting a TeX exam, every `\addpoints{N}` must set **both**:
1. `"weighting": N` on the corresponding `response` (the actual score)
2. `"post_response_text": "[N MARKS]"` on the part or response (what the student sees)

If you only do (2), every response silently scores as `weighting: 1` (the default in `validation/defaults/response_areas.json`), and a 12-mark Maple part counts the same as a 1-mark MCQ — students see "[12 MARKS]" but the gradebook records 1. This regression hit Exam2026 the first time round.

For multi-response parts, give each `responses[i].response` its own `weighting` matching the `[N MARKS]` shown next to it. Mobius emits `<weighting>` at the question level as a comma-separated list of all part weightings in order, so a per-response value is exactly what's needed.

**Sanity check after conversion:** sum the weightings per question — they should match the per-question total in the TeX (typically equal across questions, e.g. 25 marks each for a 150-mark exam).

## Response modes — required fields

The renderer fills in safe defaults (from `validation/defaults/response_areas.json`) for `name`, `comment`, and mode-specific style fields. Author only what the question genuinely needs.

### Numeric

```json
{
    "mode": "Numeric",
    "weighting": 1,
    "showUnits": true,
    "grading": "toler_perc",
    "perc": 5.0,
    "answer": {"num": "$variable_or_literal", "units": "m^3/s"}
}
```

`grading` ∈ {`exact_value`, `exact_sigd`, `toler_abs`, `toler_sigd`, `toler_perc`}. Conditional fields: `digit` for sigfig modes, `err` for absolute tolerance, `perc` for percentage tolerance.

If `showUnits: false`, set `answer.units: ""`.

### Maple (algebraic answer)

```json
{
    "mode": "Maple",
    "weighting": 1,
    "maple": "Nobius:-GradePat($ANSWER, $RESPONSE);",
    "libname": "/web/Cive4000007/Public_Html/Nobius4.mla",
    "mapleAnswer": "rho*g*Q*L*s"
}
```

`mapleAnswer` is the canonical correct expression in Maple syntax. `libname` is the path to the institution's Maple library on the Mobius server. Use the same value as in existing working sheets (`Questions/Exam2024/`, `Questions/Exam2025/`).

For Maple parts, place `input_symbols` at the **part level**, never inside the response:

```json
{
    "statement": "...",
    "response": { "mode": "Maple", ... },
    "input_symbols": [
        ["\\(\\rho\\)", "rho"],
        ["\\(g\\)", "g"]
    ]
}
```

Each entry is `[display_label, maple_variable_name]`. The display label uses the same MathJax `\\(...\\)` you'd put in a statement.

### Non Permuting Multiple Choice (single correct)

```json
{
    "mode": "Non Permuting Multiple Choice",
    "weighting": 1,
    "answer": 2,
    "choices": ["option a", "option b", "option c", "option d"]
}
```

`answer` is a 1-based **integer** index into `choices`. Use this when there is exactly one correct answer.

### Multiple Selection (two or more correct)

```json
{
    "mode": "Multiple Selection",
    "weighting": 1,
    "answer": "1,3,4",
    "choices": ["option a", "option b", "option c", "option d", "option e"]
}
```

`answer` is a **comma-separated string of 1-based indices**. Must contain **at least two indices** — a single-index `Multiple Selection` is a sign you actually want `Non Permuting Multiple Choice` (precheck flags this).

Use this for "select all that apply" / "tick all that apply" / "which are correct?" prompts when the answer set has 2+ correct options.

### List with regex `.*` (manually marked free-text)

```json
{
    "mode": "List",
    "weighting": 1,
    "display": {"display": "text", "permute": false},
    "grader": "regex",
    "answers": [".*"],
    "credits": [1]
}
```

For sketch/diagram/explanation parts marked outside Mobius (typically against a paper booklet). Auto-grades any non-empty answer as full credit. Pair with a statement that ends with `[This question will be marked using your answer booklets -- you can leave the box below blank.]`.

### Essay (free-text with optional keyword scoring)

```json
{
    "mode": "Essay",
    "weighting": 1,
    "keywords": "[]",
    "maxWordcount": 0
}
```

Alternative to `List`/regex for prose answers. Less commonly used in this codebase; prefer `List`/regex for consistency with existing exam content unless a wordcount cap is genuinely needed.

## LaTeX inside `master_statement` and `statement` strings

Mobius renders math via MathJax. Treat statements as HTML that may contain MathJax delimiters.

Inline math: `\\(...\\)`. Display (centred, own line): `\\[...\\]`. Use display for any equation longer than ~80 characters or containing `\\dfrac`/`\\sum`/`\\int`/`\\begin{...}`/`\\left(`/`\\right)` — otherwise readers see the equation squashed into a paragraph.

LaTeX-only constructs that do not work in MathJax/HTML and must be avoided in JSON strings:
- `~` between words (TeX non-breaking space) — renders as a literal `~` character. Use a regular space.
- `\\'e`, `\\\`e` and similar TeX accent escapes — render as literal text. Use Unicode (é, è, …) directly in the JSON string.
- `\\addpoints{N}` — TeX-only ExSheets command. Translate to **both** `"weighting": N` on the matching response (actual Mobius score) **and** `"post_response_text": "[N MARKS]"` for the visible label. Setting only the visible label leaves the score at the default `1` — see the "Marks" section above.
- `\\input{...}`, `\\include{...}` — no file inclusion at the JSON layer.
- `\\begin{equation}...\\end{equation}`, `\\begin{align}...` — convert to `\\[...\\]` (single-line display).

JSON string escaping: backslashes inside JSON strings double up. So a single `\(` in the rendered HTML is `\\(` in the JSON source. A `\\frac` becomes `\\\\frac` in JSON.

## Algorithm field

The `algorithm` string is Maple syntax executed by Mobius before rendering each variant of the question. It assigns variables (prefixed with `$`) that can be referenced from the master_statement, part statements, and `answer.num`.

```
$W = range(2, 4, 0.5); $h = range(2.5, 3.5, 0.25); $rho = 1000; $g = 9.81;
$FT = 0.5*$rho*$g*$W*$h^2;
$h_eq = maple("fsolve($Q - $C*$w^(3/2)*h^(3/2)*sqrt($s)/sqrt($w+2*h), h, 0.01..5)");
```

Allowed: `range(start, end, step)` for randomised values, standard maths functions (`sqrt`, `exp`, `cos`, `sin`, `acos`, `arctan`), the constant `Pi`, and `maple("<arbitrary maple expression>")` for things that need the full Maple evaluator (e.g. `fsolve`, `min`, conditional logic).

Reference variables in statements directly: `\\(F_T = \\) $FT N`. Use them as the `answer.num` for Numeric responses: `"answer": {"num": "$FT", "units": "N"}`.

## Render and verify workflow

```bash
# from inside Nobius/
python precheck.py "../Questions/<SheetFolder>"
python export_mobius.py "../Questions/<SheetFolder>"
```

The default render-mode (`assignment`) and default profile produce the assignment-style Mobius import that the user actually wants:
- Production theme `/themes/b06b01fb-1810-4bde-bc67-60630d13a866` (renders correctly in the user's Mobius)
- exam.html layout (suppresses solutions/help — correct for live exams)
- `manifests/assignment.xml` (imports as a clickable assignment, not a question-bank)

**Never use `--profile html_preview` for Mobius-bound output** — it injects `/themes/test-theme`, which the production Mobius doesn't have, so figures and styling break even if the import succeeds.

`--render-mode exercise` is for question-bank-style imports (questions go to content repo without an assignment wrapper) and includes solutions/help in the rendered HTML — wrong for an exam.

`preview_html.py` for in-browser local previews; works with either profile.

## Reference exemplars in this repo

When unsure, look at these — all import successfully in production:
- `Questions/Exam2025/` — full 6-question exam, hand-authored, minimal fields, with figures
- `Questions/Exam2024/` — same format
- `tests/fixtures/RoundTrip/` — clean 10-question set covering every response mode (Multiple Selection, Multiple Choice, Numerical, Symbolic, Essay, Matching, True/False, Text Entry, Multipart hybrid)
- `tests/fixtures/mobius_exports/RoundTripDemo.zip` — the literal manifest Mobius produces; structurally identical to what the renderer should emit

## Gotcha catalogue (every one cost time during 2026-04-30 debugging)

| Gotcha | Symptom | Fix |
|---|---|---|
| Whitespace in `media_folder` | "Application Error" on import, no diagnostic | `^\S+$` — use underscores |
| Whitespace in any `media[]` filename | Same | Rename file, update reference |
| `media[]` references a file not present in `media/` directory | Renders as broken image in Mobius — silent until inspection | Add file or remove reference |
| `media[]` non-empty but `media_folder` missing | Same — falls back to spaced sheet name | Set `media_folder` explicitly |
| `input_symbols` inside `responses[i]` | Renderer emits no `<table>` of symbols; students can't enter Maple expressions | Move to part level (sibling of `responses`) |
| `Multiple Selection` with single-index answer (`"2"`) | Mobius rejects the manifest | Use `Non Permuting Multiple Choice` with integer `answer: 2` |
| `~` between words in statement | Literal tilde appears in rendered HTML | Replace with a regular space |
| Long inline `\(...\)` equation | Equation squashed into paragraph | Use `\[...\]` for display |
| `--profile html_preview` for Mobius export | Imports but theme is missing → broken styling | Default profile only for Mobius-bound builds |
| `--render-mode exercise` for an exam | Solutions/help shown to students | Default mode (assignment) for exam content |

The precheck script enforces the structural items in this table. The presentational items (LaTeX remnants, inline-vs-display equations) are not yet enforced — when authoring, double-check against `tests/fixtures/RoundTrip/` for the conventions.
