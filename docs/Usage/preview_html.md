# preview_html.py Documentation

## Introduction

`preview_html.py` renders a Nobius sheet and creates a local HTML preview site that can be opened directly in a browser. It is useful for checking question structure, theme CSS, help-panel behaviour, and MathJax rendering before importing a package into Mobius.

## Usage

Run the script from the `Nobius` directory:

```bash
python preview_html.py SHEET_PATH [--profile PROFILE] [--render-mode {assignment,exercise}] [--config CONFIG] [--output-dir OUTPUT_DIR]
```

Where:

- `SHEET_PATH` is the path to the Nobius sheet directory.
- `--profile` selects the named Nobius profile. If omitted, the config's `html_preview_profile` is used.
- `--render-mode` selects the manifest/layout shape. Use `assignment` for assignment-style output and `exercise` for question-bank style output.
- `--config` points to the Nobius config JSON file. By default the tool uses `nobius.json` from the repo root.
- `--output-dir` overrides the preview destination. By default the preview is written under the sheet's `renders/` folder.

## Output

The preview generator creates:

- an `index.html` page listing the questions in the sheet
- one HTML page per question
- a local `assets/` folder containing extracted media from the rendered ZIP

Open `index.html` in a browser to inspect the rendered questions.

## Notes

- The preview embeds the tracked theme CSS and preview JS directly into the generated pages.
- MathJax is loaded from CDN and renders `\(...\)` and `\[...\]` expressions.
- The preview is intended for local inspection. It does not replace a real Mobius import test.
