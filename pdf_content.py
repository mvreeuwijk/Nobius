# -*- coding: utf-8 -*-
"""
Nobius content-to-LaTeX writers and the top-level TeX generation orchestrator.

This module knows about Nobius JSON structures (parts, responses, algorithms,
worked solutions) and translates them into LaTeX.  Low-level text transforms
live in :mod:`pdf_tex` and :mod:`pdf_html`; pdflatex invocation lives in
:mod:`pdf_latex`.
"""

from __future__ import annotations

import os
import re
from typing import TextIO

from nobius_config import load_config, resolve_pdf_profile, resolve_profile_name
from pdf_html import html_to_tex
from pdf_latex import generate_pdf_output
from pdf_tex import (
    apply_algorithm_values,
    format_response_target_value,
    inline_worked_solution_figures,
    make_tex_label_namespace,
    namespace_tex_labels,
    prefix_includegraphics_paths,
    preprocess_tex_like_text,
    protect_unresolved_algorithm_tokens,
    split_algorithm_commands,
    tex_escape_code_text,
    tex_escape_text,
    tex_graphics_path,
)
from render_common import load_json_file


# ---------------------------------------------------------------------------
# PDF heading / section config
# ---------------------------------------------------------------------------


def resolve_pdf_heading(config: dict, profile_name: str | None = None) -> tuple[str, dict]:
    """Look up the heading config dict for *profile_name* in *config*.

    Returns ``(selected_heading_name, heading_config_dict)``.  Raises
    ``ValueError`` if the profile's nominated heading key is absent from
    ``config["pdf"]["headings"]``.
    """
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


def render_header_template(template_text: str, heading_config: dict) -> str:
    """Substitute Nobius placeholders in the LaTeX header template."""
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


