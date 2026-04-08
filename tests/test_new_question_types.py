import pytest

from generateJSON import generate_json_file
from import_report import ImportReport
from render_common import normalize_response_area_for_render, render_sheet
from xml_scraper.get_xml_data import normalize_response

from .conftest import REPO_ROOT, create_sheet_fixture, load_json, load_question_by_title, make_render_settings


def build_html_question():
    return {
        "title": "HTML Widget",
        "master_statement": "Interact with the widget below.",
        "parts": [
            {
                "statement": "Set the widget to the correct value.",
                "response": {
                    "mode": "HTML",
                    "gradingType": "auto",
                    "answer": "42",
                    "html": "<div id=\"widget\"></div>",
                    "css": "#widget { min-height: 20px; }",
                    "javascript": "function initialize(interactiveMode) {}\nfunction setFeedback(response, answer) {}\nfunction getResponse() { return '42'; }",
                    "grading_code": "evalb(($ANSWER)-($RESPONSE)=0);"
                }
            }
        ],
        "uid": "11111111-1111-1111-1111-111111111111"
    }


def build_document_upload_question():
    return {
        "title": "Upload Work",
        "parts": [
            {
                "statement": "Upload your handwritten derivation.",
                "response": {
                    "mode": "Document Upload",
                    "uploadMode": "code",
                    "codeType": "alphanumeric",
                    "fileExtensions": ["pdf", "png"],
                    "notGraded": True
                }
            }
        ],
        "uid": "22222222-2222-2222-2222-222222222222"
    }


def test_html_response_renders_and_round_trips(tmp_path):
    sheet = create_sheet_fixture(
        tmp_path,
        "html_sheet",
        {
            "name": "HTML Demo",
            "description": "Synthetic HTML question fixture",
            "questions": ["HTML Widget"],
            "number": 1,
            "uid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        },
        [build_html_question()],
    )

    render_result = render_sheet(sheet, "master.xml", make_render_settings())
    imported = tmp_path / "html_imported"

    generate_json_file(render_result["xml_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "HTML Widget")
    response = question["parts"][0]["response"]

    assert response["mode"] == "HTML"
    assert response["html"] == "<div id=\"widget\"></div>"
    assert "getResponse()" in response["javascript"]
    assert response["grading_code"] == "evalb(($ANSWER)-($RESPONSE)=0);"


def test_html_response_round_trip_with_preserved_uids_can_be_rendered_again(tmp_path):
    sheet = create_sheet_fixture(
        tmp_path,
        "html_roundtrip_sheet",
        {
            "name": "HTML Stable Demo",
            "description": "Synthetic HTML question fixture",
            "questions": ["HTML Widget"],
            "number": 1,
            "uid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        },
        [build_html_question()],
    )

    render_result = render_sheet(sheet, "master.xml", make_render_settings())
    imported = tmp_path / "html_roundtrip_imported"

    generate_json_file(render_result["xml_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "master.xml", make_render_settings())
    response = load_question_by_title(imported, "HTML Widget")["parts"][0]["response"]

    assert (imported / "SheetInfo.json").exists()
    assert load_json(imported / "SheetInfo.json")["uid"]
    assert response["mode"] == "HTML"
    assert response["html"] == "<div id=\"widget\"></div>"
    assert rerender_result["xml_path"].endswith("HTML Stable Demo.xml")


def test_document_upload_response_normalizes_and_round_trips(tmp_path):
    sheet = create_sheet_fixture(
        tmp_path,
        "upload_sheet",
        {
            "name": "Upload Demo",
            "description": "Synthetic document upload fixture",
            "questions": ["Upload Work"],
            "number": 2,
            "uid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        },
        [build_document_upload_question()],
    )

    render_result = render_sheet(sheet, "master.xml", make_render_settings())
    imported = tmp_path / "upload_imported"

    generate_json_file(render_result["xml_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    response = load_question_by_title(imported, "Upload Work")["parts"][0]["response"]

    assert response["mode"] == "Document Upload"
    assert response["uploadMode"] == "code"
    assert response["codeType"] == "alphanumeric"
    assert response["fileExtensions"] == ["pdf", "png"]
    assert response["notGraded"] is True


def test_adaptive_questions_reject_document_upload_components(tmp_path):
    question = build_document_upload_question()
    question["adaptive"] = {"enabled": True}

    sheet = create_sheet_fixture(
        tmp_path,
        "adaptive_upload_sheet",
        {
            "name": "Adaptive Upload Demo",
            "description": "Invalid adaptive fixture",
            "questions": ["Upload Work"],
            "number": 3,
            "uid": "cccccccc-cccc-cccc-cccc-cccccccccccc"
        },
        [question],
    )

    with pytest.raises(ValueError, match="Adaptive questions cannot contain manually graded"):
        render_sheet(sheet, "master.xml", make_render_settings())


def test_normalize_response_reports_lossy_list_conversion():
    report = ImportReport("fixture", "xml", "dest", True)

    normalized = normalize_response({"mode": "List", "display": "text"}, report)

    assert normalized["display"] == {"display": "text", "permute": False}
    assert any("Normalized List response display" in warning["message"] for warning in report.warnings)


def test_normalize_response_reports_document_upload_conversion():
    report = ImportReport("fixture", "xml", "dest", True)

    normalized = normalize_response(
        {"mode": "Document Upload", "forceUpload": False, "nonGradeable": True, "codeType": 2},
        report,
    )

    assert normalized["uploadMode"] == "code"
    assert normalized["notGraded"] is True
    assert normalized["codeType"] == "alphanumeric"
    assert any("Normalized Document Upload response" in warning["message"] for warning in report.warnings)


def test_render_normalization_preserves_legacy_document_upload_forceupload_semantics():
    response = {"mode": "Document Upload", "forceUpload": False, "codeType": "alphanumeric"}

    normalize_response_area_for_render(response)

    assert response["forceUpload"] is False
    assert response["codeType"] == 2


def test_normalize_response_reports_html_field_renaming():
    report = ImportReport("fixture", "xml", "dest", True)

    normalized = normalize_response(
        {
            "mode": "HTML",
            "questionHTML": "<div></div>",
            "questionCSS": "",
            "questionJavaScript": "function getResponse() { return ''; }",
            "gradingCode": "evalb(true);",
        },
        report,
    )

    assert normalized["html"] == "<div></div>"
    assert normalized["css"] == ""
    assert "getResponse" in normalized["javascript"]
    assert normalized["grading_code"] == "evalb(true);"
    assert any("Normalized HTML response field names" in warning["message"] for warning in report.warnings)
