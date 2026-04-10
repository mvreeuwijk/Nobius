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
    "default_profile": "problem_set",
    "html_preview_profile": "html_preview",
    "profiles": {
        "problem_set": {
            "render": {
                "theme_location": "/themes/test-theme",
                "scripts_location": "/web/test/scripts.js",
            },
            "pdf": {
                "heading": "problem_sets",
            },
        },
        "exam": {
            "render": {
                "theme_location": "/themes/test-exam-theme",
                "scripts_location": "/web/test/exam-scripts.js",
            },
            "pdf": {
                "heading": "problem_sets",
            },
        },
        "html_preview": {
            "render": {
                "theme_location": "/themes/test-preview-theme",
                "scripts_location": "/web/test/preview-scripts.js",
            },
            "pdf": {
                "heading": "generic",
            },
        },
    },
    "import": {
        "strip_uids": False,
        "media_strategy": "copy",
    },
    "pdf": {
        "headings": {
            "problem_sets": {
                "footer_label": r"Set \#",
                "section_label": r"Unit Test Set \#",
            },
            "exam": {
                "footer_label": "",
                "section_label": r"Unit Test Exam",
            },
            "generic": {
                "footer_label": r"Sheet \#",
                "section_label": r"Unit Test Sheet \#",
            },
        },
    },
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


def create_named_sheet_fixture(target_root, folder_name, sheet_info, questions_by_basename, media_files=None):
    destination = target_root / folder_name
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "SheetInfo.json", sheet_info)

    for basename, question in questions_by_basename.items():
        write_json(destination / f"{basename}.json", question)

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


def make_render_settings(config=None, profile_name="problem_set", render_mode="assignment"):
    config = config or TEST_RENDER_CONFIG
    layout_profile = "exam" if render_mode == "assignment" else "default"
    return {
        "theme_location": config["profiles"][profile_name]["render"]["theme_location"],
        "scripts_location": config["profiles"][profile_name]["render"]["scripts_location"],
        "layout_profile": layout_profile,
    }


