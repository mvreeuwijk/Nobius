from __future__ import annotations

from jinja2 import Environment, FileSystemLoader
from uuid import NAMESPACE_URL, uuid4, uuid5
import copy
import json
import os
import re
import shutil
from typing import Any
from zipfile import ZipFile

import templates.filters as filters
import validation


BASE_DIR = os.path.dirname(__file__)
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")
PACKAGED_SCRIPT_NAME = "QuestionJavaScript.txt"
PACKAGED_SCRIPT_ARCNAME = os.path.join("web_folders", "Scripts", PACKAGED_SCRIPT_NAME)
PACKAGED_SCRIPT_URI = "__BASE_URI__Scripts/QuestionJavaScript.txt"
PACKAGED_THEME_URI = "__BASE_URI__QuestionTheme.css"
PACKAGED_MAPLE_LIBRARY_NAME = "Nobius4.mla"
PACKAGED_MAPLE_LIBRARY_ARCNAME = os.path.join("web_folders", PACKAGED_MAPLE_LIBRARY_NAME)
DOCUMENT_UPLOAD_CODE_TYPES = {
    "numeric": 0,
    "alphabetic": 1,
    "alphanumeric": 2,
}


class RenderConsts:
    def __init__(self, scripts_location, theme_location, layout_profile="default"):
        self.SCRIPTS_LOCATION = scripts_location
        self.THEME_LOCATION = theme_location
        self.LAYOUT_PROFILE = layout_profile


class NobiusRenderError(ValueError):
    pass


def deterministic_uuid(seed):
    return str(uuid5(NAMESPACE_URL, seed))


def resolve_media_path(work_dir):
    for candidate in ("media", "Media"):
        candidate_path = os.path.join(work_dir, candidate)
        if os.path.isdir(candidate_path):
            return candidate_path
    return os.path.join(work_dir, "media")


def load_json_file(filepath: str | os.PathLike) -> Any:
    with open(filepath, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            print(validation.get_path_string([os.path.basename(filepath)]))
            raise


def ensure_stable_uid(payload, filepath, clear_uids=False, write_missing_uids=False):
    has_uid = bool(payload.get("uid"))

    if clear_uids:
        payload["uid"] = str(uuid4())
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4)
        return payload["uid"]

    if has_uid:
        return payload["uid"]

    if write_missing_uids:
        payload["uid"] = str(uuid4())
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4)
        return payload["uid"]

    raise NobiusRenderError(
        f"Missing stable uid in {os.path.basename(filepath)}. "
        "Run again with --write-missing-uids to initialize source JSON identities."
    )


def import_question(question_path, sheet_number, question_number, q_schema, r_schema, r_defaults, clear_uids, write_missing_uids=False):
    question = load_json_file(question_path)
    ensure_stable_uid(question, question_path, clear_uids=clear_uids, write_missing_uids=write_missing_uids)

    validation.validate_question(question_path, question, q_schema)

    question["sheet_number"] = sheet_number
    question["number"] = question_number
    question["response_areas"] = []
    identifier = 1

    for i in range(len(question["parts"])):
        part = question["parts"][i]
        is_maple = False
        responses = []

        if "response" in part:
            responses, identifier, is_maple = process_response(identifier, part, question["title"], i, r_schema, r_defaults)
        elif "responses" in part:
            responses, identifier, is_maple = process_responses(identifier, part, question["title"], i, r_schema, r_defaults)
        elif "custom_response" in part:
            responses, identifier, is_maple = process_custom_response(identifier, part, question["title"], i, r_schema, r_defaults)

        question["response_areas"].extend(responses)

        if is_maple:
            question["parts"][i]["isMaple"] = True

        res_in_part = responses != []
        res_in_struct = 0

        if "structured_tutorial" in part:
            for j in range(len(part["structured_tutorial"])):
                item = question["parts"][i]["structured_tutorial"][j]
                is_maple = False
                responses = []

                if "response" in item:
                    responses, identifier, is_maple = process_response(identifier, item, question["title"], i, r_schema, r_defaults)
                elif "responses" in item:
                    responses, identifier, is_maple = process_responses(identifier, item, question["title"], i, r_schema, r_defaults)
                elif "custom_response" in item:
                    responses, identifier, is_maple = process_custom_response(identifier, item, question["title"], i, r_schema, r_defaults)

                question["response_areas"].extend(responses)

                if is_maple:
                    question["isMaple"] = True

                res_in_struct += 1 if responses else 0

            if res_in_struct > 1:
                print(f"\n[WARNING] Found more than 1 response area ({res_in_struct}) in structured tutorial\n\t- All are marked when check button is pressed\n")
            if res_in_part and res_in_struct:
                print("\n[WARNING] Response areas both in main part statement and structured tutorial\n\t- All are marked when check button is pressed\n")

    for response_index, response_area in enumerate(question["response_areas"], start=1):
        response_area.setdefault("uid", deterministic_uuid(f"{question['uid']}:part:{response_index}"))
        response_area.setdefault("language", "en")

    return question


