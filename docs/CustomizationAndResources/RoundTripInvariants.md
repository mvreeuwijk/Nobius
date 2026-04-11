# Round-Trip Invariants

Nobius supports two different levels of import fidelity:

- **Plain Mobius import**: import a normal Mobius XML or ZIP export and recover a usable Nobius JSON sheet.
- **High-fidelity Nobius round-trip**: export from Nobius, re-export from Mobius, then import back into Nobius with most authored structure preserved.

The difference is not whether the export is "from Mobius" or "from Nobius". Both are Mobius exports. The difference is whether the question HTML still contains the extra structural annotations that Nobius embeds for reconstruction.

## Mobius-generated mechanics

These are part of normal Mobius question structure. Nobius uses them, but does not define them.

- Response placeholders such as `<1>`, `<2>`, ...
- The `<parts>` definitions in question XML
- Standard question and assignment XML structure

These should be treated as generated mechanics, not hand-authored template content.

## Nobius round-trip annotations

These are the structural markers that allow `import_mobius.py` to reconstruct rich Nobius JSON fields rather than only a minimal question.

- `data-propname` attributes on authored content
- response placeholders such as `<1>`, `<2>`, ... appearing in the rendered HTML
- the top-level question `<text>` node containing the rendered Nobius question HTML
- media containers carrying `data-propname`-addressable content
- input-symbol tables for Maple questions

If these markers are removed from a template, the package may still render correctly in Mobius, but import fidelity will drop.

## Intended importer contract

The importer is intentionally coupled to a small set of Nobius-authored HTML annotations. This is by design: Nobius exports extra reconstruction metadata into the Mobius question HTML, and the importer reads that metadata back.

The important point is that the contract should be based on authored metadata, not incidental presentation structure.

### Intended and stable

- `data-propname` values such as `title`, `master_statement`, `parts.1.statement`, `parts.1.response`, `parts.1.pre_response_text`
- placeholder tags like `<1>` that identify response-area positions
- `div.part` wrappers, because parts are a semantic authored unit
- `table.input-symbols-table` with `tr.code` and `tr.symbols` for Maple input-symbol recovery
- the XML `<parts>` definitions, which are used to recover response definitions even when the HTML wrapper is sparse

### Avoid relying on casually

- purely visual wrapper nesting
- styling-only class names
- help-panel layout details
- exact tab markup or other presentational containers

The importer may still contain a small number of fallbacks for current rendered HTML, but those should be treated as repair paths, not the main compatibility contract.

## Safe vs unsafe template edits

### Generally safe

- CSS changes
- non-structural class names used only for styling, when they are not relied on by the importer
- visual layout changes that preserve `data-propname` and response placeholder structure

### Round-trip breaking

- removing `data-propname`
- removing response placeholders such as `<1>`
- moving the actual question HTML out of the question's top-level `<text>` node
- removing semantic part wrappers entirely
- hand-editing generated response placeholders
- changing template structure so authored content is no longer reachable by the HTML scraper

## Practical rule

If you want a template to remain round-trippable:

- let Nobius generate response placeholders
- keep `data-propname` markup intact
- preserve the semantic authored-content structure

If you only need a Mobius-valid export and do not care about high-fidelity re-import, the template can be much freer.
