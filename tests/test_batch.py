import subprocess
import sys
import xml.etree.ElementTree as ET

from export_mobius_batch import get_question_timings, get_timings_summary

from .conftest import REPO_ROOT, create_sheet_fixture, load_json, make_config_payload, write_json


def test_get_question_timings_reads_tutorial_fixture(t01_sheet):
    timings = get_question_timings(t01_sheet)

    assert timings["Starter"] == [10, 15]
    assert timings["Total"] == [100, 140]


def test_get_timings_summary_formats_sheet_totals():
    summary = get_timings_summary(
        {
            "t01": {
                "Total": [10, 20],
                "Question A": [3, 4],
                "Question B": [7, 16],
            }
        }
    )

    assert "t01: 10-20 mins total." in summary
    assert "Question A: 3-4 mins." in summary


def test_get_question_timings_skips_questions_without_par_time(tmp_path):
    sheet = create_sheet_fixture(
        tmp_path,
        "timing_sheet",
        {
            "name": "Sheet #1 - Timing Demo",
            "description": "Synthetic timing fixture",
            "questions": ["Timed Question", "Untimed Question"],
            "number": 1,
        },
        [
            {
                "title": "Timed Question",
                "master_statement": "Timed content.",
                "icon_data": {"difficulty": 1, "par_time": [3, 5], "statement": ""},
                "parts": [],
            },
            {
                "title": "Untimed Question",
                "master_statement": "Untimed content.",
                "icon_data": {"difficulty": 1, "statement": ""},
                "parts": [],
            },
        ],
    )

    timings = get_question_timings(sheet)

    assert timings["Timed Question"] == [3, 5]
    assert "Untimed Question" not in timings
    assert timings["Total"] == [3, 5]


