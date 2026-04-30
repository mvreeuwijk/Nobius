---
name: debugging-mobius-imports
description: Use when a Mobius import fails with "Application Error" (or any opaque server-side error) despite the JSON passing precheck and the renderer producing a ZIP. Encodes the bisection workflow that pinpoints which question, which content type, or which cross-cutting setting is rejected. Trigger on phrases like "Mobius import fails", "Application Error", "Mobius rejects", "import returned 500", or when a freshly-rendered ZIP behaves differently from a previously-imported one.
---

# Debugging Mobius imports

When a sheet ZIP fails to import into Mobius with the generic
"Application Error has occurred while processing your request" message,
the failure has no diagnostic on the client side and Mobius's own logs are
typically not accessible. The only reliable way to localise the cause is
to bisect.

## Order of operations (cheapest first)

### 1. Run precheck and look at every error

```bash
python precheck.py "<sheet>"
```

If precheck flags anything, fix that and retry the import — the rule set in
`tests/test_precheck.py` is the inventory of known failure modes. The
"Application Error" almost always corresponds to one of those rules.

If precheck is clean, continue.

### 2. Confirm the renderer command and flags

The sheet must be rendered with the **default** mode and profile for an
exam-style Mobius import:

```bash
python export_mobius.py "<sheet>"     # NO extra flags
```

- `--profile html_preview` injects the test theme `/themes/test-theme`,
  which the production Mobius doesn't have. The import may succeed but
  formatting will be visibly broken (unstyled question, broken layout).
- `--render-mode exercise` produces a question-bank manifest (no
  `<assignmentUnits>`) and the exercise.html layout (which exposes
  solutions). Imports as a content-repo dump, not as a clickable
  assignment.

Both deviations are common when copy-pasting old commands.

### 3. Compare the manifest against the Mobius reference

```bash
python -c "import zipfile; z=zipfile.ZipFile('<sheet>/renders/<name>.zip'); print(z.read('manifest.xml').decode())" | head -60
```

Diff the structure against `tests/fixtures/mobius_exports/RoundTripDemo.zip`
(the literal export Mobius itself produces). Things that should match:

- `<courseModule>` → `<module>` → either `<assignmentUnits>` (assignment
  mode) or `<questionGroups>` (exercise mode), then `<questions>`, then
  `<webResources>`.
- Per-question wrapper element names and ordering.
- `<webResources>` contains `web_folders/Scripts` plus, if there's media,
  `web_folders/<media_folder>` — both as children of a single
  `<webResources>` block.

If a fresh render of `tests/fixtures/RoundTrip/` (sheet known to import
cleanly) succeeds while the user's sheet does not, then the renderer is
fine and the issue is content-specific. Move to step 4.

### 4. Bisect by question

Build a one-question test ZIP for each `QuestionN.json` in isolation, with
fresh UIDs so prior failed-import side effects can't interfere:

```python
import shutil, json, uuid, subprocess
from pathlib import Path

src = Path("Questions/<sheet>")
out_root = Path("tmp/per_question")
out_root.mkdir(parents=True, exist_ok=True)

for question_basename in json.loads((src/"SheetInfo.json").read_text())["questions"]:
    sheet_dir = out_root / f"{question_basename}_only"
    if sheet_dir.exists():
        shutil.rmtree(sheet_dir)
    sheet_dir.mkdir()
    si = json.loads((src/"SheetInfo.json").read_text())
    si["name"] = f"Test {question_basename}"
    si["questions"] = [question_basename]
    si["uid"] = str(uuid.uuid4())
    (sheet_dir/"SheetInfo.json").write_text(json.dumps(si, indent=4))
    q = json.loads((src/f"{question_basename}.json").read_text())
    q["uid"] = str(uuid.uuid4())
    (sheet_dir/f"{question_basename}.json").write_text(json.dumps(q, indent=4))
    if (src/"media").exists():
        shutil.copytree(src/"media", sheet_dir/"media")
    subprocess.run(["python", "Nobius/export_mobius.py", str(sheet_dir)])
```

Hand the user one ZIP at a time and ask which import. The pattern of
which questions succeed vs fail tells you what's specific:

- **All fail**: cross-cutting (likely `media_folder`, theme, render mode).
- **Only questions with figures fail**: media handling. See step 5.
- **Only questions with one specific response mode fail**: that mode.
- **One specific question fails**: content in that question (algorithm
  syntax, unusual LaTeX, malformed UTF-8).

### 5. Bisect within a failing question

If a single question fails, copy it to a new test sheet and progressively
strip features until it imports:

- Remove the `media` field — does the bare statement still fail? If it now
  imports, the issue is figure-related.
- Remove the algorithm — does it fail without parameter substitution?
- Replace the `master_statement` with a one-line ASCII string — does
  exotic content (Unicode, complex MathJax) trip Mobius?
- For multi-response parts, reduce to a single response.

The goal is to reach the smallest variant that still fails. That diff
points directly at the cause.

## Known failure-cause taxonomy (so far)

| Symptom | Root cause | Fix |
| --- | --- | --- |
| All ZIPs with figures fail; figure-less work | `media_folder` (or filename) contains whitespace; manifest emits `__BASE_URI__path%20with%20space/...` which Mobius rejects | Set `media_folder` to a no-whitespace identifier; rename files. Both enforced by precheck. |
| Imports but figures show as broken images | `media[]` references a file not present in `media/`, or `media_folder` doesn't match the bundled subfolder | Check `webResources` block in manifest matches actual ZIP entries. Precheck enforces presence. |
| Imports but no figures and broken styling | `--profile html_preview` injected the test theme into the rendered HTML | Re-render without the flag |
| Imports but solutions visible to students | `--render-mode exercise` selected the exercise.html layout | Re-render without the flag (default is `assignment`) |
| Imports but multi-select grades wrong combination | `Multiple Selection` with single-index answer like `"2"` instead of `Non Permuting Multiple Choice` with integer `answer: 2` | Switch mode. Precheck flags single-index Multiple Selection. |
| Renders but Maple part missing the input-symbol palette | `input_symbols` placed inside `responses[i]` instead of at part level | Move to part level. Precheck flags this. |

Add new rows here when new failure modes are discovered, and add the
corresponding test in `tests/test_precheck.py` when the rule is
mechanically enforceable.

## Tools you have

- `python precheck.py <sheet>` — the regression guard for known patterns.
- `python preview_html.py <sheet>` — local preview to inspect rendered
  HTML before uploading.
- `tests/fixtures/mobius_exports/RoundTripDemo.zip` — Mobius's actual
  export format; the structural ground truth.
- `tests/fixtures/RoundTrip/` — clean Nobius-side fixture covering all
  response modes; useful as a "does the pipeline still work at all" test.
- `import_mobius.py` — round-trips a Mobius ZIP through Nobius; if it
  parses cleanly the XML is well-formed (does not prove Mobius will
  accept it).

## What "Application Error" usually means

Empirically: a path resolution issue at the manifest layer (most often
URL-encoded spaces in `__BASE_URI__` references). The Mobius importer
rejects the manifest before any per-question processing and surfaces no
diagnostic. The rule set in precheck was built specifically to catch
these, so a clean precheck makes the most likely causes already
impossible.

If precheck is clean, suspect (in order):
1. The render flags (theme + mode).
2. Stale UIDs from a prior partial import (try `--reset-uid` once, then
   re-import with fresh identities).
3. An unusual character in the algorithm string or a question
   `<text>` body that Mobius's XML parser chokes on.
4. A response area shape Mobius doesn't recognise (rare; the test
   fixtures cover all known modes).
