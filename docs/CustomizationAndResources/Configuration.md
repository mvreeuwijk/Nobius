# Nobius Configuration

Nobius now reads deployment-specific settings from a repo-level `nobius.json` file. This keeps Mobius paths out of the Python source and makes it practical to test different render targets.

## Location

By default, the tools look for:

```json
nobius.json
```

in the root of the Nobius repository.

The checked-in defaults are placeholders and must be replaced with deployment-specific Mobius paths before rendering.

You can override that on the command line with:

```bash
python generateGroup.py SHEET_DIR --config path/to/nobius.json
python generateGroup.py SHEET_DIR --config path/to/nobius.json --render-profile exam
python generateJSON.py EXPORT.zip --config path/to/nobius.json
python generateAll.py SHEETS_DIR OUTPUT_DIR --config path/to/nobius.json
```

## Supported keys

```json
{
  "render": {
    "theme_location": "/themes/...",
    "scripts_location": "/web/.../QuestionJavaScript.txt",
    "exam_theme_location": "/themes/...",
    "exam_scripts_location": "/web/.../QuestionJavaScript.txt"
  },
  "import": {
    "strip_uids": false,
    "media_strategy": "copy"
  }
}
```

## Render settings

- `render.theme_location`: theme used by `generateGroup.py`
- `render.scripts_location`: shared Mobius JavaScript path used by `generateGroup.py`
- `render.exam_theme_location`: theme used by `generateGroup.py --render-profile exam`
- `render.exam_scripts_location`: shared Mobius JavaScript path used by `generateGroup.py --render-profile exam`

If exam and non-exam deployments use the same Mobius resources, you can point both sets of keys at the same values.

## Import settings

- `import.strip_uids`: default for whether imported JSON should have `uid` values removed
- `import.media_strategy`: currently `copy`; referenced media from the Mobius export is copied into the imported sheet folder

Command-line flags still override config defaults. For example, `generateJSON.py --no-uid` strips UIDs even if `import.strip_uids` is `false` in `nobius.json`.
