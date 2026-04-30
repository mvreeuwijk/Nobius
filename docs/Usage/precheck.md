# `precheck.py`

Pre-export sanity check for sheet directories. Catches authoring patterns
that the per-file JSON schemas can't enforce — cross-file consistency
(e.g. media references vs files on disk), Mobius-specific quirks
(whitespace in URL paths breaks the importer), and silently-ignored
content (e.g. `input_symbols` placed in the wrong nesting level).

Every export and preview entry point (`export_mobius.py`,
`export_mobius_batch.py`, `export_pdf.py`, `preview_html.py`) calls
`precheck` automatically and aborts on any error-level finding. Run it
explicitly while authoring to get pinpointed JSON-path messages.

## Usage

```bash
python precheck.py "<sheet folder>"
```

Exits 0 when there are no errors (warnings still print but don't block),
1 when one or more errors are found.

```python
from precheck import check_sheet, run

issues = check_sheet("Questions/Exam2027")  # list[Issue]
error_count = run("Questions/Exam2027")     # prints to stderr, returns int
```

`Issue` is a small dataclass with `severity` (`"error"` or `"warning"`),
`location` (human-readable path into the sheet), and `message`.

## Rules enforced

### Errors (block export)

| Rule | Why |
| --- | --- |
| `SheetInfo.json` exists | Every sheet must have one |
| Each listed `questions[]` entry has a matching `QuestionN.json` file | Otherwise the renderer skips the question silently |
| No whitespace in any `media[]` filename | Mobius URL-encodes the path; `%20` segments produce a generic "Application Error" with no diagnostic |
| Every `media[]` reference exists in the sheet's `media/` directory | Otherwise Mobius shows a broken image after import |
| `media_folder` set in `SheetInfo.json` whenever the sheet references any media | The renderer's default falls back to the (usually spaced) sheet name; same import-failure mode as above |
| `input_symbols` lives at the part level, never inside `responses[i]` | The renderer silently ignores it in the wrong place |
| `Multiple Selection` `answer` has at least 2 comma-separated indices | Single-index multi-select is a sign you wanted `Non Permuting Multiple Choice` instead |

### Warnings (informational, don't block)

| Heuristic | Why surfaced |
| --- | --- |
| Long inline math (`\(...\)` over ~80 chars containing `\dfrac`/`\sum`/`\int`/`\begin{...}`/`\left(`) | Almost always meant for display (`\[...\]`) — squashed into a paragraph otherwise |
| `Word~Word` patterns | TeX non-breaking space renders as a literal `~` in HTML |
| TeX accent escapes (`\'e`, `\` `e`, `\^e`, `\"e`) | Don't render in MathJax/HTML — use Unicode characters |
| LaTeX equation environments (`\begin{equation}`, `\begin{align}`, …) | Convert to `\[ ... \]` for reliable display rendering |
| `\addpoints{N}` | TeX-only ExSheets command; use `post_response_text: "[N MARKS]"` instead |

Warnings print but don't fail the export. Treat them as a review prompt.

## Adding new rules

When a new failure mode is discovered:

1. Add a check function in `precheck.py` and call it from `check_sheet()`.
2. Add a regression test in `tests/test_precheck.py` — one test per rule.
3. If structurally enforceable as a JSON-schema constraint (rather than
   cross-file logic), prefer adding it to the relevant schema in
   `validation/schemas/` first.
4. Update the gotcha catalogue in
   [`.claude/skills/authoring-nobius-sheets/SKILL.md`](https://github.com/mvreeuwijk/Nobius/tree/main/.claude/skills/authoring-nobius-sheets/SKILL.md)
   so future authors and AI agents see the symptom→fix mapping.

`tests/test_precheck.py` is the canonical inventory of known failure
modes — keep it in sync with the rule set.
