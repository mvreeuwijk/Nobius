# Nobius Configuration

Nobius uses a single JSON config file with named profiles. The checked-in [`nobius.json`](../../nobius.json) is the default config for this repo.

## Location

By default, the tools load:

```text
nobius.json
```

from the root of the Nobius repository.

You can override that with `--config`.

## Structure

```json
{
  "default_profile": "exam",
  "html_preview_profile": "html_preview",
  "profiles": {
    "problem_set": {
      "render": {
        "theme_location": "/themes/...",
        "scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt"
      },
      "pdf": {
        "heading": "problem_sets"
      }
    },
    "exam": {
      "render": {
        "theme_location": "/themes/...",
        "scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt"
      },
      "pdf": {
        "heading": "problem_sets"
      }
    },
    "html_preview": {
      "render": {
        "theme_location": "/themes/test-theme",
        "scripts_location": "/web/test/scripts.js"
      },
      "pdf": {
        "heading": "generic"
      }
    }
  },
  "import": {
    "strip_uids": false,
    "media_strategy": "copy"
  },
  "pdf": {
    "headings": {
      "problem_sets": {
        "document_title": "Fluid Mechanics 2\\\\Problem Sets \\\\2021/22",
        "footer_label": "Set \\#",
        "section_label": "MECH50010 Problem Set \\#"
      }
    }
  }
}
```

## Key Ideas

- `default_profile`: profile used by default for `export_mobius.py` and `export_pdf.py`
- `html_preview_profile`: profile used by default for `preview_html.py`
- `profiles.<name>.render`: Mobius theme and shared script URIs
- `profiles.<name>.pdf.heading`: PDF heading scheme for that profile
- `pdf.headings`: reusable heading definitions shared across profiles
- `import`: importer defaults shared across profiles

Within each `pdf.headings.<name>` block:

- `document_title` controls the main title text at the top of the PDF, including the year if you include it there
- `footer_label` controls the footer label text
- `section_label` controls the numbered section heading prefix

## CLI usage

Examples:

```bash
python export_mobius.py SHEET_DIR
python export_mobius.py SHEET_DIR --profile problem_set
python export_mobius.py SHEET_DIR --render-mode exercise
python preview_html.py SHEET_DIR
python preview_html.py SHEET_DIR --profile exam
python export_pdf.py --sheet-path SHEET_DIR --profile exam
python import_mobius.py EXPORT.zip
```

`export_mobius.py` and `preview_html.py` separate:

- `--profile`: which resource/deployment profile to use
- `--render-mode`: which manifest shape to render (`assignment` or `exercise`)

`export_pdf.py` uses the selected profile's `pdf.heading`. There is no second heading selector.

## Discovering render paths

These values are usually only obvious after the resources already exist in Mobius.

DigitalEd documents:

- theme creation and application in the Content Repository:
  <https://www.digitaled.com/support/help/admin/Content/INST-CONTENT-REPO/Themes.htm>
- content export as a `.zip` package:
  <https://www.digitaled.com/support/help/admin/Content/INST-CONTENT-REPO/ACTIONS/Export-content.htm>

Those docs do not explicitly document the internal `/themes/...` and `QuestionJavaScript.txt` URIs written into exported XML. The workflow below is therefore based on inspecting real exported Mobius packages.

Use this workflow:

1. Upload or create the shared resources in Mobius.
2. Apply the theme to at least one question or assignment.
3. Export that content as a ZIP package.
4. Open the ZIP and inspect `manifest.xml`.
5. Search for:
   - `/themes/...`
   - `/web/.../QuestionJavaScript.txt`
   - or `__BASE_URI__Scripts/QuestionJavaScript.txt`
6. Copy those values into the relevant `profiles.<name>.render` block.

In this repository, the real exported ZIPs in `tmp/` all used:

```json
{
  "theme_location": "/themes/b06b01fb-1810-4bde-bc67-60630d13a866",
  "scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt"
}
```
