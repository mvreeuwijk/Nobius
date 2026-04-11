# -*- coding: utf-8 -*-
"""
Generate LaTeX and optional PDF output from a Nobius sheet.

The script writes TeX files for questions, review, or solutions content and can
optionally run pdflatex to produce PDFs. Some Nobius HTML content does not map
cleanly to LaTeX, and some valid TeX output may still fail to compile depending
on the installed LaTeX toolchain.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from subprocess import PIPE

import bs4
import validation
from nobius_config import load_config, resolve_pdf_profile, resolve_profile_name


def load_json_file(filepath):
    # Copied from Pierre/Louis
    with open(filepath, "r", encoding="utf-8") as file:
        try:
            json_dictionary = json.load(file)
        except json.JSONDecodeError as error:
            print(validation.get_path_string([os.path.basename(filepath)]))
            sys.tracebacklimit = 0
            raise error

    return json_dictionary


def get_batch_sheet_directories(parent_dir):
    sheets = []
    for item in os.listdir(parent_dir):
        sheet_dir = os.path.join(parent_dir, item)
        sheet_info_path = os.path.join(sheet_dir, "SheetInfo.json")
        if not os.path.isfile(sheet_info_path):
            continue

        sheet_info = load_json_file(sheet_info_path)
        sheet_number = sheet_info.get("number")
        if not isinstance(sheet_number, int):
            sheet_number = float("inf")

        sheet_name = str(sheet_info.get("name", item))
        sheets.append((sheet_number, sheet_name.lower(), item.lower(), item))

    sheets.sort()
    return [item for _, _, _, item in sheets]


def escape_tex_text(text):
    if not text:
        return ""

    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("\xa0", "~"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def normalize_tex_list_environments(text):
    if not text:
        return text

    replacements = [
        (r"\\begin\{enumerate\}\s*\[label=\\alph\*\)\]", r"\\begin{enumerate}[(a)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\Alph\*\)\]", r"\\begin{enumerate}[(A)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\roman\*\)\]", r"\\begin{enumerate}[(i)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\Roman\*\)\]", r"\\begin{enumerate}[(I)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\arabic\*\)\]", r"\\begin{enumerate}[1.]"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def render_html_table(table_tag):
    rows = []
    for tr in table_tag.find_all("tr", recursive=False):
        cells = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            cell_text = render_html_fragment(cell).strip()
            cell_text = re.sub(r"\s+", " ", cell_text)
            cells.append(cell_text)
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    colspec = "@{}" + "X" * max_cols + "@{}"

    lines = [r"\begin{center}", rf"\begin{{tabularx}}{{\linewidth}}{{{colspec}}}"]
    if normalized_rows:
        lines.append(r"\toprule")
        header = normalized_rows[0]
        lines.append(" & ".join(header) + r"\\")
        if len(normalized_rows) > 1:
            lines.append(r"\midrule")
            for row in normalized_rows[1:]:
                lines.append(" & ".join(row) + r"\\")
        lines.append(r"\bottomrule")
    lines.append(r"\end{tabularx}")
    lines.append(r"\end{center}")
    return "\n".join(lines)


def render_html_fragment(node):
    if node is None:
        return ""

    if isinstance(node, bs4.element.NavigableString):
        return escape_tex_text(str(node))

    if not isinstance(node, bs4.element.Tag):
        return ""

    name = node.name.lower()

    if name == "br":
        return "\n"
    if name in {"i", "em"}:
        return r"\emph{" + "".join(render_html_fragment(child) for child in node.children) + "}"
    if name in {"b", "strong"}:
        return r"\textbf{" + "".join(render_html_fragment(child) for child in node.children) + "}"
    if name == "p":
        return "\n\n" + "".join(render_html_fragment(child) for child in node.children).strip() + "\n\n"
    if name == "ul":
        items = []
        for child in node.find_all("li", recursive=False):
            item_text = "".join(render_html_fragment(grandchild) for grandchild in child.children).strip()
            items.append(r"\item " + item_text)
        return "\n\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}\n"
    if name == "ol":
        items = []
        for child in node.find_all("li", recursive=False):
            item_text = "".join(render_html_fragment(grandchild) for grandchild in child.children).strip()
            items.append(r"\item " + item_text)
        return "\n\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n"
    if name == "table":
        return "\n" + render_html_table(node) + "\n"
    if name in {"thead", "tbody", "tr", "td", "th", "div", "span"}:
        return "".join(render_html_fragment(child) for child in node.children)

    return "".join(render_html_fragment(child) for child in node.children)


def html_to_tex(input_text):
    if not input_text:
        return ""

    input_text = normalize_tex_list_environments(input_text)

    if "<" not in input_text and "&" not in input_text:
        return input_text

    soup = bs4.BeautifulSoup(input_text, "html.parser")
    rendered = "".join(render_html_fragment(child) for child in soup.contents)
    rendered = normalize_tex_list_environments(rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def tex_escape_text(value):
    if value is None:
        return ""

    text = str(value)
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def tex_escape_code_text(value):
    text = tex_escape_text(value)
    text = text.replace("$", r"\$")
    text = text.replace("^", r"\^{}")
    return text


def format_response_target_value(value):
    raw = "" if value is None else str(value)
    protected = protect_unresolved_algorithm_tokens(raw)
    if r"\texttt{[\$" in protected:
        return protected
    return r"\texttt{" + tex_escape_code_text(raw) + "}"


def clean_algorithm(input_text, pdf_values):
    # The JSON includes algorithmic variables that need replacing
    for variable_name, variable_value in pdf_values:
        input_text = re.sub(r"\$" + variable_name + r"(?!D|2)", str(variable_value), input_text)
        # Note requirement that expression is not followed by 'D'
        # Otherwise e.g. $TAD would be recognised as $TA.
    return input_text


def format_algorithm(input_text):
    replacements = [
        (r"\$", r""),
        (r";", r";}\\newline\\text{"),
    ]

    for pattern, replacement in replacements:
        input_text = re.sub(pattern, replacement, input_text)
    return input_text


def split_algorithm_commands(input_text):
    if not input_text:
        return []

    commands = []
    for line in str(input_text).splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue

        fragments = [fragment.strip() for fragment in stripped_line.split(";")]
        for fragment in fragments:
            if fragment:
                commands.append(fragment + ";")

    return commands


def resolve_pdf_heading(config, profile_name=None):
    _, profile_pdf_config = resolve_pdf_profile(config, profile_name)
    pdf_config = config.get("pdf", {}) if isinstance(config, dict) else {}
    headings = pdf_config.get("headings", {}) if isinstance(pdf_config, dict) else {}
    selected_profile = profile_pdf_config.get("heading", "problem_sets")

    if selected_profile not in headings:
        available_profiles = ", ".join(sorted(headings)) or "none"
        raise ValueError(
            f"Unknown PDF heading profile '{selected_profile}'. "
            f"Available profiles: {available_profiles}"
        )

    return selected_profile, headings[selected_profile]


def render_header_template(template_text, heading_config):
    section_label = str(heading_config.get("section_label", r"Nobius Sheet \#"))
    if section_label.strip():
        section_display_label = section_label + r"\thesection ~---"
        section_titlesep = "0.5 em"
    else:
        section_display_label = ""
        section_titlesep = "0 em"

    replacements = {
        "__NOBIUS_SECTION_DISPLAY_LABEL__": section_display_label,
        "__NOBIUS_SECTION_TITLESEP__": section_titlesep,
    }

    rendered = template_text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    return rendered


def shorten_footer_title(title, max_words=4):
    words = str(title or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + " ..."


def build_footer_mark(sheet_name, heading_config):
    short_title = shorten_footer_title(sheet_name)
    prefix = str(heading_config.get("footer_label", "") or "").strip()
    escaped_title = tex_escape_text(short_title)

    if prefix:
        suffix = "." if not prefix.endswith((".", "!", "?", ":")) else ""
        return f"{prefix}{suffix} {escaped_title}"
    return escaped_title


def apply_algorithm_values(text, content):
    if "algorithm" in content and "PDF_values" in content:
        return clean_algorithm(text, content["PDF_values"])
    return text


def normalize_inline_tex_math(text):
    if not text:
        return text

    return re.sub(
        r"(?:(?<=^)|(?<=[\s(\[{]))\$(?!\$)(.+?)(?<!\$)\$(?=(?:[\s\\\.,;:!?\)\]}]|$))",
        lambda match: r"\(" + match.group(1).strip() + r"\)",
        text,
        flags=re.S,
    )


def preprocess_tex_like_text(text):
    if not text:
        return text

    lines = []
    for line in str(text).splitlines():
        if line.lstrip().startswith("%"):
            continue
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\\d(?=\s*[A-Za-z({])", r"\\mathrm{d}", text)
    text = re.sub(r"([A-Za-z])\$\^(\{[^}]+\}|[^$]+)\$", r"\1\\(^\2\\)", text)
    return text


def tex_graphics_path(path):
    if not path:
        return path

    normalized = str(path).replace("\\", "/")
    if "/" in normalized or normalized.startswith("."):
        return normalized
    return "../media/" + normalized


def prefix_includegraphics_paths(text):
    if not text:
        return text

    pattern = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")

    def replace(match):
        return match.group(1) + tex_graphics_path(match.group(2)) + match.group(3)

    return pattern.sub(replace, text)


def inline_worked_solution_figures(text):
    if not text:
        return text

    figure_pattern = re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.S)

    def replace(match):
        body = match.group(1)
        images = re.findall(r"(\\includegraphics(?:\[[^\]]*\])?\{[^}]+\})", body)
        images = [prefix_includegraphics_paths(image) for image in images]
        caption_match = re.search(r"\\caption(?:\[[^\]]*\])?\{(.*?)\}", body, re.S)
        labels = re.findall(r"\\label\{([^}]+)\}", body)

        lines = [r"\par\begin{center}", r"\refstepcounter{figure}"]
        lines.extend(images)

        caption_text = caption_match.group(1).strip() if caption_match else ""
        if caption_text:
            lines.append(r"\par\small\textit{Figure \thefigure: " + caption_text + "}")

        for label in labels:
            lines.append(r"\label{" + label + "}")

        lines.append(r"\end{center}\par")
        return "\n".join(lines)

    return figure_pattern.sub(replace, text)


def make_tex_label_namespace(value):
    if value is None:
        return "nobius"

    namespace = re.sub(r"[^A-Za-z0-9]+", "-", str(value)).strip("-").lower()
    return namespace or "nobius"


def namespace_tex_labels(text, namespace):
    if not text or not namespace:
        return text

    commands = ("label", "ref", "eqref", "pageref", "autoref", "nameref")

    def replace(match):
        command = match.group(1)
        label = match.group(2)
        return "\\" + command + "{" + namespace + ":" + label + "}"

    pattern = r"\\(" + "|".join(commands) + r")\{([^}]+)\}"
    return re.sub(pattern, replace, text)


def protect_unresolved_algorithm_tokens(text):
    if not text:
        return text

    text = normalize_inline_tex_math(text)

    return re.sub(
        r"(?<!\\)\$([A-Za-z][A-Za-z0-9_]*)",
        lambda match: r"\texttt{[\$" + match.group(1) + "]}",
        text,
    )


def write_media_block(file_obj, media):
    if not media:
        return

    file_obj.write(r"\begin{center}")
    for pic in media:
        if pic[-3:] in ["jpg", "png", "pdf"]:
            file_obj.write("\\includegraphics[clip=true,height=0.5\\textwidth]{" + tex_graphics_path(pic) + "}\\\\")
    file_obj.write(r"\end{center}")


def render_custom_response_layout(part):
    custom_response = part.get("custom_response")
    if not isinstance(custom_response, dict):
        return ""

    layout = custom_response.get("layout")
    if not layout:
        return ""

    placeholder = r"\fbox{\strut\hspace{1.5em}}"
    layout = re.sub(r"<\d+>", lambda _: placeholder, layout)
    return html_to_tex(layout)


def write_choice_block(file_obj, part, content):
    if "response" not in part:
        return

    response = part.get("response")
    if not isinstance(response, dict):
        return

    mode = response.get("mode", "")
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return

    if "Choice" not in mode and "Selection" not in mode:
        return

    file_obj.write("\\begin{itemize}")
    for choice in choices:
        choice_tex = html_to_tex(choice)
        choice_tex = apply_algorithm_values(choice_tex, content)
        choice_tex = protect_unresolved_algorithm_tokens(choice_tex)
        file_obj.write("\\item " + choice_tex)
    file_obj.write("\\end{itemize}")


def part_has_choice_response(part):
    response = part.get("response")
    if not isinstance(response, dict):
        return False

    mode = response.get("mode", "")
    return "Choice" in mode or "Selection" in mode or mode == "True False"


def write_worked_solutions(file_obj, part, label_namespace=None, heading="Worked Solution:\\\\"):
    if "worked_solutions" not in part:
        return

    if heading:
        file_obj.write("\n\\par\\noindent " + heading + "\\par\n")
    for step in part["worked_solutions"]:
        if not isinstance(step, dict):
            continue
        write_media_block(file_obj, step.get("media", []))
        if "text" in step:
            step_text = preprocess_tex_like_text(step["text"])
            step_text = namespace_tex_labels(step_text, label_namespace)
            step_text = prefix_includegraphics_paths(step_text)
            step_text = inline_worked_solution_figures(step_text)
            step_text = html_to_tex(step_text)
            step_text = protect_unresolved_algorithm_tokens(step_text)
            file_obj.write(step_text + "\n\\par\n")


def write_final_answer(file_obj, part, label):
    if "final_answer" not in part:
        return

    file_obj.write("\n\\par\\noindent " + label + "\\par\n")
    write_media_block(file_obj, part["final_answer"].get("media", []))
    if "text" in part["final_answer"]:
        final_answer_text = preprocess_tex_like_text(part["final_answer"]["text"])
        final_answer_text = html_to_tex(final_answer_text)
        final_answer_text = protect_unresolved_algorithm_tokens(final_answer_text)
        file_obj.write(final_answer_text)


def count_nested_media(items):
    return sum(len(item.get("media", [])) for item in items if isinstance(item, dict))


def summarize_response_modes(part):
    if "response" in part:
        response = part["response"]
        if isinstance(response, dict):
            return tex_escape_text(response.get("mode", "response"))
        return "response"

    if "responses" in part:
        responses = [response.get("mode", "response") for response in part["responses"] if isinstance(response, dict)]
        if responses:
            return tex_escape_text(", ".join(responses))
        return f"{len(part['responses'])} responses"

    if "custom_response" in part:
        custom_response = part["custom_response"]
        responses = custom_response.get("responses", []) if isinstance(custom_response, dict) else []
        modes = [response.get("mode", "response") for response in responses if isinstance(response, dict)]
        if modes:
            return tex_escape_text("custom: " + ", ".join(modes))
        return "custom response"

    return "none"


def extract_marks_from_text(text):
    if not text:
        return 0

    total = 0
    for match in re.findall(r"(\d+(?:\.\d+)?)\s*MARKS?", str(text), flags=re.IGNORECASE):
        try:
            total += float(match)
        except ValueError:
            continue
    return total


def compute_part_marks(part):
    if not isinstance(part, dict):
        return 0

    total = extract_marks_from_text(part.get("statement"))
    total += extract_marks_from_text(part.get("post_response_text"))

    for response_block in part.get("responses", []):
        if isinstance(response_block, dict):
            total += extract_marks_from_text(response_block.get("post_response_text"))

    return total


def format_marks_total(value):
    if int(value) == value:
        return str(int(value))
    return str(value)


def get_part_mark_breakdown(part):
    if not isinstance(part, dict):
        return 0, "0"

    segments = []

    statement_marks = extract_marks_from_text(part.get("statement"))
    if statement_marks:
        segments.append(("r1", statement_marks))

    direct_marks = extract_marks_from_text(part.get("post_response_text"))
    if direct_marks:
        segments.append((f"r{len(segments) + 1}", direct_marks))

    response_blocks = part.get("responses", [])
    if isinstance(response_blocks, list):
        for response_block in response_blocks:
            if not isinstance(response_block, dict):
                continue
            response_marks = extract_marks_from_text(response_block.get("post_response_text"))
            if response_marks:
                segments.append((f"r{len(segments) + 1}", response_marks))

    total = sum(value for _, value in segments)
    if not segments:
        return 0, "0"

    breakdown = ", ".join(f"{label}={format_marks_total(value)}" for label, value in segments)
    return total, breakdown


def write_review_metadata(file_obj, question_filename, content):
    parts = content.get("parts", [])
    icon_data = content.get("icon_data", {})
    modes = [summarize_response_modes(part) for part in parts if isinstance(part, dict)]
    par_time = icon_data.get("par_time")
    par_time_text = f"{par_time[0]}--{par_time[1]} min" if isinstance(par_time, list) and len(par_time) == 2 else "n/a"
    difficulty_text = icon_data.get("difficulty", "n/a")
    total_marks = sum(compute_part_marks(part) for part in parts if isinstance(part, dict))
    response_summary = tex_escape_text(" | ".join(modes)) if modes else "none"

    file_obj.write(r"\begin{exobox}{Review metadata}")
    file_obj.write("\n\\small\n")
    file_obj.write(r"\begin{tabularx}{\linewidth}{@{}lX lX@{}}")
    file_obj.write("\n")
    file_obj.write(r"\textbf{File} & " + tex_escape_text(f"{question_filename}.json"))
    file_obj.write(r" & \textbf{UID} & " + tex_escape_text(content.get("uid", "n/a")) + r"\\")
    file_obj.write("\n")
    file_obj.write(r"\textbf{Parts} & " + str(len(parts)))
    file_obj.write(r" & \textbf{Responses} & " + response_summary + r"\\")
    file_obj.write("\n")
    file_obj.write(r"\textbf{Difficulty} & " + tex_escape_text(difficulty_text))
    file_obj.write(r" & \textbf{Par time} & " + tex_escape_text(par_time_text) + r"\\")
    file_obj.write("\n")
    file_obj.write(r"\textbf{Total marks} & " + tex_escape_text(format_marks_total(total_marks)))
    file_obj.write(r" & & \\")
    file_obj.write("\n")
    file_obj.write(r"\end{tabularx}")
    file_obj.write("\n\\end{exobox}\n")


def write_review_part_metadata(file_obj, part, part_index):
    mode_summary = summarize_response_modes(part)
    part_marks_total, part_marks_breakdown = get_part_mark_breakdown(part)

    file_obj.write(r"\begin{cbox}")
    file_obj.write("\n\\small ")
    file_obj.write(
        rf"\textbf{{Part ({chr(97 + part_index)}) metadata}} "
        + rf"marks={format_marks_total(part_marks_total)} "
        + rf"({part_marks_breakdown}); "
        + rf"response={mode_summary}"
    )
    file_obj.write("\n\\end{cbox}\n")


def summarize_numeric_grading(response):
    grading = response.get("grading", "n/a")
    details = [grading]

    if "perc" in response:
        details.append(f"perc={response['perc']}")
    if "tol" in response:
        details.append(f"tol={response['tol']}")
    if "dp" in response:
        details.append(f"dp={response['dp']}")
    if "sigd" in response:
        details.append(f"sigd={response['sigd']}")

    return ", ".join(str(item) for item in details)


def summarize_input_symbols(part):
    input_symbols = part.get("input_symbols", [])
    if not isinstance(input_symbols, list) or not input_symbols:
        return "n/a"

    pairs = []
    for symbol in input_symbols:
        if isinstance(symbol, list) and len(symbol) == 2:
            pairs.append(f"{symbol[1]}")

    return ", ".join(pairs) if pairs else "n/a"


def format_response_data_lines(response_wrapper, part):
    if not isinstance(response_wrapper, dict):
        return []

    response = response_wrapper.get("response", response_wrapper)
    if not isinstance(response, dict):
        return []

    mode = response.get("mode", "")
    lines = []

    if mode == "Numeric":
        answer = response.get("answer", {})
        if isinstance(answer, dict):
            lines.append(("Target", format_response_target_value(answer.get("num", "n/a")), False))
            units = answer.get("units")
            if units is not None:
                lines.append(("Units", tex_escape_text(str(units)), False))
        lines.append(("Grading", tex_escape_text(summarize_numeric_grading(response)), False))
    elif mode == "Maple":
        maple_answer = response.get("mapleAnswer", "n/a")
        lines.append(("Accepted expr", tex_escape_code_text(str(maple_answer)), True))
        maple_grader = response.get("maple")
        if maple_grader:
            lines.append(("Grader", tex_escape_code_text(str(maple_grader)), True))
        lines.append(("Symbols", tex_escape_text(summarize_input_symbols(part)), False))
    elif "Choice" in mode or "Selection" in mode or mode == "True False":
        answer = response.get("answer", "n/a")
        lines.append(("Answer", tex_escape_text(str(answer)), False))
        choices = response.get("choices", [])
        if isinstance(choices, list):
            lines.append(("Choices", tex_escape_text(str(len(choices))), False))
        display = response.get("display")
        if display is not None:
            lines.append(("Display", tex_escape_text(str(display)), False))
    elif mode == "List":
        answers = response.get("answers", [])
        if isinstance(answers, list):
            lines.append(("Answers", tex_escape_text(str(len(answers))), False))
        grader = response.get("grader")
        if grader:
            lines.append(("Grader", tex_escape_text(str(grader)), False))
        display = response.get("display")
        if display is not None:
            lines.append(("Display", tex_escape_text(str(display)), False))
    elif mode == "Essay":
        max_wordcount = response.get("maxWordcount", "n/a")
        lines.append(("Max words", tex_escape_text(str(max_wordcount)), False))
    elif mode == "Matching":
        matchings = response.get("matchings", [])
        if isinstance(matchings, list):
            lines.append(("Pairs", tex_escape_text(str(len(matchings))), False))
        format_info = response.get("format")
        if format_info is not None:
            lines.append(("Format", tex_escape_text(str(format_info)), False))
    elif mode == "Document Upload":
        for label, key in [
            ("Upload mode", "uploadMode"),
            ("Code type", "codeType"),
            ("Not graded", "notGraded"),
        ]:
            if key in response:
                lines.append((label, tex_escape_text(str(response.get(key))), False))
    elif mode:
        for label, key in [
            ("Answer", "answer"),
            ("Grading", "grading"),
            ("Display", "display"),
        ]:
            if key in response and response.get(key) is not None:
                lines.append((label, tex_escape_text(str(response.get(key))), False))
    return lines


def write_review_response_data(file_obj, part):
    response_wrappers = []
    if isinstance(part.get("response"), dict):
        response_wrappers.append(part["response"])
    if isinstance(part.get("responses"), list):
        response_wrappers.extend(
            response for response in part["responses"] if isinstance(response, dict)
        )
    custom_response = part.get("custom_response")
    if isinstance(custom_response, dict) and isinstance(custom_response.get("responses"), list):
        response_wrappers.extend(
            {"response": response}
            for response in custom_response["responses"]
            if isinstance(response, dict)
        )

    rendered_blocks = []
    for index, response_wrapper in enumerate(response_wrappers):
        lines = format_response_data_lines(response_wrapper, part)
        if not lines:
            continue

        response = response_wrapper.get("response", response_wrapper)
        mode = response.get("mode", "response")
        title = tex_escape_text(f"Response data ({mode})")
        if len(response_wrappers) > 1:
            title = tex_escape_text(f"Response data {index + 1} ({mode})")

        block_lines = [
            rf"\begin{{exobox}}{{{title}}}",
            r"\small",
        ]
        if "Choice" in mode or "Selection" in mode or mode == "True False":
            choices = response.get("choices", [])
            option_lines = []
            if isinstance(choices, list):
                for choice in choices:
                    choice_text = protect_unresolved_algorithm_tokens(
                        html_to_tex(choice if isinstance(choice, str) else str(choice))
                    )
                    choice_text = re.sub(r"\s+", " ", choice_text).strip()
                    if choice_text:
                        option_lines.append(choice_text)
            if option_lines:
                block_lines.append(r"\textbf{Answers}")
                block_lines.append(r"\begin{enumerate}[(1)]")
                for choice_text in option_lines:
                    block_lines.append(r"\item " + choice_text)
                block_lines.append(r"\end{enumerate}")

        block_lines.append(r"\begin{tabularx}{\linewidth}{@{}lX@{}}")
        for label, value, use_texttt in lines:
            rendered_value = r"\texttt{" + value + "}" if use_texttt else value
            block_lines.append(r"\textbf{" + tex_escape_text(label) + r"} & " + rendered_value + r"\\")
        block_lines.append(r"\end{tabularx}")
        block_lines.append(r"\end{exobox}")
        rendered_blocks.append("\n".join(block_lines))

    if rendered_blocks:
        file_obj.write("\n" + "\n".join(rendered_blocks) + "\n")


def write_review_algorithm_block(file_obj, content):
    if "algorithm" not in content:
        return

    file_obj.write(r"\begin{exobox}{Algorithm}")
    file_obj.write("\n\\small\n\\begin{Verbatim}\n")
    commands = split_algorithm_commands(content["algorithm"])
    if commands:
        file_obj.write("\n".join(commands))
    else:
        file_obj.write(str(content["algorithm"]))
    file_obj.write("\n\\end{Verbatim}\n\\end{exobox}\n")


def generate_pdf_output(tex_path, pdf_path):
    """
    Generate a PDF file from TeX using pdflatex.

    - output dir: pdflatex generates a lot of unwanted files, so we output
      everything to temp and copy the pdf over afterwards
    - interaction: batchmode will essentially suppress all the errors
      (not very nice for debugging)

    We have to move to the directory the tex_path is in so that images can be
    rendered properly.
    """
    print(f"[PDF] Getting reading to generate {os.path.basename(pdf_path)}")
    tex_path = os.path.abspath(tex_path)
    pdf_path = os.path.abspath(pdf_path)

    if shutil.which("pdflatex") is None:
        print("\033[91m[ERROR] pdflatex is not an executable on this system (check PATH and install)\033[0m")
        return

    initial_dir = os.getcwd()
    os.chdir(os.path.split(tex_path)[0])

    with tempfile.TemporaryDirectory() as temp_dir:
        args = [
            "pdflatex",
            f"-output-directory={temp_dir}",
            "-jobname=temp_pdf",
            "-interaction=batchmode",
            os.path.basename(tex_path),
        ]

        completed = None
        for _ in range(2):
            completed = subprocess.run(args, timeout=60, stdout=PIPE, stderr=PIPE)

        temp_pdf_path = os.path.join(temp_dir, "temp_pdf.pdf")
        if os.path.isfile(temp_pdf_path):
            shutil.move(temp_pdf_path, pdf_path)
            print(f"\033[92m[PDF] Success! Created {os.path.basename(pdf_path)} \033[0m")
        else:
            print("\033[91m[ERROR] Something went wrong with running pdflatex\033[0m")
            temp_log_path = os.path.join(temp_dir, "temp_pdf.log")
            if os.path.isfile(temp_log_path):
                print("\033[96m[PDF] Log available, print? [Y/N]: \033[0m", end="")
                if str(input()).lower() == "y":
                    with open(temp_log_path, "r", encoding="utf-8") as file:
                        for line in file.readlines():
                            print("\033[93m" + line.rstrip() + "\033[0m")
            else:
                print("\tLog file wasn't even created, printing CompletedProcess object")
                print(completed)

    os.chdir(initial_dir)


def import_pypdf2():
    from PyPDF2 import PdfFileMerger, PdfFileReader

    return PdfFileMerger, PdfFileReader


def generate_tex_output(
    sheet_dir,
    no_pdf,
    content_mode,
    pages_acc=None,
    tmp_merge_folder=None,
    config=None,
    profile_name=None,
):
    header_file = os.path.join(os.path.dirname(__file__), "resources", "latex", "header.tex")
    active_config = config
    if active_config is None:
        active_config, _ = load_config()
    selected_heading, heading_config = resolve_pdf_heading(active_config, profile_name)
    resolved_profile_name = resolve_profile_name(active_config, profile_name)
    is_exam_profile = resolved_profile_name == "exam"

    sheet_info = load_json_file(os.path.join(sheet_dir, "SheetInfo.json"))
    print(
        "[TEX] Generating outputs for "
        + str(len(sheet_info["questions"]))
        + " questions in Set "
        + os.path.basename(sheet_dir)
        + ' "'
        + sheet_info["name"]
        + '"...'
    )

    os.makedirs(os.path.join(sheet_dir, "media"), exist_ok=True)

    suffix_map = {
        "questions": "",
        "review": "_review",
        "solutions": "_solutions",
    }
    suffix = suffix_map[content_mode]

    render_dir = os.path.join(sheet_dir, "renders")
    os.makedirs(render_dir, exist_ok=True)

    outputfile_tex = os.path.join(render_dir, sheet_info["name"] + suffix + ".tex")
    if tmp_merge_folder:
        outputfile_pdf = os.path.join(tmp_merge_folder, sheet_info["name"] + suffix + ".pdf")
    else:
        outputfile_pdf = os.path.join(render_dir, sheet_info["name"] + suffix + ".pdf")

    with open(outputfile_tex, "w", encoding="utf-8") as file:
        with open(header_file, "r", encoding="utf-8") as header:
            header_text = header.read()
        file.write(render_header_template(header_text, heading_config))

        if pages_acc:
            file.write(r"\setcounter{page}{" + str(pages_acc + 1) + "}")

        file.write("\\ETrule")
        footer_mark = build_footer_mark(sheet_info["name"], heading_config)
        if is_exam_profile:
            file.write("\\section*{" + sheet_info["name"] + "}")
            file.write("\\setcounter{section}{0}")
            file.write("\\nobiussetmark{" + footer_mark + "}")
        else:
            file.write("\\setcounter{section}{" + str(sheet_info["number"] - 1) + "}")
            file.write("\\section{" + sheet_info["name"] + "}")
            file.write("\\nobiussetmark{" + footer_mark + "}")
        if content_mode != "review":
            file.write(
                "\\ETrule Note: this sheet was automatically generated from the online version. "
                "Not all content translates to the offline version, please visit the online version, "
                "accessible via BB, for full content."
            )

        for question_index in range(len(sheet_info["questions"])):
            question_filename = sheet_info["questions"][question_index]
            content = load_json_file(os.path.join(sheet_dir, question_filename + ".json"))
            label_namespace = make_tex_label_namespace(question_filename)

            file.write("")
            file.write("\\ETrule")
            heading_command = r"\section{" if is_exam_profile else r"\subsection{"
            file.write(heading_command)
            file.write(content["title"])
            file.write("}\n")

            if content_mode == "review":
                write_review_metadata(file, question_filename, content)

            if content_mode in ["questions", "review"]:
                new_master = html_to_tex(content["master_statement"])
                new_master = apply_algorithm_values(new_master, content)
                new_master = protect_unresolved_algorithm_tokens(new_master)
                file.write(new_master)
                write_media_block(file, content.get("media", []))

            num_parts = len(content["parts"])
            if num_parts > 1:
                file.write(r"\begin{enumerate}[(a)]")
            for part_index in range(num_parts):
                if num_parts > 1:
                    file.write("\\item ")
                part = content["parts"][part_index]

                if content_mode == "review":
                    write_review_part_metadata(file, part, part_index)

                if content_mode in ["questions", "review"]:
                    new_content = html_to_tex(part["statement"])
                    new_content = apply_algorithm_values(new_content, content)
                    new_content = protect_unresolved_algorithm_tokens(new_content)
                    file.write(new_content)
                    custom_response_layout = render_custom_response_layout(part)
                    if custom_response_layout:
                        file.write(custom_response_layout)
                    if "latex_only" in part:
                        file.write(part["latex_only"])
                    if content_mode != "review" or not part_has_choice_response(part):
                        write_choice_block(file, part, content)

                if content_mode == "review":
                    write_review_response_data(file, part)

                if content_mode == "review":
                    write_worked_solutions(file, part, label_namespace)
                    write_final_answer(file, part, r"Final Answer:\\")
                elif content_mode == "solutions":
                    write_worked_solutions(file, part, label_namespace, heading=None)
                    write_final_answer(file, part, r"Solution:\\")

            if num_parts > 1:
                file.write("\\end{enumerate}")

            if content_mode == "review":
                write_review_algorithm_block(file, content)

        file.write("\\ETrule\\end{document}")

    print(
        f"[TEX] Sheet tex compiled and saved to {sheet_info['name']}{suffix}.tex "
        f"(heading={selected_heading})"
    )

    if not no_pdf:
        generate_pdf_output(outputfile_tex, outputfile_pdf)

    return outputfile_pdf


def main():
    parser = argparse.ArgumentParser(description="Export PDF-oriented output from a Nobius sheet")
    parser.add_argument("--sheet-path", "-s", help="Path to the Sheet folder (if the -batch flag is set, this is interpreted as a directory containing multiple sheet folders)", required=True)
    parser.add_argument("--no-pdf", help="Set this flag to disable converting the rendered .tex file into a PDF", action="store_true")
    parser.add_argument("--batch-mode", "-b", help="Set this flag to render multiple sheets at once", action="store_true")
    parser.add_argument("--content-mode", choices=["questions", "review", "solutions"], default="questions", help="Select whether to render question sheets, review sheets, or solutions sheets")
    parser.add_argument("--config", help="Path to Nobius config JSON. Defaults to Nobius/nobius.json")
    parser.add_argument("--profile", help="Named Nobius profile controlling PDF defaults. Defaults to the config's default_profile.")
    args = parser.parse_args()
    config, _ = load_config(args.config)

    if not args.batch_mode:
        print(f"[INIT] Starting export_pdf with sheet {os.path.basename(args.sheet_path)} (pdf_write={bool(args.no_pdf)}) (batchmode=False) (content_mode={args.content_mode})")
        generate_tex_output(
            args.sheet_path,
            args.no_pdf,
            args.content_mode,
            config=config,
            profile_name=args.profile,
        )
    elif not args.no_pdf:
        print(f"[INIT] Starting export_pdf with sheets in {os.path.basename(args.sheet_path)} (pdf_write={bool(args.no_pdf)}) (batchmode=True) (content_mode={args.content_mode})")
        PdfFileMerger, PdfFileReader = import_pypdf2()
        sheets = get_batch_sheet_directories(args.sheet_path)

        print("[INIT] Going to render the following sheets in a temporary directory before merging.")
        print(f"└───{os.path.basename(args.sheet_path)}", end="")
        print("\n    ├─── " + "\n    ├─── ".join(sheets[:-1]), end="")
        print(f"\n    └─── {sheets[-1]}\n")

        with tempfile.TemporaryDirectory() as tmp_merge_folder:
            print(f"[DEBUG] Temp dir is in {tmp_merge_folder}")
            rendered_pdfs = []
            pages_acc = 0
            for sheet in sheets:
                new_pdf = generate_tex_output(
                    os.path.join(args.sheet_path, sheet),
                    args.no_pdf,
                    args.content_mode,
                    pages_acc,
                    tmp_merge_folder,
                    config=config,
                    profile_name=args.profile,
                )
                pages_acc += PdfFileReader(new_pdf).numPages
                rendered_pdfs.append(new_pdf)

            print(f"[PDF Merge] Merging {len(rendered_pdfs)} rendered PDFs")
            merged_file = PdfFileMerger()
            for pdf in rendered_pdfs:
                merged_file.append(PdfFileReader(pdf, "rb"))

        merged_suffix = "" if args.content_mode == "questions" else f"_{args.content_mode}"
        merged_file.write(os.path.join(args.sheet_path, f"MergedSheets{merged_suffix}.pdf"))
        print(f"\033[92m[PDF Merge] Merged all rendered PDFs Successfully! ({len(sheets)} accross {pages_acc} pages)\033[0m")
    else:
        print("[ERROR] Both Batchmode and No_PDF were set - currently batchmode merging requires individual pdfs to be created")
        print("[ERROR] Render .tex files for each sheet instead (no merging or pdf) (Y/N)? ", end="")
        if str(input()).lower() == "y":
            sheets = get_batch_sheet_directories(args.sheet_path)

            print("[INIT] Going to render the following sheets to their respective 'renders' folder.")
            print(f"└───{os.path.basename(args.sheet_path)}", end="")
            print("\n    ├─── " + "\n    ├─── ".join(sheets[:-1]), end="")
            print(f"\n    └─── {sheets[-1]}\n")

            for sheet in sheets:
                generate_tex_output(
                    os.path.join(args.sheet_path, sheet),
                    args.no_pdf,
                    args.content_mode,
                    config=config,
                    profile_name=args.profile,
                )


if __name__ == "__main__":
    main()