def shorten_footer_title(title: object, max_words: int = 4) -> str:
    """Truncate *title* to *max_words* words, appending ``...`` if truncated."""
    words = str(title or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + " ..."


def build_footer_mark(sheet_name: str, heading_config: dict) -> str:
    """Build the footer mark string for a sheet."""
    short_title = shorten_footer_title(sheet_name)
    prefix = str(heading_config.get("footer_label", "") or "").strip()
    escaped_title = tex_escape_text(short_title)

    if prefix:
        suffix = "." if not prefix.endswith((".", "!", "?", ":")) else ""
        return f"{prefix}{suffix} {escaped_title}"
    return escaped_title


def build_exam_question_heading(question_title: object, heading_config: dict) -> str:
    """Build the section heading for an exam-mode question."""
    title = tex_escape_text(str(question_title or "").strip())
    prefix = str(heading_config.get("footer_label", "") or "").strip()
    if prefix:
        suffix = "." if not prefix.endswith((".", "!", "?", ":")) else ""
        return f"{prefix}{suffix} {title}"
    return title


# ---------------------------------------------------------------------------
# Media / choice / response layout writers
# ---------------------------------------------------------------------------


def write_media_block(file_obj: TextIO, media: list) -> None:
    """Write a centred ``\\includegraphics`` block for each image in *media*."""
    if not media:
        return

    file_obj.write(r"\begin{center}")
    for pic in media:
        if pic[-3:] in ["jpg", "png", "pdf"]:
            file_obj.write("\\includegraphics[clip=true,height=0.5\\textwidth]{" + tex_graphics_path(pic) + "}\\\\")
    file_obj.write(r"\end{center}")


def render_custom_response_layout(part: dict) -> str:
    """Return the LaTeX for a custom response layout, or empty string."""
    custom_response = part.get("custom_response")
    if not isinstance(custom_response, dict):
        return ""

    layout = custom_response.get("layout")
    if not layout:
        return ""

    placeholder = r"\fbox{\strut\hspace{1.5em}}"
    layout = re.sub(r"<\d+>", lambda _: placeholder, layout)
    return html_to_tex(layout)


def write_choice_block(file_obj: TextIO, part: dict, content: dict) -> None:
    """Write multiple-choice / selection options as a LaTeX ``itemize`` list."""
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


def part_has_choice_response(part: dict) -> bool:
    """Return ``True`` if the part uses a choice or True/False response mode."""
    response = part.get("response")
    if not isinstance(response, dict):
        return False

    mode = response.get("mode", "")
    return "Choice" in mode or "Selection" in mode or mode == "True False"


# ---------------------------------------------------------------------------
# Worked solutions / final answers
# ---------------------------------------------------------------------------


def write_worked_solutions(
    file_obj: TextIO,
    part: dict,
    label_namespace: str | None = None,
    heading: str = "Worked Solution:\\\\",
) -> None:
    """Write worked solution steps to *file_obj*."""
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


def write_final_answer(file_obj: TextIO, part: dict, label: str) -> None:
    """Write the final answer block to *file_obj*."""
    if "final_answer" not in part:
        return

    file_obj.write("\n\\par\\noindent " + label + "\\par\n")
    write_media_block(file_obj, part["final_answer"].get("media", []))
    if "text" in part["final_answer"]:
        final_answer_text = preprocess_tex_like_text(part["final_answer"]["text"])
        final_answer_text = html_to_tex(final_answer_text)
        final_answer_text = protect_unresolved_algorithm_tokens(final_answer_text)
        file_obj.write(final_answer_text)


# ---------------------------------------------------------------------------
# Marks extraction
# ---------------------------------------------------------------------------


def count_nested_media(items: list) -> int:
    """Return the total number of media items across a list of dicts."""
    return sum(len(item.get("media", [])) for item in items if isinstance(item, dict))


def extract_marks_from_text(text: object) -> float:
    """Sum all ``N MARK(S)`` patterns found in *text*."""
    if not text:
        return 0

    total = 0
    for match in re.findall(r"(\d+(?:\.\d+)?)\s*MARKS?", str(text), flags=re.IGNORECASE):
        try:
            total += float(match)
        except ValueError:
            continue
    return total


def compute_part_marks(part: dict) -> float:
    """Return the total marks declared in *part* across statement and responses."""
    if not isinstance(part, dict):
        return 0

    total = extract_marks_from_text(part.get("statement"))
    total += extract_marks_from_text(part.get("post_response_text"))

    for response_block in part.get("responses", []):
        if isinstance(response_block, dict):
            total += extract_marks_from_text(response_block.get("post_response_text"))

    return total


def format_marks_total(value: float) -> str:
    """Format a marks total as an integer string when it has no fractional part."""
    if int(value) == value:
        return str(int(value))
    return str(value)


def get_part_mark_breakdown(part: dict) -> tuple[float, str]:
    """Return ``(total_marks, breakdown_string)`` for *part*.

    The breakdown string lists per-source marks as ``r1=N, r2=M, …``.
    """
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


# ---------------------------------------------------------------------------
# Review-mode metadata writers
# ---------------------------------------------------------------------------


def summarize_response_modes(part: dict) -> str:
    """Return a pipe-separated summary of response modes in *part*."""
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


def write_review_metadata(file_obj: TextIO, question_filename: str, content: dict) -> None:
    """Write the top-level review metadata box for a question."""
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


def write_review_part_metadata(file_obj: TextIO, part: dict, part_index: int) -> None:
    """Write the per-part metadata box for a review sheet."""
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


def summarize_numeric_grading(response: dict) -> str:
    """Return a compact grading summary string for a Numeric response."""
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


def summarize_input_symbols(part: dict) -> str:
    """Return a comma-separated list of input symbol display names."""
    input_symbols = part.get("input_symbols", [])
    if not isinstance(input_symbols, list) or not input_symbols:
        return "n/a"

    pairs = []
    for symbol in input_symbols:
        if isinstance(symbol, list) and len(symbol) == 2:
            pairs.append(f"{symbol[1]}")

    return ", ".join(pairs) if pairs else "n/a"


def format_response_data_lines(response_wrapper: dict, part: dict) -> list[tuple[str, str, bool]]:
    """Return a list of ``(label, value, use_texttt)`` tuples for a response.

    Each tuple describes one row of the response data table in a review sheet.
    """
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


def write_review_response_data(file_obj: TextIO, part: dict) -> None:
    """Write all response data boxes for a part in review mode."""
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


def write_review_algorithm_block(file_obj: TextIO, content: dict) -> None:
    """Write the algorithm source block for a review sheet."""
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


# ---------------------------------------------------------------------------
# Top-level TeX generation
# ---------------------------------------------------------------------------


def generate_tex_output(
    sheet_dir: str | os.PathLike,
    no_pdf: bool,
    content_mode: str,
    pages_acc: int | None = None,
    tmp_merge_folder: str | os.PathLike | None = None,
    config: dict | None = None,
    profile_name: str | None = None,
) -> str:
    """Generate a ``.tex`` file (and optionally a PDF) for one Nobius sheet.

    Parameters
    ----------
    sheet_dir:
        Path to the sheet directory containing ``SheetInfo.json``.
    no_pdf:
        When ``True`` only the ``.tex`` file is written; pdflatex is skipped.
    content_mode:
        One of ``"questions"``, ``"review"``, or ``"solutions"``.
    pages_acc:
        Running page count for batch mode — sets ``\\setcounter{page}{…}`` so
        pages are continuous across merged PDFs.
    tmp_merge_folder:
        When set, the PDF is written here instead of into ``renders/``.
    config:
        Loaded Nobius config dict.  Defaults to :func:`nobius_config.load_config`.
    profile_name:
        Named profile override.  Defaults to the config's ``default_profile``.

    Returns
    -------
    str
        Path to the generated PDF (or where it would have been if *no_pdf*).
    """
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
        if content_mode != "review" and not is_exam_profile:
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
            if is_exam_profile:
                file.write(r"\section*{")
                file.write(build_exam_question_heading(content["title"], heading_config))
                file.write("}\n")
            else:
                file.write(r"\subsection{")
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
