# Future additions

This page lists realistic next steps for Nobius in its current form.

## Workflow and interface

- Add a simple user interface over the four main workflows:
  - `export_mobius.py`
  - `preview_html.py`
  - `export_pdf.py`
  - `import_mobius.py`
- Return clearer machine-readable output paths from the CLI tools so a future UI can call them more easily.
- Improve reporting and diagnostics for import/export jobs, especially when a conversion succeeds with warnings rather than failing outright.

## Import and round-trip fidelity

- Expand the documented import support matrix so it is clear which fields are:
  - exported by Nobius
  - recoverable from plain Mobius exports
  - recoverable only from Nobius-annotated exports
- Add stronger tests around the round-trip template invariants, especially the HTML markers required for high-fidelity re-import.
- Continue hardening the importer against malformed or partially-corrupt Mobius exports.

## PDF and preview output

- Improve PDF modes further:
  - exercise PDF
  - solutions PDF
  - review/checking PDF with metadata
- Add optional pre-rendered maths for preview and PDF output where this improves speed or portability.
- Improve HTML preview fidelity further where it still depends on external Mobius platform styling.

## Authoring model

- Support author notes in sheet and question source files without affecting rendered output.
- Add sheet-level defaults that override tool-wide defaults for common settings such as grading behaviour.
- Consider a move to YAML as an alternative source format if the benefits are worth the migration cost:
  - multiline strings
  - easier comments
  - less escaping noise for LaTeX-heavy content

## Response-area improvements

- Add more matrix response controls, such as:
  - configurable bracket style
  - arrow-key or explicit navigation controls
- Improve behaviour for questions with no response areas, for example with a clearer completion action than a normal check flow.
- Revisit algorithmic-question `Try Another` behaviour so the custom question logic is re-applied consistently after regeneration.

## Packaging and deployment

- Automate more of the package creation process around lessons and assignments where this still saves manual work in Mobius.
- Keep tightening the contract between:
  - Mobius-valid templates
  - Nobius round-trippable templates

This list is intentionally limited to work that still fits the current tool structure and workflows.
