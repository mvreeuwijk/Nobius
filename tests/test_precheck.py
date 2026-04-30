"""Tests for ``precheck.check_sheet`` -- one per gotcha catalogued during the
2026-04-30 Mobius import debugging session. Each test takes a known-good sheet
fixture, mutates it to introduce exactly one gotcha, and asserts that ``check_sheet``
flags an error with a useful location.

Add a new test here whenever a new failure mode is identified -- this file is
the canonical inventory of what we know to break Mobius import.
"""

import json
import shutil

import pytest

from precheck import Issue, check_sheet


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def good_sheet_with_media(tmp_path):
    """A minimal sheet that should pass all precheck rules.

    Uses ``media_folder: "GoodSheet"`` and a single image filename without
    whitespace, so every check is satisfied. Tests then mutate this fixture
    in-place to introduce one gotcha at a time.
    """
    sheet_dir = tmp_path / "GoodSheet"
    sheet_dir.mkdir()
    (sheet_dir / "media").mkdir()
    (sheet_dir / "media" / "diagram.png").write_bytes(b"png-bytes")
    _write_json(
        sheet_dir / "SheetInfo.json",
        {
            "name": "Good Sheet",
            "number": 1,
            "description": "",
            "questions": ["Question1"],
            "uid": "11111111-1111-1111-1111-111111111111",
            "media_folder": "GoodSheet",
        },
    )
    _write_json(
        sheet_dir / "Question1.json",
        {
            "title": "Question1",
            "uid": "22222222-2222-2222-2222-222222222222",
            "master_statement": "Question 1",
            "media": ["diagram.png"],
            "parts": [
                {
                    "statement": "Pick one",
                    "response": {
                        "mode": "Non Permuting Multiple Choice",
                        "answer": 1,
                        "choices": ["a", "b"],
                    },
                }
            ],
        },
    )
    return sheet_dir


def test_clean_sheet_passes(good_sheet_with_media):
    issues = check_sheet(good_sheet_with_media)
    assert issues == []


def test_missing_sheet_info_is_error(tmp_path):
    sheet_dir = tmp_path / "Empty"
    sheet_dir.mkdir()
    issues = check_sheet(sheet_dir)
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert "SheetInfo.json not found" in issues[0].message


def test_listed_question_missing_file_is_error(good_sheet_with_media):
    info = _read_json(good_sheet_with_media / "SheetInfo.json")
    info["questions"].append("DoesNotExist")
    _write_json(good_sheet_with_media / "SheetInfo.json", info)

    issues = check_sheet(good_sheet_with_media)
    assert any("DoesNotExist" in i.message for i in issues)


def test_question_media_filename_with_space_is_error(good_sheet_with_media):
    """Spaces in question.media[] filenames produce ``%20`` in the rendered
    ``__BASE_URI__`` path; Mobius rejects that with a generic Application Error.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["media"] = ["bad name.png"]
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("'bad name.png'" in m and "whitespace" in m for m in error_messages)


def test_part_media_filename_with_space_is_error(good_sheet_with_media):
    """Same rule applies to part-level media."""
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0]["media"] = ["another bad.jpg"]
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("'another bad.jpg'" in m for m in error_messages)


def test_referenced_figure_missing_from_media_dir_is_error(good_sheet_with_media):
    """A media[] reference that has no matching file in media/ is a stale reference --
    renders as a broken image in Mobius. Catch it locally.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["media"] = ["does_not_exist.png"]
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("'does_not_exist.png'" in m and "not present" in m for m in error_messages)


def test_referenced_part_figure_missing_from_media_dir_is_error(good_sheet_with_media):
    """Same rule for part-level media."""
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0]["media"] = ["never_drawn.jpg"]
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("'never_drawn.jpg'" in m and "not present" in m for m in error_messages)


def test_media_folder_required_when_sheet_has_media(good_sheet_with_media):
    """If any question references media, ``SheetInfo.media_folder`` must be set
    explicitly. The renderer's default falls back to the sheet name (typically
    spaced), producing the same %20 import failure.
    """
    info = _read_json(good_sheet_with_media / "SheetInfo.json")
    del info["media_folder"]
    _write_json(good_sheet_with_media / "SheetInfo.json", info)

    issues = check_sheet(good_sheet_with_media)
    assert any(
        i.severity == "error" and "media_folder" in i.message
        for i in issues
    )


def test_media_folder_not_required_when_sheet_has_no_media(tmp_path):
    """A sheet with no figures does not need ``media_folder`` -- precheck must
    not surface a false positive.
    """
    sheet_dir = tmp_path / "TextOnly"
    sheet_dir.mkdir()
    _write_json(
        sheet_dir / "SheetInfo.json",
        {
            "name": "Text Only",
            "number": 1,
            "description": "",
            "questions": ["Question1"],
            "uid": "11111111-1111-1111-1111-111111111111",
        },
    )
    _write_json(
        sheet_dir / "Question1.json",
        {
            "title": "Question1",
            "uid": "22222222-2222-2222-2222-222222222222",
            "master_statement": "What is 1+1?",
            "parts": [
                {
                    "statement": "Answer",
                    "response": {
                        "mode": "Numeric",
                        "answer": {"num": "2", "units": ""},
                        "showUnits": False,
                    },
                }
            ],
        },
    )
    assert check_sheet(sheet_dir) == []


