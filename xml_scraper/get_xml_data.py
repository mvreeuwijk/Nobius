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

def get_sheet_data_from_xml(xml, report=None):
    sheet = get_sheet_info(xml, report)
    sheet["questions"] = []
    questions_list = []

    for question_xml in get_questions(xml):
        question = get_question_from_xml(question_xml, report)
        sheet["questions"].append(question["title"])

        if question.get("number"):
            if "number" not in sheet:
                try:
                    sheet["number"] = int(str(question["number"]).split(".")[0])
                except (ValueError, IndexError):
                    report_warning(report, "Could not infer sheet number from question numbering.", str(question["number"]))
            del question["number"]

        questions_list.append(question)

    if "name" not in sheet:
        sheet["name"] = "Imported Sheet"
        report_warning(report, "Sheet name could not be parsed cleanly; using fallback name.", "Imported Sheet")

    if "number" not in sheet:
        sheet["number"] = 1
        report_warning(report, "Sheet number could not be parsed cleanly; using fallback number.", "1")

    return {"info": sheet, "questions": questions_list}

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
    
    return question

def get_question_html_properties(question_xml, report=None):
    html = get_question_html(question_xml)
    return get_question_data(html, report)


def build_minimal_question_structure(question_xml, parts, report=None):
    text_xml = question_xml.find("text", recursive=False)
    raw_text = text_xml.text if text_xml and text_xml.text else ""
    split_tokens = re.split(r"<(\d+)\s*\/?\s*>", raw_text)
    placeholder_matches = [int(token) for token in split_tokens[1::2]]

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
        link_response_answers(p, parts, report)

        if "structured_tutorial" in p:
            for st in p["structured_tutorial"]:
                link_response_answers(st, parts, report)


def link_response_answers(p, parts, report=None):
    if "matrix_response" in p:
        p["response"] = link_matrix_answers(p["matrix_response"], parts, report)
        del p["matrix_response"]
    elif "custom_response" in p:
        p["custom_response"] = link_custom_answers(p["custom_response"], parts)
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

    if normalized.get("mode") == "Multiple Choice":
        report_warning(
            report,
            "Normalized Möbius Multiple Choice mode into Nobius authoring mode.",
            normalized.get("name", "responseNan"),
        )
        normalized["mode"] = "Non Permuting Multiple Choice"
    elif normalized.get("mode") == "Multiple Response":
        report_warning(
            report,
            "Normalized Möbius Multiple Response mode into Nobius authoring mode.",
            normalized.get("name", "responseNan"),
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
            normalized.get("name", "responseNan"),
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
            normalized.get("name", "responseNan"),
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

def link_custom_answers(custom_response, parts):
    properties = {
        "layout": custom_response["layout"],
        "responses": []
    }

    for i in range(custom_response["numberof_tags"]):
        properties["responses"].append(parts[i + custom_response["starting_value"]])

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
