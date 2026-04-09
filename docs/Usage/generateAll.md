# generateAll.py Documentation

## Introduction

`generateAll.py` is a batch wrapper around `export_mobius.py`. It renders every sheet directory in a parent folder, merges the produced XML manifests into one `all_sheets.xml`, and bundles the copied media into `all_media.zip`.

## Usage

```bash
python generateAll.py SHEETS_DIR OUTPUT_DIR [--reset-uid] [--config CONFIG] [--render-profile {standard,exam}] [--continue-on-error]
```

- `SHEETS_DIR`: parent directory containing one subdirectory per sheet
- `OUTPUT_DIR`: folder where the merged XML, media bundle, and timing summary should be written
- `--reset-uid`: regenerate question and sheet UIDs before rendering
- `--config`: pass a custom config JSON file through to `export_mobius.py` (otherwise `nobius.json` is used)
- `--render-profile`: render all sheet folders using the selected `export_mobius.py` profile
- `--continue-on-error`: keep processing remaining sheet folders if one render fails

## Outputs

`generateAll.py` writes:

- `all_sheets.xml`
- `all_media.zip`
- `question_timings.txt`
- an intermediate `xml/` directory containing per-sheet XML files
- an intermediate `web_folders/` directory containing copied media

## Notes

This script is still a wrapper around repeated single-sheet renders, not a dedicated shared rendering pipeline. It is useful for batch assembly, but the main single-sheet workflow remains `export_mobius.py`.
