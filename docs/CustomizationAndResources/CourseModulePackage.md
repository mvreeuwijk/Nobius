# Course Module Package

Nobius now targets an inferred Möbius course-module package format based on real exported content from Möbius.

## Important limitation

DigitalEd does not publish a full external schema for hand-authored Möbius content ZIP files. The package structure in Nobius is therefore based on:

- real Möbius-exported course-module ZIP files
- observed importer behavior
- round-trip regression tests in this repo

This means the package format should be treated as an implementation target, not an official vendor schema.

## Current package shape

The rendered `manifest.xml` now follows a course-module structure with these top-level sections:

- `module`
- `questionGroups`
- `assignmentUnits`
- `questions`
- `assignments`
- `assignment`
- `authors`
- `schools`
- `webResources`

For a single rendered sheet, Nobius currently emits:

- one assignment unit
- one assignment of category `LESSON`
- one `lsqGroup` per question inside the assignment
- one web-resource folder for the sheet, only when referenced media is present

## Media bundling

Nobius only bundles media files that are actually referenced by question content.

This avoids importing stray files that happen to exist in a sheet `media/` folder, which can otherwise cause package-import failures.

## Batch merge

`generateAll.py` merges single-sheet manifests into a larger course-module manifest using the same inferred structure.

The batch skeleton lives in:

- `templates/manifests/master_batch.xml`
- `templates/manifests/media_manifest.xml`

This keeps batch package structure aligned with the main render templates instead of duplicating XML inline in Python.

## Regression coverage

The repo includes regression coverage for:

- manifest shape for rendered example content
- TemplateQuestions ZIP structure
- real Möbius-exported package import
- media and document-upload round trips

If Möbius importer behavior changes again, update the package generation logic using a newly exported known-good course-module ZIP as the comparison baseline.