def process_response(identifier, part, q_title, i, r_schema, r_defaults):
    normalize_response_area_for_render(part["response"])
    part["response_mode"] = part["response"]["mode"]
    is_maple = ("Maple" in part["response"]["mode"])

    if part["response"]["mode"] in ["Matrix Numeric", "Matrix Maple"]:
        data, responses = make_matrix(part["response"], identifier)
        part["response"] = data
        identifier = data[-1][-1]
    else:
        responses = [part["response"]]
        part["response"] = identifier

    r_path = [q_title, "parts", i, "response"]
    validation.validate_response_areas(responses, r_schema, r_defaults, r_path)
    identifier += 1
    return responses, identifier, is_maple


def process_responses(identifier, part, q_title, i, r_schema, r_defaults):
    is_maple = False
    response_areas = []

    for j in range(len(part["responses"])):
        normalize_response_area_for_render(part["responses"][j]["response"])
        if not is_maple:
            is_maple = ("Maple" in part["responses"][j]["response"]["mode"])

        if part["responses"][j]["response"]["mode"] in ["Matrix Numeric", "Matrix Maple"]:
            data, responses = make_matrix(part["responses"][j]["response"], identifier)
            part["responses"][j]["response"] = data
            identifier = data[-1][-1]
        else:
            responses = [part["responses"][j]["response"]]
            part["responses"][j]["response"] = identifier

        r_path = [q_title, "parts", i, "responses", j, "response"]
        validation.validate_response_areas(responses, r_schema, r_defaults, r_path)
        response_areas.extend(responses)
        identifier += 1

    return response_areas, identifier, is_maple


def process_custom_response(identifier, part, q_title, i, r_schema, r_defaults):
    if isinstance(part["custom_response"]["responses"], list):
        for response in part["custom_response"]["responses"]:
            normalize_response_area_for_render(response)
        responses = part["custom_response"]["responses"]
        is_maple = sum([("Maple" in response["mode"]) for response in responses])
        layout = part["custom_response"]["layout"]
        layout, n = re.subn(r"(?<=<)(\d+)(?=>)", lambda match: str(int(match.group(1)) + identifier - 1), layout)
        part["custom_response"] = layout
        identifier += n
    elif isinstance(part["custom_response"]["responses"], dict):
        for response in part["custom_response"]["responses"].values():
            normalize_response_area_for_render(response)
        is_maple = sum([("Maple" in response["mode"]) for response in part["custom_response"]["responses"].values()])
        layout = part["custom_response"]["layout"]
        responses = []

        for custom_label, resp in part["custom_response"]["responses"].items():
            responses += [resp]
            layout, n = re.subn(f"(?<=<){custom_label}(?=>)", str(identifier), layout)
            if n == 0:
                raise NobiusRenderError(f"{custom_label} not found in custom_response for {q_title} part {i}")
            elif n > 1:
                raise NobiusRenderError(f"Multiple {custom_label} found in custom_response for {q_title} part {i}")
            identifier += 1

        part["custom_response"] = layout
    else:
        responses = []
        is_maple = False

    r_path = [q_title, "parts", i, "custom_response"]
    validation.validate_response_areas(responses, r_schema, r_defaults, r_path)
    return responses, identifier, is_maple


