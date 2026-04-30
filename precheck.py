"""Pre-export sanity checks for Nobius sheet directories.

Catches gotchas that are not naturally enforced by per-file JSON schema validation:
filename whitespace, the cross-file requirement that a sheet with media must declare
``media_folder`` in ``SheetInfo.json``, response-area shape errors that the schema
allows but Mobius rejects on import, and similar failure modes.

Usage:

* ``python precheck.py <sheet folder>`` -- standalone CLI; exits 0 on pass, 1 on failure.
* ``from precheck import check_sheet`` -- programmatic; returns ``list[Issue]``.

The ``export_mobius.py``, ``export_mobius_batch.py``, ``export_pdf.py`` and
``preview_html.py`` entry points call ``check_sheet`` before rendering and abort
the run on any error-level issue.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    """A single precheck finding.

    ``severity`` is ``"error"`` (blocks export) or ``"warning"`` (informational).
    ``location`` is a human-readable path into the sheet, e.g. ``"SheetInfo.json"``
    or ``"Question1.json -> parts[2].media[0]"``.
    """

    severity: str
    location: str
    message: str


def _load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _has_whitespace(value):
    return isinstance(value, str) and any(ch.isspace() for ch in value)


def _walk_question_media(question):
    """Yield ``(location_suffix, filename)`` pairs for every media reference in a question."""
    for index, item in enumerate(question.get("media") or []):
        yield f"media[{index}]", item
    for part_index, part in enumerate(question.get("parts") or []):
        if not isinstance(part, dict):
            continue
        for index, item in enumerate(part.get("media") or []):
            yield f"parts[{part_index}].media[{index}]", item


def _check_media_filenames(sheet_dir, sheet_info, questions):
    """Filenames in question/part media[] must:

    1. contain no whitespace -- Mobius URL-encodes the path and rejects ``%20``
       segments inside ``__BASE_URI__`` references with a generic "Application
       Error";
    2. exist in the sheet's ``media/`` directory -- a stale reference renders as
       a broken image in Mobius and the inconsistency only surfaces on inspection.
    """
    issues = []
    sheet_has_media = False
    media_dir = os.path.join(sheet_dir, "media")
    if os.path.isdir(media_dir):
        present_files = set(os.listdir(media_dir))
    else:
        present_files = set()

    for question_name, question in questions.items():
        for location_suffix, filename in _walk_question_media(question):
            sheet_has_media = True
            location = f"{question_name}.json -> {location_suffix}"
            if _has_whitespace(filename):
                issues.append(
                    Issue(
                        severity="error",
                        location=location,
                        message=(
                            f"Media filename '{filename}' contains whitespace. "
                            "Mobius rejects URL-encoded spaces in __BASE_URI__ paths -- rename the file."
                        ),
                    )
                )
            if filename not in present_files:
                issues.append(
                    Issue(
                        severity="error",
                        location=location,
                        message=(
                            f"Referenced figure '{filename}' is not present in the sheet's media/ directory. "
                            "Either add the file or remove the reference."
                        ),
                    )
                )
    return issues, sheet_has_media


def _check_media_folder_required(sheet_info, sheet_has_media):
    """If any question references media, ``SheetInfo.media_folder`` must be set explicitly.

    Without it the renderer falls back to the sheet name, which typically contains
    spaces and produces an unimportable manifest.
    """
    if not sheet_has_media:
        return []
    if sheet_info.get("media_folder"):
        return []
    return [
        Issue(
            severity="error",
            location="SheetInfo.json",
            message=(
                "Sheet contains media references but 'media_folder' is not set. "
                "The default falls back to the (usually spaced) sheet name, which Mobius rejects. "
                "Add an explicit no-whitespace 'media_folder' value."
            ),
        )
    ]


def _check_input_symbols_placement(questions):
    """``input_symbols`` belongs at the part level, not inside ``responses[i]``.

    The renderer silently ignores it in the wrong place, which produced an exam
    with no input-symbol tables on import. The schema's ``additionalProperties:
    false`` on ``responses[i]`` items now catches this, but we double-check here
    so the failure message is specific instead of a generic schema error.
    """
    issues = []
    for question_name, question in questions.items():
        for part_index, part in enumerate(question.get("parts") or []):
            if not isinstance(part, dict):
                continue
            for response_index, sub in enumerate(part.get("responses") or []):
                if isinstance(sub, dict) and "input_symbols" in sub:
                    issues.append(
                        Issue(
                            severity="error",
                            location=f"{question_name}.json -> parts[{part_index}].responses[{response_index}].input_symbols",
                            message=(
                                "'input_symbols' must be at the part level (sibling of 'responses'), "
                                "not inside an individual response. The renderer ignores it here."
                            ),
                        )
                    )
    return issues


_LONG_INLINE_DISPLAY_HINTS = re.compile(r"\\(?:dfrac|sum|int|begin\{|left)")
_INLINE_MATH_RE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)
_TILDE_NBSP_RE = re.compile(r"\b\w+~\w")
_TEX_ACCENT_RE = re.compile(r"\\'[a-zA-Z]|\\`[a-zA-Z]|\\\^[a-zA-Z]|\\\"[a-zA-Z]")
_TEX_ENV_RE = re.compile(r"\\(?:begin|end)\{(?:equation|align|cases|gather|eqnarray)\*?\}")
_ADDPOINTS_RE = re.compile(r"\\addpoints\b")


def _walk_question_text(question):
    """Yield ``(location_suffix, text)`` for every authored text field worth scanning.

    Covers ``master_statement``, every part's ``statement``, and per-response
    ``pre_response_text``/``post_response_text``. Skips the algorithm string
    (which is Maple syntax and legitimately uses TeX-shaped tokens).
    """
    if isinstance(question.get("master_statement"), str):
        yield "master_statement", question["master_statement"]
    for part_index, part in enumerate(question.get("parts") or []):
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("statement"), str):
            yield f"parts[{part_index}].statement", part["statement"]
        for key in ("pre_response_text", "post_response_text"):
            if isinstance(part.get(key), str):
                yield f"parts[{part_index}].{key}", part[key]
        for response_index, sub in enumerate(part.get("responses") or []):
            if not isinstance(sub, dict):
                continue
            for key in ("pre_response_text", "post_response_text"):
                if isinstance(sub.get(key), str):
                    yield f"parts[{part_index}].responses[{response_index}].{key}", sub[key]


def _check_latex_remnants(questions):
    """Surface authoring patterns that likely don't render correctly in MathJax/HTML.

    These are *warnings* -- legitimate uses exist (especially for inline math
    that genuinely belongs inline). Authors should review each finding rather
    than mechanically fix it.
    """
    issues = []
    for question_name, question in questions.items():
        for location_suffix, text in _walk_question_text(question):
            location = f"{question_name}.json -> {location_suffix}"

            # Long inline equation (\(...\)) that almost certainly wants to be display (\[...\]).
            for match in _INLINE_MATH_RE.finditer(text):
                eq = match.group(1)
                if len(eq) > 80 and _LONG_INLINE_DISPLAY_HINTS.search(eq):
                    issues.append(
                        Issue(
                            severity="warning",
                            location=location,
                            message=(
                                "Long inline equation "
                                f"\\({eq.strip()[:80]}...\\) -- consider \\[ ... \\] for display."
                            ),
                        )
                    )

            # TeX non-breaking space between words (e.g. "Tank~X") -- renders as a literal '~'.
            if _TILDE_NBSP_RE.search(text):
                issues.append(
                    Issue(
                        severity="warning",
                        location=location,
                        message="TeX-style non-breaking space (~) renders as a literal '~' in HTML. Replace with a regular space.",
                    )
                )

            # TeX accent escapes (\'e, \`e, \^e, \"e) -- don't render in MathJax/HTML.
            if _TEX_ACCENT_RE.search(text):
                issues.append(
                    Issue(
                        severity="warning",
                        location=location,
                        message="TeX-style accent escape (e.g. \\'e) does not render. Use Unicode characters (é, è, ê, ï) directly.",
                    )
                )

            # LaTeX equation environments -- MathJax accepts these but the renderer often produces inline output.
            if _TEX_ENV_RE.search(text):
                issues.append(
                    Issue(
                        severity="warning",
                        location=location,
                        message="LaTeX equation environment (\\begin{equation}, \\begin{align}, ...) found. Convert to \\[ ... \\] for reliable display rendering.",
                    )
                )

            # \addpoints{N} -- TeX ExSheets only.
            if _ADDPOINTS_RE.search(text):
                issues.append(
                    Issue(
                        severity="warning",
                        location=location,
                        message="\\addpoints is a TeX-only ExSheets command. Use 'post_response_text': '[N MARKS]' instead.",
                    )
                )
    return issues


def _check_multiple_selection_answer(questions):
    """``Multiple Selection`` answers should be a comma-separated list of indices.

    A single-index string like ``"2"`` produces a manifest the Mobius importer
    rejects -- use ``Non Permuting Multiple Choice`` for genuinely single-answer questions.
    """
    issues = []
    for question_name, question in questions.items():
        for part_index, part in enumerate(question.get("parts") or []):
            if not isinstance(part, dict):
                continue
            response = part.get("response")
            if isinstance(response, dict) and response.get("mode") == "Multiple Selection":
                answer = response.get("answer", "")
                if isinstance(answer, str) and "," not in answer and answer.strip():
                    issues.append(
                        Issue(
                            severity="error",
                            location=f"{question_name}.json -> parts[{part_index}].response.answer",
                            message=(
                                f"'Multiple Selection' with single-index answer '{answer}'. "
                                "Use 'Non Permuting Multiple Choice' (with integer answer) "
                                "for genuinely single-answer questions."
                            ),
                        )
                    )
    return issues


def check_sheet(sheet_dir):
    """Run all precheck rules against a sheet directory. Returns ``list[Issue]``."""
    sheet_dir = os.fspath(sheet_dir)
    sheet_info_path = os.path.join(sheet_dir, "SheetInfo.json")
    if not os.path.isfile(sheet_info_path):
        return [
            Issue(
                severity="error",
                location=sheet_dir,
                message=f"SheetInfo.json not found in {sheet_dir}",
            )
        ]

    issues = []
    sheet_info = _load_json(sheet_info_path)

    # Load all questions referenced from SheetInfo.json
    questions = {}
    for question_name in sheet_info.get("questions", []):
        question_path = os.path.join(sheet_dir, f"{question_name}.json")
        if not os.path.isfile(question_path):
            issues.append(
                Issue(
                    severity="error",
                    location="SheetInfo.json",
                    message=f"Listed question '{question_name}' has no matching {question_name}.json file.",
                )
            )
            continue
        questions[question_name] = _load_json(question_path)

    media_issues, sheet_has_media = _check_media_filenames(sheet_dir, sheet_info, questions)
    issues.extend(media_issues)
    issues.extend(_check_media_folder_required(sheet_info, sheet_has_media))
    issues.extend(_check_input_symbols_placement(questions))
    issues.extend(_check_multiple_selection_answer(questions))
    issues.extend(_check_latex_remnants(questions))

    return issues


def report(issues, stream=None):
    """Print issues in a human-readable format. Returns the count of error-level issues."""
    stream = stream or sys.stderr
    error_count = 0
    for issue in issues:
        if issue.severity == "error":
            error_count += 1
        prefix = "ERROR" if issue.severity == "error" else "WARN"
        stream.write(f"[{prefix}] {issue.location}: {issue.message}\n")
    return error_count


def run(sheet_dir, stream=None):
    """Run precheck and write a report. Returns the count of error-level issues."""
    issues = check_sheet(sheet_dir)
    return report(issues, stream)


def main():
    parser = argparse.ArgumentParser(
        description="Run precheck rules against a Nobius sheet directory."
    )
    parser.add_argument("filepath", help="Path to the sheet directory.")
    args = parser.parse_args()

    error_count = run(args.filepath)
    if error_count:
        sys.stderr.write(f"\nprecheck failed with {error_count} error(s).\n")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