def make_config_payload(
    problem_set_theme_location="/themes/test-theme",
    problem_set_scripts_location="/web/test/scripts.js",
    exam_theme_location="/themes/test-exam-theme",
    exam_scripts_location="/web/test/exam-scripts.js",
    preview_theme_location="/themes/test-preview-theme",
    preview_scripts_location="/web/test/preview-scripts.js",
    default_profile="problem_set",
    html_preview_profile="html_preview",
):
    return {
        "default_profile": default_profile,
        "html_preview_profile": html_preview_profile,
        "profiles": {
            "problem_set": {
                "render": {
                    "theme_location": problem_set_theme_location,
                    "scripts_location": problem_set_scripts_location,
                },
                "pdf": {
                    "heading": "problem_sets",
                },
            },
            "exam": {
                "render": {
                    "theme_location": exam_theme_location,
                    "scripts_location": exam_scripts_location,
                },
                "pdf": {
                    "heading": "problem_sets",
                },
            },
            "html_preview": {
                "render": {
                    "theme_location": preview_theme_location,
                    "scripts_location": preview_scripts_location,
                },
                "pdf": {
                    "heading": "generic",
                },
            },
        },
        "import": {
            "strip_uids": False,
            "media_strategy": "copy",
        },
        "pdf": {
            "headings": TEST_RENDER_CONFIG["pdf"]["headings"],
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
    return create_named_sheet_fixture(
        tmp_path,
        "t01",
        {
            "name": "Fundamentals",
            "description": "Synthetic render/import fixture with media and custom response coverage.",
            "questions": ["Starter", "Volume02"],
            "number": 1,
        },
        {
            "Starter": {
                "title": "Fluids",
                "master_statement": "After entering your answer, check the help box to check your work.",
                "icon_data": {"difficulty": 1, "par_time": [10, 15], "statement": ""},
                "media": ["TriangularPrism.png"],
                "parts": [
                    {
                        "statement": " Define (unambiguously) a fluid.",
                        "response": {
                            "mode": "List",
                            "display": {"display": "text", "permute": False},
                            "grader": "regex",
                            "answers": [
                                "~~~~~~~~~~Check the help box to get the answer~~~~~~~~~~",
                                ".*",
                            ],
                            "credits": [1, 0.9999999],
                        },
                        "final_answer": {
                            "text": "A substance that deforms continuously under the application of shear stress"
                        },
                    }
                ],
            },
            "Volume02": {
                "title": "Volume and Mass of Truncated Cone",
                "master_statement": "Using volume integrals, determine the volume and mass of a fluid of constant density \\(\\rho\\) in the following container filled up to the top. Determine the integrals by summing thin slices of height d\\(z\\) over the \\(z\\)-direction.",
                "icon_data": {"difficulty": 3, "par_time": [90, 125], "statement": ""},
                "media": ["TruncatedCone.png"],
                "parts": [
                    {
                        "statement": "The truncated cone:",
                        "custom_response": {
                            "layout": (
                                "<table><tr>"
                                "<td><span>\\(m=\\)</span></td>"
                                "<td><div class=\"inline-resp\"><1></div></td>"
                                "<td><span>\\(\\{ \\frac{1}{3} \\pi \\)</span></td>"
                                "<td><div class=\"inline-resp\"><2></div></td>"
                                "<td><span>\\(^{2}h+\\frac{1}{3} \\pi h R_{t} \\)</span></td>"
                                "<td><div class=\"inline-resp\"><3></div></td>"
                                "<td><span>\\(+\\frac{1}{3} \\pi \\)</span></td>"
                                "<td><div class=\"inline-resp\"><4></div></td>"
                                "<td><span>\\(R_{t}^{2}\\}\\)</span></td>"
                                "</tr></table>"
                            ),
                            "responses": [
                                {
                                    "mode": "List",
                                    "answers": ["\\(R_{0}\\)", "\\(R_{t}\\)", "\\(h\\)", "\\(\\pi\\)", "\\(\\rho\\)"],
                                    "credits": [0, 0, 0, 0, 1],
                                },
                                {
                                    "mode": "List",
                                    "answers": ["\\(R_{0}\\)", "\\(R_{t}\\)", "\\(h\\)", "\\(\\pi\\)", "\\(\\rho\\)"],
                                    "credits": [1, 0, 0, 0, 0],
                                },
                                {
                                    "mode": "List",
                                    "answers": ["\\(R_{0}\\)", "\\(R_{t}\\)", "\\(h\\)", "\\(\\pi\\)", "\\(\\rho\\)"],
                                    "credits": [1, 0, 0, 0, 0],
                                },
                                {
                                    "mode": "List",
                                    "answers": ["\\(R_{0}\\)", "\\(R_{t}\\)", "\\(h\\)", "\\(\\pi\\)", "\\(\\rho\\)"],
                                    "credits": [0, 0, 1, 0, 0],
                                },
                            ],
                        },
                        "final_answer": {
                            "text": "\\(V=\\frac{1}{3} \\pi R_{t}^{2}\\left\\{h+\\frac{h R_{0}}{R_{t}-R_{0}}\\right\\}-\\frac{1}{3} \\pi R_{0}^{2}\\left\\{\\frac{h}{R t-R_{i}}\\right\\} \\\\ m=\\rho\\left\\{\\frac{1}{3} \\pi R_{0}{ }^{2} h+\\frac{1}{3} \\pi h R_{t} R_{0}+\\frac{1}{3} \\pi h R_{t}^{2}\\right\\}\\)",
                        },
                        "worked_solutions": [
                            {"text": "Again consider a horizontal slice of thickness \\(dz\\). An element of volume is given by:<br>\\(dV=\\pi R(z)^{2}dz\\)"},
                            {"media": ["TruncatedConeAnswer01.png"]},
                        ],
                    }
                ],
            },
        },
        media_files={
            "TriangularPrism.png": b"triangular-prism-media",
            "TruncatedCone.png": b"truncated-cone-media",
            "TruncatedConeAnswer01.png": b"truncated-cone-answer-media",
        },
    )


@pytest.fixture
def t02_sheet(tmp_path):
    return create_named_sheet_fixture(
        tmp_path,
        "t02",
        {
            "name": "Algorithmic Demo",
            "description": "Synthetic algorithmic import fixture.",
            "questions": ["HydraulicPress"],
            "number": 2,
        },
        {
            "HydraulicPress": {
                "title": "Hydraulic Press",
                "master_statement": "Calculate the large-piston force.",
                "algorithm": "$f=range(100,300,1)\n$a=11\n$A=93\n$F=$f*$A/$a",
                "parts": [
                    {
                        "statement": "Give the force as an integer.",
                        "response": {
                            "mode": "Numeric",
                            "name": "response1",
                            "weighting": 1,
                            "comment": "",
                            "negStyle": "minus",
                            "numStyle": "thousands scientific arithmetic",
                            "grading": "exact_value",
                            "showUnits": False,
                            "answer": {"num": "$F", "units": ""},
                        },
                    }
                ],
            }
        },
    )


@pytest.fixture
def uploads_sheet(tmp_path):
    return copy_sheet_fixture("Uploads", tmp_path)


@pytest.fixture
def template_questions_sheet(tmp_path):
    return copy_sheet_fixture("TemplateQuestions", tmp_path)


@pytest.fixture
def roundtrip_sheet(tmp_path):
    return copy_sheet_fixture("RoundTrip", tmp_path)


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
def roundtrip_demo_zip():
    return MOBIUS_EXPORTS_ROOT / "RoundTripDemo.zip"


@pytest.fixture
def experimental_sheet_v2_baseline_xml():
    return BASELINES_ROOT / "Experimental Sheet V2__6e6882e.xml"
