import zipfile

import bs4

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
    write_json,
)


def test_resolve_manifest_path_detects_xml_source(experimental_xml_path):
    source_info = resolve_manifest_path(str(experimental_xml_path))

    assert source_info["source_type"] == "xml"
    assert source_info["manifest_path"] == str(experimental_xml_path)
    assert source_info["media_root"] is None


def test_resolve_manifest_path_detects_zip_source(t01_sheet):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())

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
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "imported-standard"

    report = generate_json_file(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    assert (destination / "SheetInfo.json").exists()
    assert (destination / "import_report.json").exists()
    assert (destination / "import_report.txt").exists()
    assert (destination / "media" / "TruncatedCone.png").exists()
    assert report.source_type == "zip"
    assert len(report.copied_media) >= 1


def test_generate_json_strip_uids_removes_sheet_and_question_uids(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "imported-no-uid"

    generate_json_file(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    sheet_info = load_json(destination / "SheetInfo.json")
    question = load_json(destination / "Fluids.json")

    assert "uid" not in sheet_info
    assert "uid" not in question


def test_standard_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-standard"

    generate_json_file(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "manifests/assignment.xml", make_render_settings())
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["xml_path"].endswith("Fundamentals.xml")
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_exam_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(exam=True))
    imported = tmp_path / "roundtrip-exam"

    generate_json_file(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "manifests/assignment.xml", make_render_settings(exam=True))
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_t01_round_trip_preserves_custom_response_shape(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-custom"

    generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Volume and Mass of Truncated Cone")
    custom_response = question["parts"][0]["custom_response"]

    assert len(custom_response_placeholders(custom_response["layout"])) == 4
    assert len(custom_response["responses"]) == 4
    assert all(response["mode"] == "List" for response in custom_response["responses"])


def test_t02_round_trip_preserves_algorithmic_question_content(t02_sheet, tmp_path):
    render_result = render_sheet(t02_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-t02"

    generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Hydraulic Press")

    assert "algorithm" in question
    assert "$f=range(100,300,1)" in question["algorithm"]
    assert question["parts"][0]["response"]["mode"] == "Numeric"


def test_import_report_for_exam_style_round_trip_records_warning_for_nonstandard_name(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(exam=True))
    imported = tmp_path / "roundtrip-report"

    report = generate_json_file(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))

    assert any("Sheet name did not match" in warning["message"] for warning in report.warnings)


def test_generate_json_imports_real_question_types_demo_zip(question_types_demo_zip, tmp_path):
    destination = tmp_path / "question-types-demo"

    report = generate_json_file(str(question_types_demo_zip), str(destination), True, load_json(REPO_ROOT / "nobius.json"))
    sheet_info = load_json(destination / "SheetInfo.json")

    assert report.source_type == "zip"
    assert sheet_info["name"] == "Question types demo"
    assert sheet_info["questions"] == [
        "Units",
        "Text Entry",
        "Symbolic",
        "Multiple Choice",
        "Numeric Answer",
        "Symbolic 2",
    ]
    assert load_question_by_title(destination, "Text Entry")["parts"][0]["response"]["mode"] == "List"
    assert load_question_by_title(destination, "Units")["parts"][0]["response"]["mode"] == "Numeric"


def test_real_question_types_demo_zip_surfaces_import_warnings_explicitly(question_types_demo_zip, tmp_path):
    destination = tmp_path / "question-types-demo-report"

    report = generate_json_file(str(question_types_demo_zip), str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    assert any("Question title could not be recovered" in warning["message"] for warning in report.warnings)
    assert any("Response area tag couldn't be found" in warning["message"] for warning in report.warnings)


def test_generate_json_imports_real_moodle_roundtrip_zip_to_expected_json_shape(moodle_demo_roundtrip_zip, tmp_path):
    destination = tmp_path / "moodle-roundtrip-imported"

    report = generate_json_file(str(moodle_demo_roundtrip_zip), str(destination), False, load_json(REPO_ROOT / "nobius.json"))
    text_entry = load_question_by_title(destination, "Text Entry-20260408_220141")
    multiple_choice = load_question_by_title(destination, "Multiple Choice-20260408_220141")
    numerical = load_question_by_title(destination, "Numerical-20260408_220141")
    numerical_algorithmic = load_question_by_title(destination, "Numerical")
    symbolic = load_question_by_title(destination, "Symbolic")
    true_false = load_question_by_title(destination, "True False-20260408_220141")
    essay = load_question_by_title(destination, "Essay-20260408_220141")
    matching = load_question_by_title(destination, "Matching-20260408_220141")

    assert report.source_type == "zip"
    assert load_json(destination / "SheetInfo.json")["name"] == "moodle_demo-20260408_220141"
    assert text_entry["master_statement"] == "Define a fluid."
    assert text_entry["parts"][0]["response"]["mode"] == "List"
    assert text_entry["parts"][0]["response"]["display"] == {"display": "text", "permute": False}
    assert multiple_choice["master_statement"] == "What is Newton's Third Law?"
    assert multiple_choice["parts"][0]["response"]["mode"] == "Non Permuting Multiple Choice"
    assert multiple_choice["parts"][0]["response"]["answer"] == 3
    assert "chainId" not in multiple_choice["parts"][0]["response"]
    assert "privacy" not in multiple_choice["parts"][0]["response"]
    assert "modifiedIn" not in multiple_choice["parts"][0]["response"]
    assert numerical["parts"][0]["response"]["mode"] == "Numeric"
    assert numerical["parts"][0]["response"]["answer"] == {"num": "9.81", "units": ""}
    assert numerical["parts"][0]["response"]["err"] == 0.01
    assert numerical_algorithmic["algorithm"]
    assert numerical_algorithmic["parts"][0]["response"]["answer"] == {"num": "$c", "units": ""}
    assert symbolic["parts"][0]["response"]["mode"] == "Maple"
    assert symbolic["parts"][0]["response"]["mapleAnswer"] == "Pi/4*D^2"
    assert symbolic["parts"][0]["response"]["maple"] == "evalb(($ANSWER)-($RESPONSE)=0);"
    assert true_false["parts"][0]["response"]["answer"] == 1
    assert essay["parts"][0]["response"]["mode"] == "Essay"
    assert essay["parts"][0]["response"]["maxWordcount"] == 0
    assert matching["parts"][0]["response"]["mode"] == "Matching"
    assert matching["parts"][0]["response"]["format"] == [3]
    assert len(matching["parts"][0]["response"]["matchings"]) == 3


def test_generate_json_imports_real_roundtrip_demo_zip_with_multipart_question(roundtrip_demo_zip, tmp_path):
    destination = tmp_path / "moodle-roundtrip-demo-imported"

    report = generate_json_file(str(roundtrip_demo_zip), str(destination), False, load_json(REPO_ROOT / "nobius.json"))
    multipart = load_question_by_title(destination, "Multipart hybrid exercise")
    multiple_selection = load_json(destination / "Multiple selection problem.json")

    assert report.source_type == "zip"
    assert load_json(destination / "SheetInfo.json")["name"] == "Moodle Round Trip Demo"
    assert multiple_selection["master_statement"] == "Which one of these is true?"
    assert multiple_selection["parts"][0]["response"]["mode"] == "Multiple Selection"
    assert multiple_selection["parts"][0]["response"]["answer"] == "1,3,5"
    assert multiple_selection["parts"][0]["response"]["display"] == "vertical"
    assert len(multiple_selection["parts"][0]["response"]["choices"]) == 5
    assert multipart["algorithm"]
    assert multipart["master_statement"] == "If a=$a m/s and b=$b m/s, what is c?"
    assert len(multipart["parts"]) == 2
    assert multipart["parts"][0]["response"]["mode"] == "Numeric"
    assert multipart["parts"][0]["response"]["answer"] == {"num": "$c", "units": "m/s"}
    assert multipart["parts"][1]["statement"] == (
        "If v=$c is the velocity of a car and x0 is the initial position, "
        "give an equation for the position of the car as a function of time t"
    )
    assert multipart["parts"][1]["response"]["mode"] == "Maple"
    assert multipart["parts"][1]["response"]["mapleAnswer"] == "x0+$c*t"


def test_roundtrip_exercise_json_supported_plain_subset_can_be_rendered(roundtrip_sheet):
    sheet_info_path = roundtrip_sheet / "SheetInfo.json"
    sheet_info = load_json(sheet_info_path)
    sheet_info["questions"] = [
        "Multiple selection problem",
        "Multipart hybrid exercise",
        "Text Entry-20260408_220141",
        "Multiple Choice-20260408_220141",
        "Numerical",
        "Symbolic",
        "True False-20260408_220141",
        "Essay-20260408_220141",
        "Matching-20260408_220141",
    ]
    sheet_info["name"] = "RoundTripExercise"
    write_json(sheet_info_path, sheet_info)

    result = render_sheet(roundtrip_sheet, "manifests/questionbank.xml", make_render_settings())
    rendered_xml = (roundtrip_sheet / "renders" / "RoundTripExercise.xml").read_text(encoding="utf-8")
    soup = bs4.BeautifulSoup(rendered_xml, "lxml-xml")
    root = soup.find("courseModule", recursive=False)
    questions = root.find("questions", recursive=False).find_all("question", recursive=False)

    assert result["zip_path"].endswith("RoundTripExercise.zip")
    assert root.find("questionGroups", recursive=False) is not None
    assert root.find("assignmentUnits", recursive=False) is None
    assert [question.find("name").text.strip() for question in questions] == [
        "Multiple selection problem.",
        "Multipart hybrid exercise",
        "Text Entry-20260408_220141",
        "Multiple Choice-20260408_220141",
        "Numerical",
        "Symbolic",
        "True False-20260408_220141",
        "Essay-20260408_220141",
        "Matching-20260408_220141",
    ]

    multiple_selection_text = questions[0].find("text").string
    multipart_text = questions[1].find("text").string
    text_entry_text = questions[2].find("text").string
    multiple_choice_text = questions[3].find("text").string
    numerical_text = questions[4].find("text").string
    symbolic_text = questions[5].find("text").string
    true_false_text = questions[6].find("text").string
    essay_text = questions[7].find("text").string
    matching_text = questions[8].find("text").string

    assert "<div>Which one of these is true?</div>" in multiple_selection_text or "<p>Which one of these is true?</p>" in multiple_selection_text
    assert "<1>" in multiple_selection_text
    assert "<p>If a=$a m/s and b=$b m/s, what is c?</p>" in multipart_text
    assert "<p><1><span>&nbsp;</span></p>" in multipart_text
    assert "If v=$c is the velocity of a car and x0 is the initial position" in multipart_text
    assert "<p><2><span>&nbsp;</span></p>" in multipart_text
    assert "<div>Define a fluid.</div>" in text_entry_text
    assert "<p><1><span>&nbsp;</span></p>" in text_entry_text
    assert "<div>What is Newton's Third Law?</div>" in multiple_choice_text
    assert "<p><1><span>&nbsp;</span></p>" in multiple_choice_text
    assert "<p>If a=$a and b=$b, what is c?</p>" in numerical_text
    assert "<p><1><span>&nbsp;</span></p>" in numerical_text
    assert "<p>Give the equation for the area of a Circle in terms of its diameter D?</p>" in symbolic_text
    assert "<p><1><span>&nbsp;</span></p>" in symbolic_text
    assert "<div>Hydrostatic pressure increases with depth in a stationary fluid.</div>" in true_false_text
    assert "<p><1><span>&nbsp;</span></p>" in true_false_text
    assert "<div>Briefly explain the difference between pressure and force.</div>" in essay_text
    assert "<p><1><span>&nbsp;</span></p>" in essay_text
    assert "<div>Match each quantity to its SI unit.</div>" in matching_text
    assert "<p><1><span>&nbsp;</span></p>" in matching_text
    assert questions[0].find("part").find("mode").text == "Non Permuting Multiple Selection"
    assert questions[0].find("part").find("answer").text.strip() == "1,3,5"
    assert len(questions[1].find_all("part")) == 2
    assert questions[1].find_all("part")[0].find("mode").text == "Numeric"
    assert questions[1].find_all("part")[0].find("answer").find("num").text.strip() == "$c"
    assert questions[1].find_all("part")[1].find("mode").text == "Maple"
    assert questions[1].find_all("part")[1].find("mapleAnswer").text.strip() == "x0+$c*t"
    assert questions[1].find("algorithm").text.strip()
    assert questions[2].find("part").find("mode").text == "List"
    assert questions[3].find("part").find("mode").text == "Non Permuting Multiple Choice"
    assert questions[4].find("part").find("mode").text == "Numeric"
    assert questions[4].find("part").find("answer").find("num").text.strip() == "$c"
    assert questions[4].find("algorithm").text.strip()
    assert questions[5].find("part").find("mode").text == "Maple"
    assert questions[5].find("part").find("mapleAnswer").text.strip() == "Pi/4*D^2"
    assert questions[6].find("part").find("mode").text == "Non Permuting Multiple Choice"
    assert questions[6].find("part").find("answer").text.strip() == "1"
    assert questions[7].find("part").find("mode").text == "Essay"
    assert questions[7].find("part").find("maxWordcount").text.strip() == "0"
    assert questions[8].find("part").find("mode").text == "Matching"
    assert questions[8].find("part").find("format").find("columns").text.strip() == "3"


def test_roundtrip_assignment_json_supported_plain_subset_can_be_rendered(roundtrip_sheet):
    sheet_info_path = roundtrip_sheet / "SheetInfo.json"
    sheet_info = load_json(sheet_info_path)
    sheet_info["questions"] = [
        "Multiple selection problem",
        "Multipart hybrid exercise",
        "Text Entry-20260408_220141",
        "Multiple Choice-20260408_220141",
        "Numerical",
        "Symbolic",
        "True False-20260408_220141",
        "Essay-20260408_220141",
        "Matching-20260408_220141",
    ]
    sheet_info["name"] = "RoundTripAssignment"
    write_json(sheet_info_path, sheet_info)

    result = render_sheet(roundtrip_sheet, "manifests/assignment.xml", make_render_settings())
    rendered_xml = (roundtrip_sheet / "renders" / "RoundTripAssignment.xml").read_text(encoding="utf-8")
    soup = bs4.BeautifulSoup(rendered_xml, "lxml-xml")
    root = soup.find("courseModule", recursive=False)
    questions = root.find("questions", recursive=False).find_all("question", recursive=False)

    assert result["zip_path"].endswith("RoundTripAssignment.zip")
    assert root.find("assignmentUnits", recursive=False) is not None
    assert root.find("assignments", recursive=False) is not None
    assert root.find("questionGroups", recursive=False) is None
    assert [question.find("name").text.strip() for question in questions] == [
        "Multiple selection problem.",
        "Multipart hybrid exercise",
        "Text Entry-20260408_220141",
        "Multiple Choice-20260408_220141",
        "Numerical",
        "Symbolic",
        "True False-20260408_220141",
        "Essay-20260408_220141",
        "Matching-20260408_220141",
    ]
    assert questions[0].find("part").find("mode").text == "Non Permuting Multiple Selection"
    assert questions[1].find_all("part")[0].find("mode").text == "Numeric"
    assert questions[1].find_all("part")[1].find("mode").text == "Maple"
    assert questions[4].find("part").find("mode").text == "Numeric"
    assert questions[5].find("part").find("mode").text == "Maple"
    assert questions[8].find("part").find("mode").text == "Matching"


def test_template_questions_zip_round_trip_imports_successfully_and_omits_hidden_media(template_questions_sheet, tmp_path):
    render_result = render_sheet(template_questions_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "template-questions-imported"

    report = generate_json_file(render_result["zip_path"], str(destination), False, load_json(REPO_ROOT / "nobius.json"))

    assert report.source_type == "zip"

    with zipfile.ZipFile(render_result["zip_path"], "r") as zip_file:
        members = set(zip_file.namelist())

    assert "manifest.xml" in members
    assert "web_folders/Question Type Demos/.tex" not in members
    assert "web_folders/Question Type Demos/Fundamentals.tex" not in members
    assert "web_folders/Question Type Demos/Tutorial 01 - Fundamentals.tex" not in members
    assert "web_folders/Question Type Demos/Volumes.png" in members
    assert (destination / "SheetInfo.json").exists()


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
