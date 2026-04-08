from generateJSON import gather_media_references, generate_json_file, resolve_manifest_path, safe_question_basename
from render_common import render_sheet
from xml_scraper.get_xml_data import normalize_response

from .conftest import (
    REPO_ROOT,
    custom_response_placeholders,
    load_json,
    load_question_by_title,
    make_render_settings,
    rendered_question_titles,
)


def test_resolve_manifest_path_detects_xml_source(experimental_xml_path):
    source_info = resolve_manifest_path(str(experimental_xml_path))

    assert source_info["source_type"] == "xml"
    assert source_info["manifest_path"] == str(experimental_xml_path)
    assert source_info["media_root"] is None


def test_resolve_manifest_path_detects_zip_source(t01_sheet):
    render_result = render_sheet(t01_sheet, "master.xml", make_render_settings())

    source_info = resolve_manifest_path(render_result["zip_path"])

    assert source_info["source_type"] == "zip"
    assert source_info["manifest_path"] == "manifest.xml"
    assert source_info["zip_path"] == render_result["zip_path"]


def test_gather_media_references_walks_nested_question_data():
    node = {
        "media": ["a.png"],
        "parts": [
            {"media": ["b.png"]},
            {"worked_solutions": [{"media": ["c.png"]}]},
        ],
    }

    assert gather_media_references(node) == {"a.png", "b.png", "c.png"}


def test_generate_json_from_standard_zip_writes_expected_outputs(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master.xml", make_render_settings())
    destination = tmp_path / "imported-standard"

    report = generate_json_file(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    assert (destination / "SheetInfo.json").exists()
    assert (destination / "import_report.json").exists()
    assert (destination / "import_report.txt").exists()
    assert (destination / "media" / "TruncatedCone.png").exists()
    assert report.source_type == "zip"
    assert len(report.copied_media) >= 1


def test_generate_json_strip_uids_removes_sheet_and_question_uids(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master.xml", make_render_settings())
    destination = tmp_path / "imported-no-uid"

    generate_json_file(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    sheet_info = load_json(destination / "SheetInfo.json")
    question = load_json(destination / "Fluids.json")

    assert "uid" not in sheet_info
    assert "uid" not in question


def test_standard_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master.xml", make_render_settings())
    imported = tmp_path / "roundtrip-standard"

    generate_json_file(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "master.xml", make_render_settings())
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["xml_path"].endswith("Fundamentals.xml")
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_exam_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master_exam.xml", make_render_settings(exam=True))
    imported = tmp_path / "roundtrip-exam"

    generate_json_file(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "master_exam.xml", make_render_settings(exam=True))
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_t01_round_trip_preserves_custom_response_shape(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master.xml", make_render_settings())
    imported = tmp_path / "roundtrip-custom"

    generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Volume and Mass of Truncated Cone")
    custom_response = question["parts"][0]["custom_response"]

    assert len(custom_response_placeholders(custom_response["layout"])) == 4
    assert len(custom_response["responses"]) == 4
    assert all(response["mode"] == "List" for response in custom_response["responses"])


def test_t02_round_trip_preserves_algorithmic_question_content(t02_sheet, tmp_path):
    render_result = render_sheet(t02_sheet, "master.xml", make_render_settings())
    imported = tmp_path / "roundtrip-t02"

    generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Hydraulic Press")

    assert "algorithm" in question
    assert "$f=range(100,300,1)" in question["algorithm"]
    assert question["parts"][0]["response"]["mode"] == "Numeric"


def test_import_report_for_exam_style_round_trip_records_warning_for_nonstandard_name(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "master_exam.xml", make_render_settings(exam=True))
    imported = tmp_path / "roundtrip-report"

    report = generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))

    assert any("Sheet name did not match" in warning["message"] for warning in report.warnings)


def test_normalize_response_wraps_legacy_list_display_string():
    response = {"mode": "List", "display": "text"}

    normalized = normalize_response(response)

    assert normalized["display"] == {"display": "text", "permute": False}


def test_safe_question_basename_sanitizes_invalid_filename_characters():
    used_names = set()

    basename = safe_question_basename('Question: 1 / "Test"?', used_names)

    assert basename == "Question 1 Test"


def test_generate_json_sanitizes_duplicate_or_invalid_question_filenames(tmp_path):
    group = {
        "info": {
            "name": "Imported Sheet",
            "description": "",
            "number": 1,
            "uid": "sheet-uid",
            "questions": []
        },
        "questions": [
            {"title": 'A/B', "parts": [], "uid": "1"},
            {"title": 'A:B', "parts": [], "uid": "2"},
            {"title": '', "parts": [], "uid": "3"},
        ]
    }

    from generateJSON import write_group_json

    outputs = write_group_json(group, tmp_path)
    basenames = load_json(tmp_path / "SheetInfo.json")["questions"]

    assert basenames == ["AB", "AB (2)", "Question"]
    assert (tmp_path / "AB.json").exists()
    assert (tmp_path / "AB (2).json").exists()
    assert (tmp_path / "Question.json").exists()
    assert len(outputs) == 4


def test_safe_question_basename_handles_case_insensitive_windows_collisions():
    used_names = set()

    first = safe_question_basename("Question", used_names)
    second = safe_question_basename("question", used_names)
    third = safe_question_basename("QUESTION", used_names)

    assert first == "Question"
    assert second == "question (2)"
    assert third == "QUESTION (3)"
