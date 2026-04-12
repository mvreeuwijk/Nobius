import os
import zipfile

import bs4
import pytest
import xml.etree.ElementTree as ET

from export_mobius_batch import ensure_output_structure, merge_xml
from import_mobius import (
    gather_media_references,
    get_import_media_strategy,
    import_mobius_package,
    resolve_manifest_path,
    safe_question_basename,
    select_media_match,
    write_group_json,
)
from preview_html import safe_extract_archive
from render_common import render_sheet
from validation.validation import add_response_area_defaults
from xml_scraper.get_html_data import get_question_data
from xml_scraper.get_xml_data import link_custom_answers, link_response_answers, normalize_response

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


def test_get_import_media_strategy_defaults_to_copy():
    assert get_import_media_strategy({}) == "copy"
    assert get_import_media_strategy({"import": {}}) == "copy"
    assert get_import_media_strategy({"import": {"media_strategy": "copy"}}) == "copy"


def test_generate_json_from_standard_zip_writes_expected_outputs(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "imported-standard"

    report = import_mobius_package(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    assert (destination / "SheetInfo.json").exists()
    assert (destination / "import_report.json").exists()
    assert (destination / "import_report.txt").exists()
    assert (destination / "media" / "TruncatedCone.png").exists()
    assert report.source_type == "zip"
    assert len(report.copied_media) >= 1


def test_import_mobius_package_defaults_media_strategy_when_config_is_empty(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "imported-empty-config"

    report = import_mobius_package(render_result["zip_path"], str(destination), True, {})

    assert (destination / "SheetInfo.json").exists()
    assert (destination / "media" / "TruncatedCone.png").exists()
    assert report.source_type == "zip"


def test_generate_json_imports_merged_course_module_into_assessment_folders(t01_sheet, t02_sheet, tmp_path):
    batch_output = tmp_path / "batch-output"
    zip_path = tmp_path / "merged-course-module.zip"
    destination = tmp_path / "merged-imported"

    ensure_output_structure(batch_output)
    render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(), output_dir=batch_output)
    render_sheet(t02_sheet, "manifests/assignment.xml", make_render_settings(), output_dir=batch_output)
    merged_xml = merge_xml(batch_output)

    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.write(merged_xml, arcname="manifest.xml")
        for media_file in (batch_output / "web_folders").rglob("*"):
            if media_file.is_file():
                zip_file.write(media_file, arcname=str(media_file.relative_to(batch_output)).replace("\\", "/"))

    report = import_mobius_package(str(zip_path), str(destination), False, load_json(REPO_ROOT / "nobius.json"))

    assert report.source_type == "zip"
    assert (destination / "Fundamentals" / "SheetInfo.json").exists()
    assert (destination / "Algorithmic Demo" / "SheetInfo.json").exists()
    assert rendered_question_titles(destination / "Fundamentals") == rendered_question_titles(t01_sheet)
    assert rendered_question_titles(destination / "Algorithmic Demo") == rendered_question_titles(t02_sheet)
    assert (destination / "Fundamentals" / "media" / "TruncatedCone.png").exists()


def test_generate_json_imports_multi_assignment_unit_into_nested_folders(t01_sheet, t02_sheet, tmp_path):
    batch_output = tmp_path / "batch-output-nested"
    zip_path = tmp_path / "merged-course-module-nested.zip"
    destination = tmp_path / "merged-imported-nested"

    ensure_output_structure(batch_output)
    render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(), output_dir=batch_output)
    render_sheet(t02_sheet, "manifests/assignment.xml", make_render_settings(), output_dir=batch_output)
    merged_xml = merge_xml(batch_output)

    tree = ET.parse(merged_xml)
    root = tree.getroot()
    units_root = root.find("./assignmentUnits")
    units = units_root.findall("./unit")
    first_unit = units[0]
    first_unit.find("./name").text = "Combined Unit"
    first_unit.find("./description").text = "Combined unit for nested import test."
    first_assignments = first_unit.find("./assignments")
    for extra_ref in units[1].findall("./assignments/aRef"):
        first_assignments.append(extra_ref)
    units_root.remove(units[1])
    tree.write(merged_xml, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.write(merged_xml, arcname="manifest.xml")
        for media_file in (batch_output / "web_folders").rglob("*"):
            if media_file.is_file():
                zip_file.write(media_file, arcname=str(media_file.relative_to(batch_output)).replace("\\", "/"))

    report = import_mobius_package(str(zip_path), str(destination), False, load_json(REPO_ROOT / "nobius.json"))

    assert report.source_type == "zip"
    assert (destination / "Combined Unit" / "Fundamentals" / "SheetInfo.json").exists()
    assert (destination / "Combined Unit" / "Algorithmic Demo" / "SheetInfo.json").exists()
    assert rendered_question_titles(destination / "Combined Unit" / "Fundamentals") == rendered_question_titles(t01_sheet)
    assert rendered_question_titles(destination / "Combined Unit" / "Algorithmic Demo") == rendered_question_titles(t02_sheet)


def test_generate_json_strip_uids_removes_sheet_and_question_uids(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    destination = tmp_path / "imported-no-uid"

    import_mobius_package(render_result["zip_path"], str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    sheet_info = load_json(destination / "SheetInfo.json")
    question = load_json(destination / "Fluids.json")

    assert "uid" not in sheet_info
    assert "uid" not in question


def test_standard_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-standard"

    import_mobius_package(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "manifests/assignment.xml", make_render_settings())
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["xml_path"].endswith("Fundamentals.xml")
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_exam_zip_round_trip_can_be_rendered_again(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(profile_name="exam"))
    imported = tmp_path / "roundtrip-exam"

    import_mobius_package(render_result["zip_path"], str(imported), False, load_json(REPO_ROOT / "nobius.json"))
    rerender_result = render_sheet(imported, "manifests/assignment.xml", make_render_settings(profile_name="exam"))
    imported_sheet_info = load_json(imported / "SheetInfo.json")

    assert rendered_question_titles(imported) == rendered_question_titles(t01_sheet)
    assert imported_sheet_info["uid"]
    assert rerender_result["zip_path"].endswith("Fundamentals.zip")


def test_t01_round_trip_preserves_custom_response_shape(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-custom"

    import_mobius_package(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Volume and Mass of Truncated Cone")
    custom_response = question["parts"][0]["custom_response"]

    assert len(custom_response_placeholders(custom_response["layout"])) == 4
    assert len(custom_response["responses"]) == 4
    assert all(response["mode"] == "List" for response in custom_response["responses"])


def test_t02_round_trip_preserves_algorithmic_question_content(t02_sheet, tmp_path):
    render_result = render_sheet(t02_sheet, "manifests/assignment.xml", make_render_settings())
    imported = tmp_path / "roundtrip-t02"

    import_mobius_package(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))
    question = load_question_by_title(imported, "Hydraulic Press")

    assert "algorithm" in question
    assert "$f=range(100,300,1)" in question["algorithm"]
    assert question["parts"][0]["response"]["mode"] == "Numeric"


def test_import_report_for_exam_style_round_trip_records_warning_for_nonstandard_name(t01_sheet, tmp_path):
    render_result = render_sheet(t01_sheet, "manifests/assignment.xml", make_render_settings(profile_name="exam"))
    imported = tmp_path / "roundtrip-report"

    report = import_mobius_package(render_result["zip_path"], str(imported), True, load_json(REPO_ROOT / "nobius.json"))

    assert any("Sheet name did not match" in warning["message"] for warning in report.warnings)


def test_generate_json_imports_real_question_types_demo_zip(question_types_demo_zip, tmp_path):
    destination = tmp_path / "question-types-demo"

    report = import_mobius_package(str(question_types_demo_zip), str(destination), True, load_json(REPO_ROOT / "nobius.json"))
    sheet_info = load_json(destination / "SheetInfo.json")

    assert report.source_type == "zip"
    assert sheet_info["name"] == "Question types demo"
    assert sheet_info["questions"] == [
        "Text Entry",
        "Multiple Choice",
        "Units",
        "Symbolic",
        "Symbolic 2",
        "Numeric Answer",
    ]
    assert load_question_by_title(destination, "Text Entry")["parts"][0]["response"]["mode"] == "List"
    assert load_question_by_title(destination, "Units")["parts"][0]["response"]["mode"] == "Numeric"


def test_finalize_sheet_payload_does_not_infer_exam_sheet_number_from_question_numbers():
    from xml_scraper.get_xml_data import finalize_sheet_payload

    result = finalize_sheet_payload(
        {"name": "Practice exam 2", "description": ""},
        [
            {"title": "Question 1", "number": "10.1"},
            {"title": "Question 2", "number": "10.2"},
        ],
    )

    assert result["info"]["number"] == 1


def test_get_assignment_unit_info_does_not_use_weight_for_exam_like_names():
    from bs4 import BeautifulSoup
    from xml_scraper.get_xml_data import get_assignment_unit_info

    unit_xml = BeautifulSoup(
        """
        <unit uid="u1">
            <name>Practice exam 2</name>
            <description></description>
            <weight>10</weight>
        </unit>
        """,
        "xml",
    ).find("unit")

    info = get_assignment_unit_info(unit_xml)

    assert "number" not in info


def test_import_preserves_assignment_question_ref_order(question_types_demo_zip, tmp_path):
    destination = tmp_path / "imported-reordered"
    zip_path = tmp_path / "question-types-reordered.zip"

    with zipfile.ZipFile(question_types_demo_zip, "r") as original_zip:
        manifest_xml = original_zip.read("manifest.xml")
        zip_entries = {
            name: original_zip.read(name)
            for name in original_zip.namelist()
            if name != "manifest.xml"
        }

    manifest_path = tmp_path / "manifest.xml"
    manifest_path.write_bytes(manifest_xml)

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    group_nodes = root.findall(".//lessonSection/questionGroups/lsqGroup")
    reordered = [group_nodes[2], group_nodes[0], group_nodes[5], group_nodes[3], group_nodes[1], group_nodes[4]]
    question_groups_node = root.find(".//lessonSection/questionGroups")
    for child in list(question_groups_node):
        question_groups_node.remove(child)
    for group in reordered:
        question_groups_node.append(group)
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.write(manifest_path, arcname="manifest.xml")
        for name, data in zip_entries.items():
            zip_file.writestr(name, data)

    import_mobius_package(str(zip_path), str(destination), True, load_json(REPO_ROOT / "nobius.json"))
    sheet_info = load_json(destination / "SheetInfo.json")

    assert sheet_info["questions"] == [
        "Units",
        "Text Entry",
        "Numeric Answer",
        "Symbolic",
        "Multiple Choice",
        "Symbolic 2",
    ]


def test_select_media_match_prefers_assignment_specific_folder():
    matches = [
        "web_folders/Fluid Statics 2/SluiceGate.png",
        "web_folders/Fluid Motion 01/SluiceGate.png",
    ]
    group = {
        "_path_parts": ["Fluid Motion", "Fluid Motion 01"],
        "_parent_unit": "Fluid Motion",
    }

    selected, matched_by_context = select_media_match(matches, group)

    assert selected == "web_folders/Fluid Motion 01/SluiceGate.png"
    assert matched_by_context is True


def test_get_question_data_recovers_placeholder_and_marks_from_duplicate_statement_blocks():
    html = bs4.BeautifulSoup(
        """
        <div class="wrapper">
          <span data-propname="title">Question 1</span>
          <div class="parts-container">
            <div class="part" id="part1">
              <p class="part-statement" data-propname="parts.1.statement">Main statement.</p>
              <p class="part-statement" data-propname="parts.1.statement"><6><span>&nbsp;</span></p>
              <p class="part-statement" data-propname="parts.1.statement">[4 MARKS]</p>
              <div class="response-wrapper" data-propname="parts.1.response">&nbsp;</div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    question = get_question_data(html)

    assert question["parts"][0]["statement"] == "Main statement."
    assert question["parts"][0]["response"] == 6
    assert question["parts"][0]["post_response_text"] == "[4 MARKS]"


def test_get_question_data_recovers_duplicate_statement_placeholders_without_spurious_response_warning():
    html = bs4.BeautifulSoup(
        """
        <div class="wrapper">
          <span data-propname="title">Question 1</span>
          <div class="parts-container">
            <div class="part" id="part1">
              <p class="part-statement" data-propname="parts.1.statement">Main statement.</p>
              <p class="part-statement" data-propname="parts.1.statement"><6><span>&nbsp;</span></p>
              <p class="part-statement" data-propname="parts.1.statement">[4 MARKS]</p>
              <div class="response-wrapper" data-propname="parts.1.response">&nbsp;</div>
            </div>
          </div>
        </div>
        """,
        "html.parser",
    )

    class StubReport:
        def __init__(self):
            self.warnings = []

        def warn(self, message, context=None):
            self.warnings.append({"message": message, "context": context})

    report = StubReport()
    question = get_question_data(html, report)

    assert question["parts"][0]["response"] == 6
    assert not any("Response area tag couldn't be found" in warning["message"] for warning in report.warnings)


def test_normalize_response_strips_response_nan_name_variant():
    response = {
        "mode": "Essay",
        "name": "responseNaN",
        "maxWordcount": 0,
    }

    normalized = normalize_response(response)

    assert "name" not in normalized


def test_real_question_types_demo_zip_surfaces_import_warnings_explicitly(question_types_demo_zip, tmp_path):
    destination = tmp_path / "question-types-demo-report"

    report = import_mobius_package(str(question_types_demo_zip), str(destination), True, load_json(REPO_ROOT / "nobius.json"))

    assert any("Question title could not be recovered" in info["message"] for info in report.infos)
    assert any("Response area tag couldn't be found" in warning["message"] for warning in report.warnings)


def test_generate_json_imports_real_roundtrip_demo_zip_to_expected_json_shape(roundtrip_demo_zip, tmp_path):
    destination = tmp_path / "moodle-roundtrip-imported"

    report = import_mobius_package(str(roundtrip_demo_zip), str(destination), False, load_json(REPO_ROOT / "nobius.json"))
    text_entry = load_question_by_title(destination, "Text Entry-20260408_220141")
    multiple_choice = load_question_by_title(destination, "Multiple Choice-20260408_220141")
    numerical = load_question_by_title(destination, "Numerical-20260408_220141")
    numerical_algorithmic = load_question_by_title(destination, "Numerical")
    symbolic = load_question_by_title(destination, "Symbolic")
    true_false = load_question_by_title(destination, "True False-20260408_220141")
    essay = load_question_by_title(destination, "Essay-20260408_220141")
    matching = load_question_by_title(destination, "Matching-20260408_220141")

    assert report.source_type == "zip"
    assert load_json(destination / "SheetInfo.json")["name"] == "Moodle Round Trip Demo"
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

    report = import_mobius_package(str(roundtrip_demo_zip), str(destination), False, load_json(REPO_ROOT / "nobius.json"))
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


def test_get_question_from_xml_uses_top_level_question_text_not_hint_text():
    from xml_scraper.get_xml_data import get_question_from_xml

    question_xml = bs4.BeautifulSoup(
        """
        <question uid="q1">
          <name>1 Lock</name>
          <hints>
            <hint>
              <text><![CDATA[<p>Hint body only.</p>]]></text>
            </hint>
          </hints>
          <text><![CDATA[
            <div class="wrapper">
              <span data-propname="title">Lock</span>
              <p data-propname="master_statement">Actual question statement.</p>
              <div class="parts-container">
                <div class="part">
                  <p data-propname="parts.1.statement">Actual part.</p>
                  <div class="response-wrapper" data-propname="parts.1.response"><1></div>
                </div>
              </div>
            </div>
          ]]></text>
          <parts>
            <part>
              <mode>Essay</mode>
              <name>responseNaN</name>
              <maxWordcount>0</maxWordcount>
            </part>
          </parts>
        </question>
        """,
        "xml",
    ).find("question")

    question = get_question_from_xml(question_xml)

    assert question["title"] == "Lock"
    assert question["master_statement"] == "Actual question statement."
    assert question["parts"][0]["statement"] == "Actual part."
    assert question["parts"][0]["response"]["mode"] == "Essay"
    assert "name" not in question["parts"][0]["response"]


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

    assert "Which one of these is true?" in multiple_selection_text
    assert "<1>" in multiple_selection_text
    assert "If a=$a m/s and b=$b m/s, what is c?" in multipart_text
    assert "<1>" in multipart_text
    assert "If v=$c is the velocity of a car and x0 is the initial position" in multipart_text
    assert "<2>" in multipart_text
    assert "Define a fluid." in text_entry_text
    assert "<1>" in text_entry_text
    assert "What is Newton's Third Law?" in multiple_choice_text
    assert "<1>" in multiple_choice_text
    assert "If a=$a and b=$b, what is c?" in numerical_text
    assert "<1>" in numerical_text
    assert "Give the equation for the area of a Circle in terms of its diameter D?" in symbolic_text
    assert "<1>" in symbolic_text
    assert "Hydrostatic pressure increases with depth in a stationary fluid." in true_false_text
    assert "<1>" in true_false_text
    assert "Briefly explain the difference between pressure and force." in essay_text
    assert "<1>" in essay_text
    assert "Match each quantity to its SI unit." in matching_text
    assert "<1>" in matching_text
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

    report = import_mobius_package(render_result["zip_path"], str(destination), False, load_json(REPO_ROOT / "nobius.json"))

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


def test_link_response_answers_reports_out_of_range_placeholder_instead_of_crashing():
    part = {"response": 3}
    linked_parts = [{"mode": "Numeric", "answer": {"num": 1, "units": ""}, "comment": "", "name": "r1"}]
    warnings = []

    class StubReport:
        def warn(self, message, context=None):
            warnings.append((message, context))

    link_response_answers(part, linked_parts, StubReport())

    assert part["response"] is None
    assert any("out of range" in message for message, _ in warnings)


def test_link_custom_answers_reports_out_of_range_placeholder_instead_of_crashing():
    custom_response = {"layout": "<x>", "numberof_tags": 2, "starting_value": 1}
    linked_parts = [{"mode": "List", "answer": [1], "comment": "", "name": "r1"}]
    warnings = []

    class StubReport:
        def warn(self, message, context=None):
            warnings.append((message, context))

    linked = link_custom_answers(custom_response, linked_parts, StubReport())

    assert linked["responses"] == []
    assert any("Custom response could not be fully reconstructed" in message for message, _ in warnings)


def test_safe_extract_archive_rejects_parent_relative_members(tmp_path):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with zipfile.ZipFile(archive_path, "r") as archive:
        with pytest.raises(ValueError, match="unsafe zip member"):
            safe_extract_archive(archive, tmp_path / "assets")


def test_add_response_area_defaults_deep_copies_nested_defaults():
    defaults = {
        "Numeric": {
            "meta": {"tags": ["alpha"]},
        }
    }
    first = {"mode": "Numeric"}
    second = {"mode": "Numeric"}

    add_response_area_defaults(first, defaults, [])
    add_response_area_defaults(second, defaults, [])
    first["meta"]["tags"].append("beta")

    assert defaults["Numeric"]["meta"]["tags"] == ["alpha"]
    assert second["meta"]["tags"] == ["alpha"]