def test_input_symbols_misplaced_inside_responses_is_error(good_sheet_with_media):
    """``input_symbols`` belongs at the part level. Inside ``responses[i]`` it
    is silently ignored by the renderer, which produced the missing-input-symbols
    bug encountered during the 2026-04-30 chase.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0] = {
        "statement": "Algebra",
        "responses": [
            {
                "pre_response_text": "x = ",
                "response": {
                    "mode": "Maple",
                    "mapleAnswer": "y+1",
                    "maple": "Nobius:-GradePat($ANSWER, $RESPONSE);",
                },
                "input_symbols": [["y", "y"]],  # WRONG -- belongs at part level
            }
        ],
    }
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("input_symbols" in m and "part level" in m for m in error_messages)


def test_multiple_selection_with_single_index_answer_is_error(good_sheet_with_media):
    """``Multiple Selection`` with a single-index answer string is the wrong
    response mode -- a genuinely single-answer question should use
    ``Non Permuting Multiple Choice`` with an integer answer.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0]["response"] = {
        "mode": "Multiple Selection",
        "answer": "2",
        "choices": ["a", "b", "c"],
    }
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    error_messages = [i.message for i in issues if i.severity == "error"]
    assert any("Multiple Selection" in m and "single-index" in m for m in error_messages)


def test_multiple_selection_with_comma_separated_answer_is_ok(good_sheet_with_media):
    """A genuine multi-select with two or more correct indices must not be flagged."""
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0]["response"] = {
        "mode": "Multiple Selection",
        "answer": "1,3",
        "choices": ["a", "b", "c"],
    }
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    assert all(
        not (i.severity == "error" and "Multiple Selection" in i.message)
        for i in issues
    )


def test_long_inline_equation_emits_warning(good_sheet_with_media):
    """Long inline math (\\(...\\) over ~80 chars with display-only commands) is
    almost always meant for display. Surface it as a warning so authors can
    review -- non-blocking because legitimate inline complex math exists.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    long_eq = "\\(t_e = \\dfrac{2\\pi\\sqrt{H}}{A_0\\sqrt{2g}}\\left(r_b^2 + \\frac{2}{3}r_b(r_t-r_b) + \\frac{1}{5}(r_t-r_b)^2\\right). \\)"
    q["master_statement"] = "The emptying time is " + long_eq + " for the tank."
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("Long inline equation" in w.message and "consider \\[" in w.message for w in warnings)
    # Must not be an error (non-blocking).
    assert all("Long inline equation" not in i.message for i in issues if i.severity == "error")


def test_tex_nbsp_emits_warning(good_sheet_with_media):
    """``Tank~X`` (TeX non-breaking space between words) renders as literal '~'.

    Warning rather than error because '~' inside math (\\(\\sim\\) etc.) is fine.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["master_statement"] = "Tank~X drains faster than Tank~Y."
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("non-breaking space" in w.message for w in warnings)


def test_tex_accent_emits_warning(good_sheet_with_media):
    """TeX accent escapes (\\'e, \\`e, \\^e, \\"e) render as literal text in HTML."""
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["master_statement"] = "Use the Ch\\'ezy coefficient \\(C\\)."
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("accent escape" in w.message and "Unicode" in w.message for w in warnings)


def test_addpoints_emits_warning(good_sheet_with_media):
    """``\\addpoints{N}`` is the TeX ExSheets points-tracking command and has no
    meaning in Mobius; the convention here is ``post_response_text: "[N MARKS]"``.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["parts"][0]["statement"] = "Compute the answer. (\\addpoints{5})"
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("\\addpoints" in w.message and "post_response_text" in w.message for w in warnings)


def test_latex_equation_environment_emits_warning(good_sheet_with_media):
    """LaTeX equation environments occasionally render but the convention is to use
    ``\\[ ... \\]`` for display math.
    """
    q = _read_json(good_sheet_with_media / "Question1.json")
    q["master_statement"] = "Solve \\begin{equation} x = 1 \\end{equation}"
    _write_json(good_sheet_with_media / "Question1.json", q)

    issues = check_sheet(good_sheet_with_media)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("LaTeX equation environment" in w.message for w in warnings)


def test_warnings_do_not_fail_precheck(good_sheet_with_media):
    """Warnings are reported but ``run`` should return 0 errors (exit 0) so that
    legacy authoring patterns don't block the export.
    """
    from precheck import run
    import io

    q = _read_json(good_sheet_with_media / "Question1.json")
    q["master_statement"] = "Tank~X. Use the Ch\\'ezy coefficient."
    _write_json(good_sheet_with_media / "Question1.json", q)

    error_count = run(good_sheet_with_media, stream=io.StringIO())
    assert error_count == 0


def test_round_trip_fixture_passes(tmp_path):
    """The shipped ``tests/fixtures/RoundTrip`` sheet must satisfy precheck --
    it is the canonical clean reference and a regression here would mean the
    rule set is too aggressive.
    """
    from tests.conftest import REPO_ROOT

    src = REPO_ROOT / "tests" / "fixtures" / "RoundTrip"
    dst = tmp_path / "RoundTrip"
    shutil.copytree(src, dst)
    issues = check_sheet(dst)
    error_messages = [f"{i.location}: {i.message}" for i in issues if i.severity == "error"]
    assert error_messages == [], "unexpected precheck errors:\n  " + "\n  ".join(error_messages)
