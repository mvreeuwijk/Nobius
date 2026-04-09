from .get_html_data import get_question_data, report_warning

import json
import bs4
import re
from html import unescape


def serialize_html_payload(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(serialize_html_payload(item) for item in value)
    if hasattr(value, "get_text"):
        return value.get_text()
    if isinstance(value, dict):
        items = list(value.items())
        if not items:
            return ""
        tag_name, tag_value = items[0]
        attributes = "".join(
            f' {key}="{attribute_value}"'
            for key, attribute_value in items[1:]
            if attribute_value is not None
        )
        inner_html = serialize_html_payload(tag_value)
        return f"<{tag_name}{attributes}>{inner_html}</{tag_name}>"
    return str(value)


def simplify_matching_html(value):
    if value is None:
        return ""
    decoded = unescape(str(value))
    soup = bs4.BeautifulSoup(decoded, "html.parser")
    return soup.get_text(" ", strip=True)

"""
Main Methods
"""

def finalize_sheet_payload(sheet, questions_list, report=None):
    sheet["questions"] = []

    for question in questions_list:
        sheet["questions"].append(question["title"])

        if question.get("number"):
            if "number" not in sheet:
                try:
                    sheet["number"] = int(str(question["number"]).split(".")[0])
                except (ValueError, IndexError):
                    report_warning(report, "Could not infer sheet number from question numbering.", str(question["number"]))
            del question["number"]

    if "name" not in sheet:
        sheet["name"] = "Imported Sheet"
        report_warning(report, "Sheet name could not be parsed cleanly; using fallback name.", "Imported Sheet")

    if "number" not in sheet:
        sheet["number"] = 1
        report_warning(report, "Sheet number could not be parsed cleanly; using fallback number.", "1")

    return {"info": sheet, "questions": questions_list}


def get_sheets_data_from_xml(xml, report=None):
    question_lookup = {}
    questions_in_document_order = []
    manifest_path = None
    line_maps = {}
    if report is not None:
        manifest_path = report.metadata.get("manifest_path")
        line_maps = report.metadata.get("line_maps", {})

    for question_xml in get_questions(xml):
        question_name_xml = question_xml.find("name", recursive=False)
        question_name = question_name_xml.text if question_name_xml and question_name_xml.text else "Imported Question"
        question_uid = question_xml.get("uid")
        context_kwargs = {
            "manifest_path": manifest_path,
            "line": line_maps.get("questions", {}).get(question_uid),
            "item_type": "question",
            "item_name": question_name.strip() if isinstance(question_name, str) else "Imported Question",
        }
        if report is not None:
            with report.scoped_context(**context_kwargs):
                question = get_question_from_xml(question_xml, report)
        else:
            question = get_question_from_xml(question_xml, report)
        question_uid = question.get("uid") or question_uid
        if question_uid:
            question_lookup[question_uid] = question
        questions_in_document_order.append(question)

    assignment_sheets = get_assignment_sheets_from_xml(xml, question_lookup, questions_in_document_order, report)
    if assignment_sheets:
        referenced_uids = set()
        for sheet in assignment_sheets:
            for question in sheet["questions"]:
                question_uid = question.get("uid")
                if question_uid:
                    referenced_uids.add(question_uid)

        unassigned_questions = [
            question for question in questions_in_document_order
            if question.get("uid") not in referenced_uids
        ]
        if unassigned_questions:
            report_warning(
                report,
                "Some questions were not linked to an imported assessment; writing them into a fallback sheet.",
                str(len(unassigned_questions)),
            )
            assignment_sheets.append(
                finalize_sheet_payload(
                    {
                        "name": "Unassigned Questions",
                        "description": "Questions present in the manifest but not linked from assignment units.",
                    },
                    unassigned_questions,
                    report,
                )
            )
        return assignment_sheets

    sheet = get_sheet_info(xml, report)
    return [finalize_sheet_payload(sheet, questions_in_document_order, report)]


def get_sheet_data_from_xml(xml, report=None):
    sheets = get_sheets_data_from_xml(xml, report)
    return sheets[0]

def get_question_from_xml(question_xml, report=None):
    question = get_question_html_properties(question_xml, report)
    if "title" not in question:
        name_xml = question_xml.find("name", recursive=False)
        if name_xml and name_xml.text:
            question_name = name_xml.text.strip()
            number_match = re.match(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<title>.+)$", question_name)
            if number_match:
                question["title"] = number_match.group("title").strip()
                question.setdefault("number", number_match.group("number"))
            else:
                question["title"] = question_name
            report_warning(
                report,
                "Question title could not be recovered from data-propname markup; using Mobius question name.",
                question_name,
            )
    question.update(get_algorithm(question_xml))
    question.update(get_ids(question_xml))
    
    parts = get_list_of_part_properties(question_xml)
    if "parts" not in question or not question["parts"]:
        question.update(build_minimal_question_structure(question_xml, parts, report))
    add_parts_to_question(question, parts, report)
    normalize_question_structure(question, report)
    
    return question


def normalize_question_structure(question, report=None):
    icon_data = question.get("icon_data")
    parts = question.get("parts")

    if (
        isinstance(icon_data, dict)
        and isinstance(parts, list)
        and len(parts) == 1
        and isinstance(parts[0], dict)
    ):
        statement = icon_data.get("statement")
        part_statement = parts[0].get("statement")
        if isinstance(statement, str) and statement.strip() and (part_statement is None or not str(part_statement).strip()):
            parts[0]["statement"] = statement.strip()
            del icon_data["statement"]
            report_warning(report, "Moved misplaced icon_data.statement into the first part statement during import.", question.get("title"))

    if isinstance(icon_data, dict) and not icon_data:
        question.pop("icon_data", None)


def get_assignment_sheets_from_xml(xml, question_lookup, questions_in_document_order, report=None):
    course_module = xml.find("courseModule", recursive=False)
    if course_module is None:
        course_module = xml.find("courseModule") or xml
    manifest_path = None
    line_maps = {}
    if report is not None:
        manifest_path = report.metadata.get("manifest_path")
        line_maps = report.metadata.get("line_maps", {})

    units_root = course_module.find("assignmentUnits", recursive=False)
    assignments_root = course_module.find("assignments", recursive=False)
    if units_root is None or assignments_root is None:
        return []

    assignments_by_uid = {}
    for assignment_xml in assignments_root.find_all("assignment", recursive=False):
        assignment_uid = assignment_xml.get("uid")
        if assignment_uid:
            assignments_by_uid[assignment_uid] = assignment_xml

    sheets = []
    for unit_xml in units_root.find_all("unit", recursive=False):
        unit_name_xml = unit_xml.find("name", recursive=False)
        unit_name = unit_name_xml.text if unit_name_xml and unit_name_xml.text else "Imported Unit"
        unit_uid = unit_xml.get("uid")
        unit_context = {
            "manifest_path": manifest_path,
            "line": line_maps.get("assignment_units", {}).get(unit_uid),
            "item_type": "assignment unit",
            "item_name": unit_name.strip() if isinstance(unit_name, str) else "Imported Unit",
        }
        assignments_xml = unit_xml.find("assignments", recursive=False)
        if assignments_xml is None:
            continue

        if report is not None:
            with report.scoped_context(**unit_context):
                unit_info = get_assignment_unit_info(unit_xml, report)
        else:
            unit_info = get_assignment_unit_info(unit_xml, report)
        assignment_entries = []
        for assignment_ref in assignments_xml.find_all("aRef", recursive=False):
            assignment_uid = assignment_ref.get("uid")
            assignment_xml = assignments_by_uid.get(assignment_uid)
            if assignment_xml is None:
                report_warning(report, "Assignment unit referenced a missing assignment during import.", assignment_uid)
                continue

            assignment_entries.append((assignment_uid, assignment_xml))

        if not assignment_entries:
            continue

        if len(assignment_entries) == 1:
            referenced_question_uids = set()
            for _, assignment_xml in assignment_entries:
                for question_ref in iter_assignment_question_refs(assignment_xml):
                    question_uid = question_ref.get("uid")
                    if not question_uid:
                        continue

                    if question_uid not in question_lookup:
                        report_warning(report, "Assignment referenced a missing question during import.", question_uid)
                        continue

                    referenced_question_uids.add(question_uid)

            ordered_questions = [
                question for question in questions_in_document_order
                if question.get("uid") in referenced_question_uids
            ]

            if ordered_questions:
                sheet = finalize_sheet_payload(unit_info, ordered_questions, report)
                sheet["_path_parts"] = [unit_info["name"]]
                sheets.append(sheet)
            continue

        for assignment_index, (assignment_uid, assignment_xml) in enumerate(assignment_entries, start=1):
            assignment_name_xml = assignment_xml.find("name", recursive=False)
            assignment_name = assignment_name_xml.text if assignment_name_xml and assignment_name_xml.text else f"set{assignment_index}"
            assignment_context = {
                "manifest_path": manifest_path,
                "line": line_maps.get("assignments", {}).get(assignment_uid),
                "item_type": "assignment",
                "item_name": assignment_name.strip() if isinstance(assignment_name, str) else f"set{assignment_index}",
            }
            referenced_question_uids = set()
            if report is not None:
                with report.scoped_context(**assignment_context):
                    for question_ref in iter_assignment_question_refs(assignment_xml):
                        question_uid = question_ref.get("uid")
                        if not question_uid:
                            continue

                        if question_uid not in question_lookup:
                            report_warning(report, "Assignment referenced a missing question during import.", question_uid)
                            continue

                        referenced_question_uids.add(question_uid)
            else:
                for question_ref in iter_assignment_question_refs(assignment_xml):
                    question_uid = question_ref.get("uid")
                    if not question_uid:
                        continue

                    if question_uid not in question_lookup:
                        report_warning(report, "Assignment referenced a missing question during import.", question_uid)
                        continue

                    referenced_question_uids.add(question_uid)

            ordered_questions = [
                question for question in questions_in_document_order
                if question.get("uid") in referenced_question_uids
            ]

            if not ordered_questions:
                continue

            if report is not None:
                with report.scoped_context(**assignment_context):
                    sheet = finalize_sheet_payload(get_assignment_info(assignment_xml, assignment_index, report), ordered_questions, report)
            else:
                sheet = finalize_sheet_payload(get_assignment_info(assignment_xml, assignment_index, report), ordered_questions, report)
            sheet["_path_parts"] = [unit_info["name"], sheet["info"]["name"]]
            sheet["_parent_unit"] = unit_info["name"]
            sheet["_parent_unit_uid"] = unit_info.get("uid")
            sheets.append(sheet)

    return sheets


def iter_assignment_question_refs(assignment_xml):
    regular_refs = assignment_xml.select("questionGroups > aqGroup > questions > qRef")
    if regular_refs:
        return regular_refs

    lesson_refs = assignment_xml.select("sections > lessonSection > questionGroups > lsqGroup > questions > qRef")
    if lesson_refs:
        return lesson_refs

    return []

def get_question_html_properties(question_xml, report=None):
    html = get_question_html(question_xml)
    return get_question_data(html, report)


def build_minimal_question_structure(question_xml, parts, report=None):
    text_xml = question_xml.find("text", recursive=False)
    raw_text = text_xml.text if text_xml and text_xml.text else ""
    split_tokens = re.split(r"<(\d+)\s*\/?\s*>", raw_text)
    placeholder_matches = [int(token) for token in split_tokens[1::2]]

    if placeholder_matches:
        report_warning(
            report,
            "Question structure was reconstructed from raw HTML placeholders rather than explicit Mobius parts; review the imported question carefully.",
            question_xml.get("uid"),
        )

    prompt_html = split_tokens[0] if split_tokens else ""
    prompt_soup = bs4.BeautifulSoup(prompt_html, features="html.parser")
    prompt_text = prompt_soup.get_text(" ", strip=True)

    minimal_parts = []
    if placeholder_matches:
        for index, placeholder in enumerate(placeholder_matches):
            part_statement = ""
            if index > 0:
                statement_html = split_tokens[index * 2]
                statement_soup = bs4.BeautifulSoup(statement_html, features="html.parser")
                part_statement = statement_soup.get_text(" ", strip=True).replace("\xa0", " ").strip()

            minimal_parts.append({
                "statement": part_statement,
                "response": placeholder,
            })
    elif parts:
        minimal_parts.append({
            "statement": "",
            "response": 1,
        })

    if not minimal_parts:
        report_warning(report, "Could not reconstruct any parts from raw question text.", raw_text[:120])
        minimal_parts = [{"statement": ""}]

    return {
        "master_statement": prompt_text,
        "parts": minimal_parts,
    }

"""
BeautifulSoup Methods
"""

def get_list_of_part_properties(question_xml):
    return [get_part_properties(p) for p in get_parts(question_xml)]

def add_parts_to_question(question, parts, report=None):
    for p in question["parts"]:
        if not isinstance(p, dict):
            report_warning(report, "Skipped a malformed question part during import.", str(p))
            continue
        link_response_answers(p, parts, report)

        if "structured_tutorial" in p:
            for st in p["structured_tutorial"]:
                if not isinstance(st, dict):
                    report_warning(report, "Skipped a malformed structured tutorial part during import.", str(st))
                    continue
                link_response_answers(st, parts, report)


def link_response_answers(p, parts, report=None):
    if not isinstance(p, dict):
        report_warning(report, "Skipped a malformed nested response during import.", str(p))
        return

    if "matrix_response" in p:
        p["response"] = link_matrix_answers(p["matrix_response"], parts, report)
        del p["matrix_response"]
    elif "custom_response" in p:
        p["custom_response"] = link_custom_answers(p["custom_response"], parts, report)
    elif "responses" in p and len(p["responses"]) != 0:
        for r in p["responses"]:
            link_response_answers(r, parts, report)
    elif "response" in p and p["response"] is not None:
        linked_response = get_part_by_placeholder(parts, p["response"], report)
        if linked_response is not None:
            p["response"] = normalize_response(linked_response, report)
        else:
            p["response"] = None


def get_part_by_placeholder(parts, placeholder, report=None):
    if not isinstance(placeholder, int):
        report_warning(report, "Response placeholder was not an integer during import.", placeholder)
        return None

    index = placeholder - 1
    if index < 0 or index >= len(parts):
        report_warning(report, "Response placeholder was out of range during import.", placeholder)
        return None

    return parts[index]

def normalize_response(response, report=None):
    normalized = response.copy()
    for ignored_key in [
        "editing",
        "chainId",
        "numberOfAttempts",
        "numberOfAttemptsLeft",
        "numberOfTryAnother",
        "numberOfTryAnotherLeft",
        "privacy",
        "allowRepublish",
        "attributeAuthor",
        "modifiedIn",
        "difficulty",
        "text",
        "width",
        "fixed",
    ]:
        normalized.pop(ignored_key, None)

    response_name = normalized.get("name")
    if response_name is None or str(response_name).strip() in {"", "responseNan"}:
        normalized.pop("name", None)
        response_name = None
    else:
        response_name = str(response_name).strip()

    if normalized.get("mode") == "Multiple Choice":
        report_warning(
            report,
            "Normalized Möbius Multiple Choice mode into Nobius authoring mode.",
            response_name,
        )
        normalized["mode"] = "Non Permuting Multiple Choice"
    elif normalized.get("mode") == "Multiple Response":
        report_warning(
            report,
            "Normalized Möbius Multiple Response mode into Nobius authoring mode.",
            response_name,
        )
        normalized["mode"] = "Non Permuting Multiple Selection"

    if normalized.get("mode") in {"Non Permuting Multiple Choice", "True False"}:
        answer_value = normalized.get("answer")
        if isinstance(answer_value, str) and answer_value.strip().isdigit():
            normalized["answer"] = int(answer_value.strip())
    elif normalized.get("mode") == "Numeric":
        answer_value = normalized.get("answer")
        if isinstance(answer_value, list) and answer_value:
            normalized["answer"] = {
                "num": answer_value[0],
                "units": "",
            }
        elif isinstance(answer_value, (str, int, float)):
            normalized["answer"] = {
                "num": answer_value,
                "units": "",
            }
        elif isinstance(answer_value, dict):
            answer_value.setdefault("units", "")

    if normalized.get("mode") == "List" and isinstance(normalized.get("display"), str):
        report_warning(
            report,
            "Normalized List response display from legacy scalar form to Nobius object form.",
            normalized.get("display"),
        )
        normalized["display"] = {
            "display": normalized["display"],
            "permute": False
        }
    elif normalized.get("mode") == "Document Upload":
        code_type = normalized.get("codeType", 0)
        report_warning(
            report,
            "Normalized Document Upload response into Nobius authoring fields.",
            response_name,
        )
        normalized["uploadMode"] = "direct" if normalized.get("forceUpload") else "code"
        normalized["notGraded"] = normalized.get("nonGradeable", False)
        normalized["codeType"] = {
            0: "numeric",
            1: "alphabetic",
            2: "alphanumeric"
        }.get(code_type, code_type)
    elif normalized.get("mode") == "HTML":
        report_warning(
            report,
            "Normalized HTML response field names into Nobius authoring fields.",
            response_name,
        )
        if "questionHTML" in normalized:
            normalized["html"] = normalized.pop("questionHTML")
        if "questionCSS" in normalized:
            normalized["css"] = normalized.pop("questionCSS")
        if "questionJavaScript" in normalized:
            normalized["javascript"] = normalized.pop("questionJavaScript")
        if "gradingCode" in normalized:
            normalized["grading_code"] = normalized.pop("gradingCode")
        if "html" in normalized and not isinstance(normalized["html"], str):
            normalized["html"] = serialize_html_payload(normalized["html"])
        if "answer" in normalized and normalized["answer"] is not None and not isinstance(normalized["answer"], str):
            normalized["answer"] = str(normalized["answer"])
    elif normalized.get("mode") == "Matching":
        for matching in normalized.get("matchings", []):
            if "term" in matching:
                matching["term"] = simplify_matching_html(matching["term"])
            if "defs" in matching:
                matching["defs"] = [simplify_matching_html(definition) for definition in matching["defs"]]

    if normalized.get("comment") is None:
        normalized["comment"] = ""

    return normalized

def link_matrix_answers(matrix_response, parts, report=None):
    tags = json.loads(matrix_response)

    if is_empty_matrix(tags):
        report_warning(report, "Encountered an empty matrix response during import.")
        return None

    properties = get_all_same_properties(tags, parts, report)

    if "mode" in properties:
        if properties["mode"] == "Numeric":
            answer_key = "answer"
        elif properties["mode"] == "Maple":
            answer_key = "mapleAnswer"
        else:
            report_warning(report, "Matrix response mode not supported for Nobius matrix expansion.", properties["mode"])
            return None
    else:
        report_warning(report, "Matrix response parts had conflicting properties and could not be reconstructed.")
        return None
    
    answers = []
    for tags_row in tags:
        answer_row = []

        for tag in tags_row:
            linked_part = get_part_by_placeholder(parts, tag, report)
            if linked_part is None:
                report_warning(report, "Matrix response could not be reconstructed because a placeholder was invalid.", tag)
                return None
            if properties["mode"] == "Numeric":
                answer_row.append(linked_part["answer"]["num"])
            elif properties["mode"] == "Maple":
                answer_row.append(linked_part["mapleAnswer"])
        
        answers.append(answer_row)

    properties["mode"] = f"Matrix {properties['mode']}"
    properties[answer_key] = answers

    return properties

def link_custom_answers(custom_response, parts, report=None):
    properties = {
        "layout": custom_response["layout"],
        "responses": []
    }

    for i in range(custom_response["numberof_tags"]):
        placeholder = custom_response["starting_value"] + i + 1
        linked_part = get_part_by_placeholder(parts, placeholder, report)
        if linked_part is None:
            report_warning(
                report,
                "Custom response could not be fully reconstructed because a placeholder was invalid.",
                placeholder,
            )
            break
        properties["responses"].append(linked_part)

    return properties

def is_empty_matrix(m):
    for row in m:
        if len(row) > 0:
            return False
    return True

def get_all_same_properties(tags, parts, report=None):
    first_part = get_part_by_placeholder(parts, tags[0][0], report)
    if first_part is None:
        return {}

    properties = first_part.copy()

    for tags_row in tags:
        for tag in tags_row:
            linked_part = get_part_by_placeholder(parts, tag, report)
            if linked_part is None:
                return {}
            compare_properties(properties, linked_part)
        
    return properties

def compare_properties(mutable_dict, immutable_dict):
    for key in [*mutable_dict]:
        if key not in immutable_dict or immutable_dict[key] != mutable_dict[key]:
            del mutable_dict[key]

def get_sheet_info(xml, report=None):
    group_xml = get_sheet_container(xml)

    if group_xml is None:
        raise ValueError("Could not find a supported sheet container in the Mobius export.")

    info = get_sheet_name(group_xml.find("name").text, report)
    description_xml = group_xml.find("description")
    info["description"] = description_xml.text.strip() if description_xml and description_xml.text else ""
    
    info.update(get_ids(group_xml))

    return info


def get_assignment_unit_info(unit_xml, report=None):
    name_xml = unit_xml.find("name", recursive=False)
    description_xml = unit_xml.find("description", recursive=False)
    weight_xml = unit_xml.find("weight", recursive=False)
    raw_name = name_xml.text.strip() if name_xml and name_xml.text else "Imported Sheet"

    info = get_sheet_name(raw_name, report)
    info["description"] = description_xml.text.strip() if description_xml and description_xml.text else ""
    if weight_xml and weight_xml.text:
        try:
            info.setdefault("number", int(float(weight_xml.text.strip())))
        except ValueError:
            report_warning(report, "Could not parse assignment unit weight into a sheet number.", weight_xml.text.strip())
    info.update(get_ids(unit_xml))

    return info


def get_assignment_info(assignment_xml, assignment_index=None, report=None):
    name_xml = assignment_xml.find("name", recursive=False)
    description_xml = assignment_xml.find("description", recursive=False)
    fallback_name = f"set{assignment_index}" if assignment_index is not None else "Imported Assignment"
    assignment_name = name_xml.text.strip() if name_xml and name_xml.text else fallback_name

    info = {
        "name": assignment_name,
        "description": description_xml.text.strip() if description_xml and description_xml.text else "",
    }
    info.update(get_ids(assignment_xml))
    return info


def get_sheet_container(xml):
    question_groups = xml.find("questionGroups")
    if question_groups is not None:
        group = question_groups.find("group")
        if group is not None:
            return group

    assignment_units = xml.find("assignmentUnits")
    if assignment_units is not None:
        unit = assignment_units.find("unit")
        if unit is not None:
            return unit

    return None

def get_questions(xml):
    return xml.find_all("question", {"uid": True})

def get_question_html(question_xml):
    html_string = question_xml.find("text").string
    return bs4.BeautifulSoup(html_string, 'html.parser')

def get_parts(question_xml):
    return question_xml.find_all("part")

def get_part_properties(part_xml):
    # finds all children in parts, which are its properties
    return {
        prop_xml.name: get_prop_value(prop_xml) \
        for prop_xml in part_xml.find_all(recursive=False)
    }

"""
JSON Nesting Methods
"""

def get_sheet_name(name_string, report=None):
    name_match = re.match(r"^\s+Sheet #(?P<number>\d+) - (?P<name>.+)\b\s+$", name_string)
    sheet_name = name_match.groupdict() if name_match else {"name": name_string.strip()}
    
    if "number" in sheet_name:
        sheet_name["number"] = int(sheet_name["number"])
    elif report is not None:
        report_warning(report, "Sheet name did not match the standard 'Sheet #N - Name' pattern.", name_string.strip())
    
    return sheet_name

def get_ids(xml):
    ids_dict = {}

    for key, value in xml.attrs.items():
        if key in ["uid"]: #["uid", "modifiedBy", "school"]:
            ids_dict[key] = value

    return ids_dict

def get_algorithm(xml):
    algorithm_xml = xml.find("algorithm", recursive=False)
    return {"algorithm": algorithm_xml.string} if algorithm_xml else {}

def get_prop_value(prop_xml):
    if prop_xml.find_all(recursive=False):
        return add_deeper_nest(prop_xml)
    elif prop_xml.attrs:
        prop_value = {prop_xml.name: cast_prop_string(prop_xml.string)}
        
        for name, value in prop_xml.attrs.items():
            prop_value[name] = cast_prop_string(value)

        return prop_value
    else:
        return cast_prop_string(prop_xml.string)

def add_deeper_nest(prop_xml):
    children = get_tag_children(prop_xml)
    if all_same_name(children):
        return add_nested_list(prop_xml)
    else:
        return add_nested_dictionary(prop_xml)

def get_tag_children(prop_xml):
    return [child for child in prop_xml.children if isinstance(child, bs4.element.Tag)]

def all_same_name(li):
    return len(li) > 0 and all(x.name == li[0].name for x in li)

def add_nested_list(prop_xml):
    return [get_prop_value(child) for child in get_tag_children(prop_xml)]

def add_nested_dictionary(prop_xml):
    return {child.name:get_prop_value(child) for child in get_tag_children(prop_xml)}

def cast_prop_string(prop_string):
    if not prop_string:
        return None
    elif prop_string.lower() == "true":
        return True
    elif prop_string.lower() == "false":
        return False
    elif re.match(r'^\d+$', prop_string): # check if int
        return int(prop_string)
    elif re.match(r'^\d+\.\d+$', prop_string): # check if float
        return float(prop_string)
    else:
        return prop_string.strip() # remove whitespace at ends of string from CDATA