def make_matrix(params: dict, identifier: int) -> tuple[list[list[int]], list[dict]]:
    res_areas: list[dict] = []

    if params["mode"] == "Matrix Numeric":
        rows = len(params["answer"])
        if rows == 0 or len(params["answer"][0]) == 0:
            raise NobiusRenderError("Matrix Numeric response requires a non-empty answer array")
        cols = len(params["answer"][0])
        data = [[identifier + j + cols * i for j in range(cols)] for i in range(rows)]
        params["mode"] = "Numeric"
        params["showUnits"] = False

        for row in params["answer"]:
            for answer in row:
                curr = copy.deepcopy(params)
                curr["answer"] = {"num": answer}
                res_areas += [curr]

    elif params["mode"] == "Matrix Maple":
        rows = len(params["mapleAnswer"])
        if rows == 0 or len(params["mapleAnswer"][0]) == 0:
            raise NobiusRenderError("Matrix Maple response requires a non-empty mapleAnswer array")
        cols = len(params["mapleAnswer"][0])
        data = [[identifier + j + cols * i for j in range(cols)] for i in range(rows)]
        params["mode"] = "Maple"

        for row in params["mapleAnswer"]:
            for answer in row:
                curr = copy.deepcopy(params)
                curr["mapleAnswer"] = answer
                res_areas += [curr]
    else:
        data = []

    return data, res_areas


def normalize_response_area_for_render(response):
    mode = response.get("mode")

    if mode == "Document Upload":
        if "notGraded" in response and "nonGradeable" not in response:
            response["nonGradeable"] = response["notGraded"]

        if isinstance(response.get("fileExtensions"), str):
            response["fileExtensions"] = [
                extension.strip()
                for extension in response["fileExtensions"].split(",")
                if extension.strip()
            ]

        if "uploadMode" in response:
            upload_mode = response["uploadMode"]
        elif "forceUpload" in response:
            upload_mode = "direct" if response["forceUpload"] else "code"
        else:
            upload_mode = "direct"
        response["forceUpload"] = upload_mode == "direct"

        code_type = response.get("codeType", 0)
        if isinstance(code_type, str):
            response["codeType"] = DOCUMENT_UPLOAD_CODE_TYPES.get(code_type, 0)

        response.pop("uploadMode", None)
        response.pop("notGraded", None)

    elif mode == "HTML":
        if "html" in response and "questionHTML" not in response:
            response["questionHTML"] = response.pop("html")
        if "css" in response and "questionCSS" not in response:
            response["questionCSS"] = response.pop("css")
        if "javascript" in response and "questionJavaScript" not in response:
            response["questionJavaScript"] = response.pop("javascript")
        if "grading_code" in response and "gradingCode" not in response:
            response["gradingCode"] = response.pop("grading_code")
    elif mode == "Essay":
        if response.get("keywords") is None:
            response["keywords"] = []


def iter_render_media_files(media_path):
    for media_file in sorted(os.listdir(media_path)):
        if media_file.startswith("."):
            continue
        yield media_file


def collect_question_media_references(node):
    references = set()

    if isinstance(node, dict):
        for key, value in node.items():
            if key == "media" and isinstance(value, list):
                references.update(value)
            else:
                references.update(collect_question_media_references(value))
    elif isinstance(node, list):
        for item in node:
            references.update(collect_question_media_references(item))

    return references


