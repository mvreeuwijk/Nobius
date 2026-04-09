# Nobius Configuration

Nobius now reads deployment-specific settings from a JSON config file. This keeps Mobius paths out of the Python source and makes it practical to test different render targets.

## Location

By default, the tools look for:

```json
nobius.json
```

in the root of the Nobius repository.

The checked-in defaults are placeholders and must be replaced with deployment-specific Mobius paths before rendering.

If you need more than one deployment profile, keep additional JSON files alongside the default config. For example:

```json
nobius.json
local_preview.json
```

and pass it explicitly with `--config`.

You can override that on the command line with:

```bash
python export_mobius.py SHEET_DIR --config path/to/config.json
python export_mobius.py SHEET_DIR --config path/to/config.json --render-profile exam
python import_mobius.py EXPORT.zip --config path/to/config.json
python export_mobius_batch.py SHEETS_DIR OUTPUT_DIR --config path/to/config.json
```

## Supported keys

```json
{
  "render": {
    "theme_location": "/themes/...",
    "scripts_location": "/web/.../QuestionJavaScript.txt",
    "exam_theme_location": "/themes/...",
    "exam_scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt"
  },
  "import": {
    "strip_uids": false,
    "media_strategy": "copy"
  }
}
```

## Render settings

- `render.theme_location`: theme used by `export_mobius.py`
- `render.scripts_location`: shared Mobius JavaScript path used by `export_mobius.py`
- `render.exam_theme_location`: theme used by `export_mobius.py --render-profile exam`
- `render.exam_scripts_location`: shared Mobius JavaScript path used by `export_mobius.py --render-profile exam`

For packaged Mobius exports, `render.exam_scripts_location` can be the packaged resource URI:

```json
"__BASE_URI__Scripts/QuestionJavaScript.txt"
```

This matches exports that rely on the script bundled into `web_folders/Scripts/QuestionJavaScript.txt` inside the zip rather than an external `/web/...` URL.

If exam and non-exam deployments use the same Mobius resources, you can point both sets of keys at the same values.

## Import settings

- `import.strip_uids`: default for whether imported JSON should have `uid` values removed
- `import.media_strategy`: `copy`; referenced media from the Mobius export is copied into the imported sheet folder

Command-line flags still override config defaults. For example, `import_mobius.py --no-uid` strips UIDs even if `import.strip_uids` is `false` in the active config JSON.
