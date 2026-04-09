import json
import re
import subprocess
import sys
import zipfile

import bs4
import pytest

from render_common import NobiusRenderError, load_json_file, make_matrix, process_custom_response, render_sheet

from .conftest import (
    REPO_ROOT,
    load_question_by_title,
    make_config_payload,
    make_render_settings,
    write_json,
)


def canonicalize_export_xml(xml_text):
    xml_text = xml_text.replace("\r\n", "\n")
    return re.sub(
        r"-?\d+\.\d{13,}",
        lambda match: format(round(float(match.group(0)), 12), ".12f").rstrip("0").rstrip("."),
        xml_text,
    )


def test_render_sheet_standard_creates_xml_and_zip_for_tutorial_fixture(t01_sheet):
    result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())

    assert result["xml_path"].endswith("Fundamentals.xml")
    assert result["zip_path"].endswith("Fundamentals.zip")


def test_render_sheet_exam_creates_xml_and_zip_for_tutorial_fixture(t01_sheet):
    result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(exam=True))

    assert result["xml_path"].endswith("Fundamentals.xml")
    assert result["zip_path"].endswith("Fundamentals.zip")


def test_exam_render_includes_feedback_separator_and_script_spacing(t01_sheet):
    render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(exam=True))
    rendered_xml = (t01_sheet / "renders" / "Fundamentals.xml").read_text(encoding="utf-8")
    soup = bs4.BeautifulSoup(rendered_xml, "lxml-xml")
    first_question_text = soup.find("courseModule", recursive=False).find("questions", recursive=False).find("question", recursive=False).find("text").string

    assert '<hr id="question-feedback-separator">' in first_question_text
    assert "<p>&nbsp;</p>" in first_question_text
    assert '<p><script src="__BASE_URI__Scripts/QuestionJavaScript.txt" type="application/javascript">' in first_question_text


def test_render_sheet_zip_contains_manifest_and_media(t01_sheet):
    result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())

    with zipfile.ZipFile(result["zip_path"], "r") as zip_file:
        members = set(zip_file.namelist())

    assert "manifest.xml" in members
    assert "web_folders/Scripts/QuestionJavaScript.txt" in members
    assert "web_folders/Fundamentals/TruncatedCone.png" in members


