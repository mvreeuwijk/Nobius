# Nobius (_Mobius Sheet Generator_)

Python package to generate tutorial sheets for the EdTech Mobius platform from local JSON source files.

Configuration is driven by the repo-level `nobius.json` file rather than editing hardcoded URLs in the generator source.

The checked-in `nobius.json` contains named profiles. `default_profile` drives normal export/PDF workflows, while `html_preview_profile` drives `preview_html.py`.

Primary workflows:

- export Mobius packages with `export_mobius.py`
- create local HTML previews with `preview_html.py`
- create LaTeX and PDF outputs with `export_pdf.py`
- import Mobius XML/ZIP exports with `import_mobius.py`
- run the regression suite with `pytest -q tests`
- run lint checks with `python -m ruff check Nobius`

## First render and stable UIDs

Nobius treats `uid` values as stable question identities. That matters when you export/import the same content to Mobius multiple times: if the `uid` changes, Mobius will treat the question as new content rather than an update.

Because of that, rendering refuses to proceed when a sheet or question is missing a `uid`. For a brand-new sheet, initialize and persist missing identities once:

```bash
python export_mobius.py "C:\path\to\sheet" --write-missing-uids --config nobius.json
```

After that, normal renders should be read-only with respect to the source JSON.

## HTML mode

Nobius supports a first-class `HTML` response mode for questions that need a custom interactive widget.

This is intended for cases where `custom_response` is not enough:

- `custom_response` is for arranging standard Mobius response areas in a custom layout
- `HTML` is for authoring a real HTML/CSS/JavaScript component with grading hooks

Typical uses:

- canvas- or SVG-based interactions
- drag/drop or geometry widgets
- custom visual controls that return a structured response to Mobius grading

Example:

```json
"response": {
  "mode": "HTML",
  "gradingType": "auto",
  "answer": "42",
  "html": "<div id=\"widget\"></div>",
  "css": "#widget { min-height: 20px; }",
  "javascript": "function initialize(interactiveMode) {}\nfunction setFeedback(response, answer) {}\nfunction getResponse() { return '42'; }",
  "grading_code": "evalb(($ANSWER)-($RESPONSE)=0);"
}
```

For auto-graded HTML questions, the JavaScript `getResponse()` value becomes `$RESPONSE` in the Maple grading code.

## Current scope

The active Nobius workflow is centered on:

- standard sheet rendering
- profile-specific rendering via `export_mobius.py --profile exam`
- local HTML preview generation
- LaTeX and PDF generation from Nobius JSON
- Mobius ZIP/XML import back into Nobius JSON
- HTML response components
- document upload components

There is some validation scaffolding for adaptive-question constraints, but adaptive questions are not part of the current recommended authoring workflow.

Please read the documentation for this package in the repo `docs/` tree or via the published site configured for your fork.
