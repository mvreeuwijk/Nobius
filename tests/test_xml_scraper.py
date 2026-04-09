import bs4
import re
import zipfile

from import_report import ImportReport
from import_mobius import import_mobius_package
from xml_scraper import get_sheet_data_from_xml
from xml_scraper.get_xml_data import get_prop_value

from .conftest import REPO_ROOT, load_json


def load_experimental_sheet(path):
    return bs4.BeautifulSoup(path.read_text(encoding="utf-8"), "lxml-xml")


def make_assignment_unit_xml(path):
    xml_text = path.read_text(encoding="utf-8")
    replacement = """
  <assignmentUnits>
    <unit uid="a94acccf-a5d8-43ae-8cfb-e912d2bd2567">
      <weight>1.0</weight>
      <name><![CDATA[  Experimental Sheet V2  ]]></name>
      <description><![CDATA[  Sheet to be bundled in lesson format  ]]></description>
      <privacy>10</privacy>
      <assignments>
        <aRef uid="experimental-assignment" weight="1.0"/>
      </assignments>
    </unit>
  </assignmentUnits>
"""
    xml_text = re.sub(r"<questionGroups>.*?</questionGroups>", replacement, xml_text, count=1, flags=re.S)
    return xml_text


def test_xml_scraper_parses_expected_sheet_metadata(experimental_xml_path):
    xml = load_experimental_sheet(experimental_xml_path)

    group = get_sheet_data_from_xml(xml)

    assert group["info"]["name"] == "Experimental Sheet V2"
    assert group["info"]["number"] == 2
    assert len(group["questions"]) == 4
    assert group["info"]["questions"] == [
        "Hydraulic Scale",
        "Viscometer",
        "Drag on a Plate",
        "Small gravitational waves in shallow waters",
    ]


def test_xml_scraper_preserves_numeric_and_multiple_choice_parts(experimental_xml_path):
    xml = load_experimental_sheet(experimental_xml_path)
    group = get_sheet_data_from_xml(xml)
    questions = {question["title"]: question for question in group["questions"]}

    hydraulic_scale = questions["Hydraulic Scale"]

    assert hydraulic_scale["parts"][0]["response"]["mode"] == "Numeric"
    assert hydraulic_scale["parts"][1]["response"]["mode"] == "Non Permuting Multiple Choice"


def test_xml_scraper_parses_maple_content_from_experimental_sheet(experimental_xml_path):
    xml = load_experimental_sheet(experimental_xml_path)
    group = get_sheet_data_from_xml(xml)
    questions = {question["title"]: question for question in group["questions"]}

    viscometer = questions["Viscometer"]

    assert viscometer["parts"][0]["response"]["mode"] == "Maple"
    assert "omega*R" in viscometer["parts"][0]["response"]["mapleAnswer"]


def test_xml_scraper_preserves_worked_solution_media(experimental_xml_path):
    xml = load_experimental_sheet(experimental_xml_path)
    group = get_sheet_data_from_xml(xml)
    questions = {question["title"]: question for question in group["questions"]}

    drag = questions["Drag on a Plate"]

    assert drag["media"] == ["Drag on a Plate Image.png"]
    assert drag["parts"][0]["worked_solutions"][0]["media"] == ["A4-Q3a.jpg"]
    assert drag["parts"][1]["worked_solutions"][0]["media"] == ["A4-Q3b.jpg"]


def test_xml_scraper_collects_report_warnings_without_failing_parse(experimental_xml_path):
    xml = load_experimental_sheet(experimental_xml_path)
    report = ImportReport("fixture.xml", "xml", "unused", True)

    group = get_sheet_data_from_xml(xml, report=report)

    assert len(group["questions"]) == 4
    assert isinstance(report.warnings, list)


def test_xml_scraper_parses_assignment_unit_exports(experimental_xml_path):
    xml = bs4.BeautifulSoup(make_assignment_unit_xml(experimental_xml_path), "lxml-xml")

    group = get_sheet_data_from_xml(xml)

    assert group["info"]["name"] == "Experimental Sheet V2"
    assert group["info"]["uid"] == "a94acccf-a5d8-43ae-8cfb-e912d2bd2567"
    assert len(group["questions"]) == 4


def test_generate_json_imports_assignment_unit_zip_exports(experimental_xml_path, tmp_path):
    zip_path = tmp_path / "assignment_unit_export.zip"
    destination = tmp_path / "imported_assignment_unit"
    xml_text = make_assignment_unit_xml(experimental_xml_path)

    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("manifest.xml", xml_text)

    report = import_mobius_package(str(zip_path), str(destination), True, load_json(REPO_ROOT / "nobius.json"))
    sheet_info = load_json(destination / "SheetInfo.json")

    assert report.source_type == "zip"
    assert sheet_info["name"] == "Experimental Sheet V2"
    assert sheet_info["number"] == 2
    assert len(sheet_info["questions"]) == 4


def test_xml_scraper_falls_back_to_mobius_question_name_when_title_prop_is_missing(experimental_xml_path):
    xml_text = experimental_xml_path.read_text(encoding="utf-8").replace('data-propname="title"', 'data-propname="heading"')
    xml = bs4.BeautifulSoup(xml_text, "lxml-xml")

    group = get_sheet_data_from_xml(xml)

    assert group["questions"][0]["title"] == "Hydraulic Scale"
    assert group["info"]["questions"][0] == "Hydraulic Scale"
    assert group["info"]["number"] == 2


def test_get_prop_value_ignores_whitespace_text_nodes_in_nested_properties():
    xml = bs4.BeautifulSoup(
        """
        <response>
          <html><![CDATA[<div>Hello</div>]]></html>
          <css><![CDATA[body { color: red; }]]></css>
        </response>
        """,
        "lxml-xml",
    )

    value = get_prop_value(xml.response)

    assert value == {
        "html": "<div>Hello</div>",
        "css": "body { color: red; }",
    }
