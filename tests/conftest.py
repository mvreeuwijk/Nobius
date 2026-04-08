import json
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT.parent
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
QUESTIONS_ROOT = FIXTURES_ROOT if FIXTURES_ROOT.exists() else PROJECT_ROOT / "Questions"
MOBIUS_EXPORTS_ROOT = FIXTURES_ROOT / "mobius_exports"
BASELINES_ROOT = FIXTURES_ROOT / "baselines"
TEST_RENDER_CONFIG = {
    "render": {
        "theme_location": "/themes/test-theme",
        "scripts_location": "/web/test/scripts.js",
        "exam_theme_location": "/themes/test-exam-theme",
        "exam_scripts_location": "/web/test/exam-scripts.js",
    }
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def copy_sheet_fixture(source_name, target_root):
    source = QUESTIONS_ROOT / source_name
    return copy_directory_fixture(source, target_root / source_name)


def copy_directory_fixture(source, destination):
    destination.mkdir(parents=True, exist_ok=True)

    for child in source.iterdir():
        if child.name in {"renders", "solutions"}:
            continue
        if child.is_dir():
            shutil.copytree(child, destination / child.name)
        else:
            shutil.copy2(child, destination / child.name)

    initialize_missing_uids(destination)
    return destination


def create_sheet_fixture(target_root, folder_name, sheet_info, questions, media_files=None):
    destination = target_root / folder_name
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "SheetInfo.json", sheet_info)

    for question in questions:
        write_json(destination / f"{question['title']}.json", question)

    if media_files:
        media_dir = destination / "media"
        media_dir.mkdir(exist_ok=True)
        for filename, content in media_files.items():
            (media_dir / filename).write_bytes(content)

    initialize_missing_uids(destination)
    return destination


def initialize_missing_uids(sheet_dir):
    sheet_info_path = sheet_dir / "SheetInfo.json"
    sheet_info = load_json(sheet_info_path)

    if not sheet_info.get("uid"):
        sheet_info["uid"] = str(uuid4())
        write_json(sheet_info_path, sheet_info)

    for question_name in sheet_info.get("questions", []):
        question_path = sheet_dir / f"{question_name}.json"
        question = load_json(question_path)
        if not question.get("uid"):
            question["uid"] = str(uuid4())
            write_json(question_path, question)


def question_titles(sheet_dir):
    sheet_info = load_json(sheet_dir / "SheetInfo.json")
    return list(sheet_info["questions"])


def rendered_question_titles(sheet_dir):
    titles = []
    for question_name in question_titles(sheet_dir):
        question = load_json(sheet_dir / f"{question_name}.json")
        titles.append(question["title"])
    return titles


def load_question_by_title(sheet_dir, title):
    return load_json(sheet_dir / f"{title}.json")


def custom_response_placeholders(layout):
    return re.findall(r"<\d+>", layout)


def make_render_settings(config=None, exam=False):
    config = config or TEST_RENDER_CONFIG
    if exam:
        return {
            "theme_location": config["render"]["exam_theme_location"],
            "scripts_location": config["render"]["exam_scripts_location"],
        }

    return {
        "theme_location": config["render"]["theme_location"],
        "scripts_location": config["render"]["scripts_location"],
    }


def make_config_payload(
    theme_location="/themes/test-theme",
    scripts_location="/web/test/scripts.js",
    exam_theme_location="/themes/test-exam-theme",
    exam_scripts_location="/web/test/exam-scripts.js",
):
    return {
        "render": {
            "theme_location": theme_location,
            "scripts_location": scripts_location,
            "exam_theme_location": exam_theme_location,
            "exam_scripts_location": exam_scripts_location,
        },
        "import": {
            "strip_uids": False,
            "media_strategy": "copy",
        },
    }


@pytest.fixture
def tmp_path():
    base_dir = Path(tempfile.gettempdir()) / "nobius_pytest"
    base_dir.mkdir(exist_ok=True)
    path = base_dir / f"pytest_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def t01_sheet(tmp_path):
    return copy_sheet_fixture("t01", tmp_path)


@pytest.fixture
def t02_sheet(tmp_path):
    return copy_sheet_fixture("t02", tmp_path)


@pytest.fixture
def uploads_sheet(tmp_path):
    return copy_sheet_fixture("Uploads", tmp_path)


@pytest.fixture
def template_questions_sheet(tmp_path):
    return copy_sheet_fixture("TemplateQuestions", tmp_path)


@pytest.fixture
def example_sheet(tmp_path):
    return copy_directory_fixture(REPO_ROOT / "example", tmp_path / "example")


@pytest.fixture
def experimental_xml_path():
    return REPO_ROOT / "xml_scraper" / "tests" / "experimental_sheet.xml"


@pytest.fixture
def question_types_demo_zip():
    return MOBIUS_EXPORTS_ROOT / "QuestionTypesDemo.zip"


@pytest.fixture
def experimental_sheet_v2_baseline_xml():
    return BASELINES_ROOT / "Experimental Sheet V2__6e6882e.xml"