def build_course_module_context(sheet_info, questions, media_files, exam=False):
    assignment_uid = deterministic_uuid(f"{sheet_info['uid']}:assignment")
    instance_uid = deterministic_uuid("nobius:instance")
    author_uid = deterministic_uuid("nobius:author")

    question_groups = [
        {
            "name": sheet_info["name"],
            "uid": sheet_info["uid"],
            "weight": "1.0",
            "questions": [
                {
                    "uid": question["uid"],
                    "weight": f"{float(index):.1f}",
                }
                for index, question in enumerate(questions, 1)
            ],
        }
    ]

    web_resource_folders = [{
        "name": "web_folders/Scripts",
        "uri": "web_folders/Scripts",
    }]
    if media_files:
        web_resource_folders.insert(0, {
            "name": f"web_folders/{sheet_info['name']}",
            "uri": f"web_folders/{sheet_info['name']}",
        })

    return {
        "module": {
            "name": sheet_info["name"],
            "description": "Course Module",
            "uri": sheet_info["uid"],
            "privacy": 0,
            "autoModule": True,
            "exportedFrom": instance_uid,
        },
        "unit": {
            "uid": sheet_info["uid"],
            "modifiedBy": author_uid,
            "weight": f"{float(sheet_info['number']):.1f}",
            "name": sheet_info["name"],
            "description": sheet_info.get("description", ""),
            "privacy": 10,
            "assignment_uid": assignment_uid,
        },
        "question_groups": question_groups,
        "assignment": {
            "uid": assignment_uid,
            "name": sheet_info["name"],
            "description": sheet_info.get("description", ""),
            "privacy": 10,
            "category": "REGULAR",
            "presentationMode": 0,
            "question_groups": [
                {
                    "name": question["title"],
                    "weighting": 1,
                    "select": 1,
                    "question_uid": question["uid"],
                }
                for index, question in enumerate(questions, 1)
            ],
            "policies": {
                "mode": 1,
                "reworkable": "true",
                "reuseAlgorithmicVariables": "false",
                "targeted": "false",
                "scramble": 0,
                "printable": "false",
                "preAuthorized": "false",
                "gradeAuthorizationRequired": "false",
                "useLockdown": "false",
                "isVisibleAdvancedPolicy": "false",
                "passingScore": -1,
                "showPassFailFeedback": 4,
                "timeLimit": -1,
                "quPerPage": 1,
                "presentationMode": 0,
                "completionMode": 3,
                "isVisibleTimeRange": "false",
                "isVisible": "true",
                "forceGrade": "false",
                "allowSubmitLesson": "false",
                "showLaunchPage": "true",
                "showAdaptiveProgress": "false",
                "hintsShown": "false",
                "showOneHint": "false",
                "showCurrentGrade": "false",
                "allowResubmitQuestion": "true",
                "inSessionGradeReported": "false",
                "inSessionAnswer": 3,
                "inSessionComment": 3,
                "gradeReported": "true",
                "showAnswer": 2,
                "showComment": 0,
                "emailNotified": "false",
                "delayedFeedback": "false",
                "maxAttempts": -1,
            },
        },
        "authors": [],
        "schools": [],
        "web_resource_folders": web_resource_folders,
        "sheet_display_name": sheet_info["name"] if exam else f"Sheet #{sheet_info['number']} - {sheet_info['name']}",
    }


def resolve_template_name_and_layout(template_name, render_settings):
    layout_profile = render_settings.get("layout_profile")
    if layout_profile:
        return template_name, layout_profile
    return template_name, "default"