def test_generate_all_cli_can_initialize_missing_uids_and_merge_output(tmp_path):
    sheets_root = tmp_path / "sheets"
    output_root = tmp_path / "output"
    sheets_root.mkdir()
    output_root.mkdir()

    create_sheet_fixture(
        sheets_root,
        "batch_sheet",
        {
            "name": "Sheet #1 - Batch Demo",
            "description": "Synthetic batch fixture",
            "questions": ["Batch Question"],
            "number": 1,
        },
        [
                {
                    "title": "Batch Question",
                    "master_statement": "Batch test.",
                    "icon_data": {"difficulty": 1, "par_time": [5, 7], "statement": ""},
                    "parts": [
                        {
                            "statement": "Enter a number.",
                            "response": {"mode": "Numeric", "answer": {"num": 2}},
                    }
                ],
            }
        ],
        media_files={"batch.png": b"batch-media"},
    )

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    subprocess.run(
        [
            sys.executable,
            "export_mobius_batch.py",
            str(sheets_root),
            str(output_root),
            "--config",
            str(config_path),
            "--write-missing-uids",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    sheet_info = load_json(sheets_root / "batch_sheet" / "SheetInfo.json")
    question = load_json(sheets_root / "batch_sheet" / "Batch Question.json")

    assert sheet_info["uid"]
    assert question["uid"]
    assert (output_root / "all_sheets.xml").exists()
    assert (output_root / "all_media.zip").exists()
    assert (output_root / "question_timings.txt").exists()
    merged_root = ET.parse(output_root / "all_sheets.xml").getroot()
    assert merged_root.find("assignmentUnits") is not None
    assert merged_root.find("questions/question") is not None
    assert merged_root.find("assignments") is not None


def test_generate_all_cli_continue_on_error_preserves_successful_sheet_output(tmp_path):
    sheets_root = tmp_path / "sheets"
    output_root = tmp_path / "output"
    sheets_root.mkdir()
    output_root.mkdir()

    create_sheet_fixture(
        sheets_root,
        "good_sheet",
        {
            "name": "Sheet #1 - Good Sheet",
            "description": "Valid batch fixture",
            "questions": ["Good Question"],
            "number": 1,
            "uid": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        },
        [
                {
                    "title": "Good Question",
                    "master_statement": "Valid content.",
                    "icon_data": {"difficulty": 1, "par_time": [4, 6], "statement": ""},
                    "parts": [
                        {
                            "statement": "Enter a number.",
                            "response": {"mode": "Numeric", "answer": {"num": 3}},
                    }
                ],
                "uid": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            }
        ],
        media_files={"good.png": b"good-media"},
    )

    create_sheet_fixture(
        sheets_root,
        "bad_sheet",
        {
            "name": "Sheet #2 - Bad Sheet",
            "description": "Invalid batch fixture",
            "questions": ["Bad Question"],
            "number": 2,
        },
        [
                {
                    "title": "Bad Question",
                    "master_statement": "Invalid content.",
                    "icon_data": {"difficulty": 1, "par_time": [1, 1], "statement": ""},
                    "parts": [
                        {
                            "statement": "Broken custom response.",
                            "custom_response": {
                            "layout": "<missing>",
                            "responses": {
                                "x": {
                                    "mode": "List",
                                    "choices": ["A"],
                                    "display": {"display": "text", "permute": False},
                                }
                            },
                        },
                    }
                ],
            }
        ],
    )

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    result = subprocess.run(
        [
            sys.executable,
            "export_mobius_batch.py",
            str(sheets_root),
            str(output_root),
            "--config",
            str(config_path),
            "--write-missing-uids",
            "--continue-on-error",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[ERROR] Sheet bad_sheet aborted" in result.stdout
    assert (output_root / "all_sheets.xml").exists()
    assert (output_root / "xml" / "Sheet #1 - Good Sheet.xml").exists()


def test_generate_all_cli_supports_exam_render_profile(tmp_path):
    sheets_root = tmp_path / "sheets"
    output_root = tmp_path / "output"
    sheets_root.mkdir()
    output_root.mkdir()

    create_sheet_fixture(
        sheets_root,
        "exam_sheet",
        {
            "name": "Exam Demo",
            "description": "Synthetic exam-style batch fixture",
            "questions": ["Exam Question"],
            "number": 1,
        },
        [
            {
                "title": "Exam Question",
                "master_statement": "Exam batch test.",
                "icon_data": {"difficulty": 1, "par_time": [6, 8], "statement": ""},
                "parts": [
                    {
                        "statement": "Enter a number.",
                        "response": {"mode": "Numeric", "answer": {"num": 5}},
                    }
                ],
            }
        ],
        media_files={"exam.png": b"exam-media"},
    )

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    subprocess.run(
        [
            sys.executable,
            "export_mobius_batch.py",
            str(sheets_root),
            str(output_root),
            "--config",
            str(config_path),
            "--profile",
            "exam",
            "--write-missing-uids",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    rendered_xml = (output_root / "xml" / "Exam Demo.xml").read_text(encoding="utf-8")

    assert "<![CDATA[ Exam Demo ]]>" in rendered_xml
    assert (output_root / "all_sheets.xml").exists()
    assert (output_root / "all_media.zip").exists()


def test_generate_all_cli_fails_cleanly_when_no_sheet_xmls_are_produced(tmp_path):
    sheets_root = tmp_path / "empty_sheets"
    output_root = tmp_path / "output"
    sheets_root.mkdir()
    output_root.mkdir()

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    result = subprocess.run(
        [
            sys.executable,
            "export_mobius_batch.py",
            str(sheets_root),
            str(output_root),
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "No rendered sheet XML files were produced" in result.stdout
    assert not (output_root / "all_sheets.xml").exists()
    assert not (output_root / "all_media.zip").exists()


def test_generate_all_cli_all_failed_continue_on_error_exits_cleanly(tmp_path):
    sheets_root = tmp_path / "sheets"
    output_root = tmp_path / "output"
    sheets_root.mkdir()
    output_root.mkdir()

    create_sheet_fixture(
        sheets_root,
        "bad_sheet",
        {
            "name": "Sheet #1 - Bad Sheet",
            "description": "Invalid batch fixture",
            "questions": ["Bad Question"],
            "number": 1,
        },
        [
            {
                "title": "Bad Question",
                "master_statement": "Invalid content.",
                "icon_data": {"difficulty": 1, "par_time": [1, 1], "statement": ""},
                "parts": [
                    {
                        "statement": "Broken custom response.",
                        "custom_response": {
                            "layout": "<missing>",
                            "responses": {
                                "x": {
                                    "mode": "List",
                                    "choices": ["A"],
                                    "display": {"display": "text", "permute": False},
                                }
                            },
                        },
                    }
                ],
            }
        ],
    )

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    result = subprocess.run(
        [
            sys.executable,
            "export_mobius_batch.py",
            str(sheets_root),
            str(output_root),
            "--config",
            str(config_path),
            "--continue-on-error",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "[ERROR] Sheet bad_sheet aborted" in result.stdout
    assert "No rendered sheet XML files were produced" in result.stdout
    assert not (output_root / "all_sheets.xml").exists()