def test_generate_group_cli_uses_config_values_in_standard_template(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload(
        theme_location="/themes/unit-test-standard",
        scripts_location="/web/unit-test/standard.js",
    ))

    subprocess.run(
        [sys.executable, "generateGroup.py", str(t01_sheet), "--config", str(config_path)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    rendered_xml = (t01_sheet / "renders" / "Fundamentals.xml").read_text(encoding="utf-8")

    assert "__BASE_URI__QuestionTheme.css" in rendered_xml
    assert "__BASE_URI__Scripts/QuestionJavaScript.txt" in rendered_xml


def test_generate_group_cli_uses_exam_render_profile_config_values(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload(
        exam_theme_location="/themes/unit-test-exam",
        exam_scripts_location="/web/unit-test/exam.js",
    ))

    subprocess.run(
        [
            sys.executable,
            "generateGroup.py",
            str(t01_sheet),
            "--config",
            str(config_path),
            "--render-profile",
            "exam",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    rendered_xml = (t01_sheet / "renders" / "Fundamentals.xml").read_text(encoding="utf-8")

    assert "__BASE_URI__QuestionTheme.css" in rendered_xml
    assert "__BASE_URI__Scripts/QuestionJavaScript.txt" in rendered_xml


def test_example_export_uses_question_bank_manifest_shape(example_sheet):
    legacy_settings = {
        "theme_location": "/themes/b06b01fb-1810-4bde-bc67-60630d13a866",
        "scripts_location": "/web/Pjohnso000/Public_Html/Scripts/QuestionJavaScript.txt",
    }

    result = render_sheet(example_sheet, "manifests/questionbank.xml", legacy_settings)
    current_xml = (example_sheet / "renders" / "Experimental Sheet V2.xml").read_text(encoding="utf-8")
    soup = bs4.BeautifulSoup(current_xml, "lxml-xml")
    root = soup.find_all(recursive=False)[0]

    assert result["xml_path"].endswith("Experimental Sheet V2.xml")
    assert root.name == "courseModule"
    assert soup.find("module") is not None
    assert soup.find("module").find("uri") is not None
    root_question_groups = soup.find("courseModule", recursive=False).find("questionGroups", recursive=False)
    assert root_question_groups is not None
    assert root_question_groups.find("group") is not None
    assert root_question_groups.find("qRef") is not None
    assert soup.find("authors") is not None
    assert soup.find("schools") is not None
    assert soup.find("assignmentUnits") is None
    assert soup.find("assignments") is None
    assert soup.find("webResources") is not None
    assert soup.find("webResources").find("uri").text.strip() == "web_folders/Scripts"
    questions = soup.find("courseModule", recursive=False).find("questions", recursive=False)
    assert questions is not None
    first_question = questions.find("question", recursive=False)
    assert first_question.get("language") == "en"
    assert first_question.find("chainId") is not None
    assert first_question.find("numberOfAttempts") is not None
    assert first_question.find("numberOfAttemptsLeft") is not None
    assert first_question.find("numberOfTryAnother") is not None
    assert first_question.find("numberOfTryAnotherLeft") is not None
    assert first_question.find("width") is not None


def test_default_export_uses_assignment_manifest_shape(example_sheet):
    result = render_sheet(example_sheet, "manifests/assignment.xml", make_render_settings())
    current_xml = (example_sheet / "renders" / "Experimental Sheet V2.xml").read_text(encoding="utf-8")
    soup = bs4.BeautifulSoup(current_xml, "lxml-xml")
    root = soup.find_all(recursive=False)[0]

    assert result["xml_path"].endswith("Experimental Sheet V2.xml")
    assert root.name == "courseModule"
    assert soup.find("assignmentUnits") is not None
    assert soup.find("assignments") is not None
    assert soup.find("webResources") is not None
    assert soup.find("questionGroups", recursive=False) is None


def test_make_matrix_numeric_expands_into_scalar_numeric_responses():
    params = {
        "mode": "Matrix Numeric",
        "answer": [[1, 2], [3, 4]],
        "showUnits": True,
    }

    data, responses = make_matrix(params, 7)

    assert data == [[7, 8], [9, 10]]
    assert len(responses) == 4
    assert all(response["mode"] == "Numeric" for response in responses)
    assert all(response["showUnits"] is False for response in responses)
    assert [response["answer"]["num"] for response in responses] == [1, 2, 3, 4]


def test_make_matrix_maple_expands_into_scalar_maple_responses():
    params = {
        "mode": "Matrix Maple",
        "mapleAnswer": [["a", "b"], ["c", "d"]],
    }

    data, responses = make_matrix(params, 3)

    assert data == [[3, 4], [5, 6]]
    assert len(responses) == 4
    assert all(response["mode"] == "Maple" for response in responses)
    assert [response["mapleAnswer"] for response in responses] == ["a", "b", "c", "d"]


def test_process_custom_response_rewrites_list_placeholders(t01_sheet):
    question = load_question_by_title(t01_sheet, "Volume02")
    part = question["parts"][0]
    response_schema = load_json_file(REPO_ROOT / "validation" / "schemas" / "response_areas.json")
    response_defaults = load_json_file(REPO_ROOT / "validation" / "defaults" / "response_areas.json")

    responses, next_identifier, is_maple = process_custom_response(
        10,
        part,
        question["title"],
        0,
        response_schema,
        response_defaults,
    )

    assert next_identifier == 14
    assert is_maple == 0
    assert "<10>" in part["custom_response"]
    assert "<13>" in part["custom_response"]
    assert len(responses) == 4
    assert all(response["mode"] == "List" for response in responses)


def test_render_refuses_missing_uids_by_default(t01_sheet):
    sheet_info_path = t01_sheet / "SheetInfo.json"
    question_path = t01_sheet / "Starter.json"

    sheet_info = load_json_file(sheet_info_path)
    question = load_json_file(question_path)
    del sheet_info["uid"]
    del question["uid"]

    with open(sheet_info_path, "w", encoding="utf-8") as file:
        json.dump(sheet_info, file, indent=2)
    with open(question_path, "w", encoding="utf-8") as file:
        json.dump(question, file, indent=2)

    with pytest.raises(NobiusRenderError, match="--write-missing-uids"):
        render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())


def test_render_can_persist_missing_uids_when_explicitly_requested(t01_sheet):
    sheet_info_path = t01_sheet / "SheetInfo.json"
    question_path = t01_sheet / "Starter.json"

    sheet_info = load_json_file(sheet_info_path)
    question = load_json_file(question_path)
    del sheet_info["uid"]
    del question["uid"]

    with open(sheet_info_path, "w", encoding="utf-8") as file:
        json.dump(sheet_info, file, indent=2)
    with open(question_path, "w", encoding="utf-8") as file:
        json.dump(question, file, indent=2)

    render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(), write_missing_uids=True)

    assert load_json_file(sheet_info_path)["uid"]
    assert load_json_file(question_path)["uid"]


def test_generate_group_cli_can_write_missing_uids(t01_sheet, tmp_path):
    sheet_info_path = t01_sheet / "SheetInfo.json"
    sheet_info = load_json_file(sheet_info_path)
    del sheet_info["uid"]
    with open(sheet_info_path, "w", encoding="utf-8") as file:
        json.dump(sheet_info, file, indent=2)

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload(
        theme_location="/themes/unit-test-standard",
        scripts_location="/web/unit-test/standard.js",
    ))

    subprocess.run(
        [
            sys.executable,
            "generateGroup.py",
            str(t01_sheet),
            "--config",
            str(config_path),
            "--write-missing-uids",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert load_json_file(sheet_info_path)["uid"]


def test_generate_group_cli_reset_uid_rewrites_existing_source_uids(t01_sheet, tmp_path):
    sheet_info_path = t01_sheet / "SheetInfo.json"
    question_path = t01_sheet / "Starter.json"
    original_sheet_uid = load_json_file(sheet_info_path)["uid"]
    original_question_uid = load_json_file(question_path)["uid"]

    config_path = tmp_path / "nobius.json"
    write_json(config_path, make_config_payload())

    subprocess.run(
        [
            sys.executable,
            "generateGroup.py",
            str(t01_sheet),
            "--config",
            str(config_path),
            "--reset-uid",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert load_json_file(sheet_info_path)["uid"] != original_sheet_uid
    assert load_json_file(question_path)["uid"] != original_question_uid


def test_render_sheet_raises_for_missing_sheetinfo(tmp_path):
    missing_dir = tmp_path / "empty_sheet"
    missing_dir.mkdir()

    with pytest.raises(NobiusRenderError, match="SheetInfo.json"):
        render_sheet(missing_dir, "manifests/assignment.xml", make_render_settings())


def test_process_custom_response_raises_when_layout_label_is_missing():
    response_schema = load_json_file(REPO_ROOT / "validation" / "schemas" / "response_areas.json")
    response_defaults = load_json_file(REPO_ROOT / "validation" / "defaults" / "response_areas.json")
    part = {
        "custom_response": {
            "layout": "<missing>",
            "responses": {
                "x": {"mode": "List", "choices": ["A"], "display": {"display": "text", "permute": False}},
            },
        }
    }

    with pytest.raises(NobiusRenderError, match="x not found in custom_response"):
        process_custom_response(1, part, "Bad Question", 0, response_schema, response_defaults)


def test_process_custom_response_raises_when_layout_label_is_duplicated():
    response_schema = load_json_file(REPO_ROOT / "validation" / "schemas" / "response_areas.json")
    response_defaults = load_json_file(REPO_ROOT / "validation" / "defaults" / "response_areas.json")
    part = {
        "custom_response": {
            "layout": "<x> then again <x>",
            "responses": {
                "x": {"mode": "List", "choices": ["A"], "display": {"display": "text", "permute": False}},
            },
        }
    }

    with pytest.raises(NobiusRenderError, match="Multiple x found in custom_response"):
        process_custom_response(1, part, "Bad Question", 0, response_schema, response_defaults)


def test_custom_response_validation_error_uses_correct_path_label():
    response_schema = load_json_file(REPO_ROOT / "validation" / "schemas" / "response_areas.json")
    response_defaults = load_json_file(REPO_ROOT / "validation" / "defaults" / "response_areas.json")
    part = {
        "custom_response": {
            "layout": "<1>",
            "responses": [{"mode": "List", "choices": ["A"]}],
        }
    }

    with pytest.raises(Exception, match="custom_response"):
        process_custom_response(1, part, "Bad Question", 0, response_schema, response_defaults)
