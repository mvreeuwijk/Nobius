import bs4

from import_report import ImportReport
from xml_scraper import get_sheet_data_from_xml


def load_experimental_sheet(path):
    return bs4.BeautifulSoup(path.read_text(encoding="utf-8"), "lxml-xml")


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
