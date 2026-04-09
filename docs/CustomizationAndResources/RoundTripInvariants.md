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
- expected question/part wrapper structure around statements, responses, worked solutions, final answers, and tutorials
- help/solution/tutorial containers used by the HTML scraper
- media containers carrying `data-propname`-addressable content

If these markers are removed from a template, the package may still render correctly in Mobius, but import fidelity will drop.

## Safe vs unsafe template edits

### Generally safe

- CSS changes
- non-structural class names used only for styling, when they are not relied on by the importer
- visual layout changes that preserve `data-propname` and response placeholder structure

### Round-trip breaking

- removing `data-propname`
- flattening or removing worked-solution / final-answer / tutorial containers the importer expects
- hand-editing generated response placeholders
- changing template structure so authored content is no longer reachable by the HTML scraper

## Practical rule

If you want a template to remain round-trippable:

- let Nobius generate response placeholders
- keep `data-propname` markup intact
- preserve the authored-content container structure

If you only need a Mobius-valid export and do not care about high-fidelity re-import, the template can be much freer.