def render_sheet(
    work_dir: str | os.PathLike,
    template_name: str,
    render_settings: dict,
    reset_uid: bool = False,
    write_missing_uids: bool = False,
    output_dir: str | os.PathLike | None = None,
) -> dict[str, str]:
    print("[LOADING] Fetching sheet data")
    template_name, layout_profile = resolve_template_name_and_layout(template_name, render_settings)

    si_schema = load_json_file(os.path.join(BASE_DIR, "validation", "schemas", "sheet_info.json"))
    q_schema = load_json_file(os.path.join(BASE_DIR, "validation", "schemas", "question.json"))
    r_schema = load_json_file(os.path.join(BASE_DIR, "validation", "schemas", "response_areas.json"))
    r_defaults = load_json_file(os.path.join(BASE_DIR, "validation", "defaults", "response_areas.json"))

    try:
        with open(os.path.join(work_dir, "SheetInfo.json"), "r", encoding="utf-8") as file:
            sheet_info = json.load(file)
    except FileNotFoundError:
        raise NobiusRenderError("Folder specified does not contain the SheetInfo.json file")

    ensure_stable_uid(
        sheet_info,
        os.path.join(work_dir, "SheetInfo.json"),
        clear_uids=reset_uid,
        write_missing_uids=write_missing_uids,
    )

    validation.validate_sheet_info(os.path.join(work_dir, "SheetInfo.json"), sheet_info, si_schema)

    question_paths = [os.path.join(work_dir, f"{path}.json") for path in sheet_info["questions"]]
    questions = []
    question_number = 1
    for question_path in question_paths:
        questions += [import_question(
            question_path,
            sheet_info["number"],
            question_number,
            q_schema,
            r_schema,
            r_defaults,
            reset_uid,
            write_missing_uids=write_missing_uids,
        )]
        question_number += 1

    if not output_dir:
        times = [0, 0]
        qs = []
        for question in questions:
            try:
                times = map(sum, zip(question["icon_data"]["par_time"], times))
                qs += [(question["title"], question["icon_data"]["par_time"])]
            except KeyError:
                pass

        print("[TIME ANALYSIS] Estimated student time required summary ([min, max] mins):")
        for title, par_time in qs:
            print(f"\t-- {title}: {par_time}")
        print(f"\t-- Total: {list(times)}\n")

    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    env.globals.update(
        consts=RenderConsts(
            render_settings["scripts_location"],
            render_settings["theme_location"],
            layout_profile=layout_profile,
        ),
        packaged_scripts_location=PACKAGED_SCRIPT_URI,
        sheetName=sheet_info["name"],
        alphabet="abcdefghijklmnopqrstuvwxyz",
        arc=filters.get_arc_path,
        ticks=filters.get_ticks,
    )

    renders_dir = os.path.join(work_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    media_path = resolve_media_path(work_dir)
    zip_path = None
    referenced_media = set()
    for question in questions:
        referenced_media.update(collect_question_media_references(question))

    media_files = []
    if os.path.isdir(media_path):
        media_files = [
            media_file
            for media_file in iter_render_media_files(media_path)
            if media_file in referenced_media
        ]

    course_module = build_course_module_context(
        sheet_info,
        questions,
        media_files,
        exam=(layout_profile == "exam"),
    )

    master = env.get_template(template_name)
    rendered_xml = master.render(questions=questions, SheetInfo=sheet_info, CourseModule=course_module)
    print("[LOADING] XML Rendered Successfully")

    xml_path = os.path.join(renders_dir, f"{sheet_info['name']}.xml")
    with open(xml_path, "w", encoding="utf-8") as file:
        file.write(rendered_xml)

    if output_dir:
        with open(os.path.join(output_dir, "xml", f"{sheet_info['name']}.xml"), "w", encoding="utf-8") as file:
            file.write(rendered_xml)

    script_path = os.path.join(RESOURCES_DIR, PACKAGED_SCRIPT_NAME)
    maple_library_path = os.path.join(RESOURCES_DIR, PACKAGED_MAPLE_LIBRARY_NAME)
    zip_path = os.path.join(renders_dir, f"{sheet_info['name']}.zip")
    include_packaged_script = PACKAGED_SCRIPT_URI in rendered_xml or template_name == "manifests/questionbank.xml"
    include_packaged_maple_library = template_name == "manifests/questionbank.xml" and os.path.exists(maple_library_path)
    if media_files:
        print("[LOADING] Detected Media folder -> bundling media files and .xml")
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.write(xml_path, arcname="manifest.xml")
        if include_packaged_script and os.path.exists(script_path):
            zip_file.write(script_path, arcname=PACKAGED_SCRIPT_ARCNAME)
        if include_packaged_maple_library:
            zip_file.write(maple_library_path, arcname=PACKAGED_MAPLE_LIBRARY_ARCNAME)
        for media_file in media_files:
            zip_file.write(
                os.path.join(media_path, media_file),
                arcname=os.path.join("web_folders", f"{sheet_info['name']}", media_file),
            )

    if output_dir:
        scripts_output_dir = os.path.join(output_dir, "web_folders", "Scripts")
        os.makedirs(scripts_output_dir, exist_ok=True)
        if include_packaged_script and os.path.exists(script_path):
            shutil.copy(script_path, os.path.join(scripts_output_dir, PACKAGED_SCRIPT_NAME))
        if include_packaged_maple_library:
            shutil.copy(maple_library_path, os.path.join(output_dir, "web_folders", PACKAGED_MAPLE_LIBRARY_NAME))
        if media_files:
            output_media_path = os.path.join(output_dir, "web_folders", f"{sheet_info['name']}")
            if os.path.exists(output_media_path):
                shutil.rmtree(output_media_path)
            os.mkdir(output_media_path)
            for media_file in media_files:
                shutil.copy(os.path.join(media_path, media_file), output_media_path)

    print("[DONE]")
    return {"xml_path": xml_path, "zip_path": zip_path}
