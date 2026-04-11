import json
import subprocess
import sys

from export_pdf import (
    build_footer_mark,
    compute_part_marks,
    extract_marks_from_text,
    generate_tex_output,
    get_part_mark_breakdown,
    get_batch_sheet_directories,
    html_to_tex,
    inline_worked_solution_figures,
    namespace_tex_labels,
    protect_unresolved_algorithm_tokens,
    resolve_pdf_heading,
    split_algorithm_commands,
)

from .conftest import REPO_ROOT, create_named_sheet_fixture


def test_generate_pdf_from_json_surfaces_json_decode_error_without_nameerror(tmp_path):
    sheet_dir = tmp_path / "bad_pdf_sheet"
    media_dir = sheet_dir / "media"
    sheet_dir.mkdir()
    media_dir.mkdir()

    (sheet_dir / "SheetInfo.json").write_text("{ invalid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "export_pdf.py",
            "--sheet-path",
            str(sheet_dir),
            "--no-pdf",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode != 0
    assert "JSONDecodeError" in combined_output
    assert "NameError" not in combined_output


def test_get_batch_sheet_directories_uses_sheetinfo_number_order(tmp_path):
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()

    for folder_name, sheet_number, sheet_name in [
        ("z_sheet", 3, "Later Sheet"),
        ("a_sheet", 2, "Middle Sheet"),
        ("m_sheet", 1, "First Sheet"),
    ]:
        sheet_dir = batch_dir / folder_name
        sheet_dir.mkdir()
        (sheet_dir / "SheetInfo.json").write_text(
            json.dumps({"number": sheet_number, "name": sheet_name, "questions": []}),
            encoding="utf-8",
        )

    ordered = get_batch_sheet_directories(str(batch_dir))

    assert ordered == ["m_sheet", "a_sheet", "z_sheet"]


def test_generate_review_tex_includes_compact_metadata_blocks(t01_sheet):
    generate_tex_output(str(t01_sheet), True, "review")

    tex_path = t01_sheet / "renders" / "Fundamentals_review.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert r"\begin{exobox}{Review metadata}" in tex_content
    assert r"\textbf{File} & Starter.json" in tex_content
    assert r"\textbf{UID} &" in tex_content
    assert r"\textbf{Total marks} & 0" in tex_content
    assert r"\textbf{Part (a) metadata}" in tex_content
    assert r"\begin{exobox}{Algorithm}" not in tex_content
    assert "Note: this sheet was automatically generated from the online version." not in tex_content


def test_generate_questions_tex_keeps_online_version_note(t01_sheet):
    generate_tex_output(str(t01_sheet), True, "questions", profile_name="problem_set")

    tex_path = t01_sheet / "renders" / "Fundamentals.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert "Note: this sheet was automatically generated from the online version." in tex_content


def test_generate_exam_questions_tex_omits_online_version_note(t01_sheet):
    generate_tex_output(str(t01_sheet), True, "questions", profile_name="exam")

    tex_path = t01_sheet / "renders" / "Fundamentals.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert "Note: this sheet was automatically generated from the online version." not in tex_content


def test_generate_solutions_tex_omits_worked_solution_label_but_keeps_content_and_solution_label(t01_sheet):
    generate_tex_output(str(t01_sheet), True, "solutions")

    tex_path = t01_sheet / "renders" / "Fundamentals_solutions.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert "Worked Solution:" not in tex_content
    assert "Again consider a horizontal slice of thickness" in tex_content
    assert r"Solution:\\" in tex_content


def test_generate_tex_uses_heading_profile_from_config(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    config_path.write_text(
        json.dumps(
            {
                "default_profile": "exam",
                "profiles": {
                    "exam": {
                        "pdf": {
                            "heading": "generic",
                        }
                    }
                },
                "pdf": {
                    "headings": {
                        "generic": {
                            "footer_label": r"QA Sheet \#",
                            "section_label": r"QA Pack \#",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "export_pdf.py",
            "--sheet-path",
            str(t01_sheet),
            "--no-pdf",
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0

    tex_path = t01_sheet / "renders" / "Fundamentals.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert r"\lfoot{\nouppercase{\leftmark}}" in tex_content
    assert r"\nobiussetmark{QA Sheet \#. Fundamentals}" in tex_content
    assert r"{QA Pack \#\thesection ~---}{0.5 em}{}" in tex_content


def test_generate_tex_omits_section_prefix_when_section_label_is_blank(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    config_path.write_text(
        json.dumps(
            {
                "default_profile": "exam",
                "profiles": {
                    "exam": {
                        "pdf": {
                            "heading": "generic",
                        }
                    }
                },
                "pdf": {
                    "headings": {
                        "generic": {
                            "footer_label": r"Exam",
                            "section_label": "",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "export_pdf.py",
            "--sheet-path",
            str(t01_sheet),
            "--no-pdf",
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0

    tex_path = t01_sheet / "renders" / "Fundamentals.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert r"{QA Pack \#\thesection ~---}{0.5 em}{}" not in tex_content
    assert r"{}{0 em}{}" in tex_content
    assert r"\section*{Fundamentals}" in tex_content
    assert r"\nobiussetmark{Exam. Fundamentals}" in tex_content


def test_generate_exam_tex_uses_unnumbered_prefixed_headings_for_questions(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    config_path.write_text(
        json.dumps(
            {
                "default_profile": "exam",
                "profiles": {
                    "exam": {
                        "pdf": {
                            "heading": "exam",
                        }
                    }
                },
                "pdf": {
                    "headings": {
                        "exam": {
                            "footer_label": "CIVE40008 Fluid Mechanics I",
                            "section_label": "",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "export_pdf.py",
            "--sheet-path",
            str(t01_sheet),
            "--no-pdf",
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0

    tex_path = t01_sheet / "renders" / "Fundamentals.tex"
    tex_content = tex_path.read_text(encoding="utf-8")

    assert r"\section*{Fundamentals}" in tex_content
    assert r"\subsection{Fluids}" not in tex_content
    assert r"\section{Fluids}" not in tex_content
    assert r"\section*{CIVE40008 Fluid Mechanics I. Fluids}" in tex_content


def test_build_footer_mark_truncates_sheet_name_to_four_words():
    assert build_footer_mark("Very Long Problem Sheet Name Here", {"footer_label": ""}) == "Very Long Problem Sheet ..."
    assert build_footer_mark("Very Long Problem Sheet Name Here", {"footer_label": "CIVE40008"}) == "CIVE40008. Very Long Problem Sheet ..."


def test_generate_tex_renders_standard_multiple_selection_choices(tmp_path):
    sheet_dir = create_named_sheet_fixture(
        tmp_path,
        "choices",
        {
            "name": "Choice Sheet",
            "questions": ["Q1"],
            "number": 1,
        },
        {
            "Q1": {
                "title": "Choice Question",
                "master_statement": "Pick all valid statements.",
                "parts": [
                    {
                        "statement": "Select the valid items:",
                        "response": {
                            "mode": "Multiple Selection",
                            "choices": [
                                "<p>First item</p>",
                                "<p>Second item</p>",
                            ],
                        },
                    }
                ],
            }
        },
    )

    generate_tex_output(str(sheet_dir), True, "questions")

    tex_content = (sheet_dir / "renders" / "Choice Sheet.tex").read_text(encoding="utf-8")

    assert r"\begin{itemize}" in tex_content
    assert r"\item First item" in tex_content
    assert r"\item Second item" in tex_content


def test_generate_tex_renders_custom_response_table_layout(t01_sheet):
    generate_tex_output(str(t01_sheet), True, "questions")

    tex_content = (t01_sheet / "renders" / "Fundamentals.tex").read_text(encoding="utf-8")

    assert r"\begin{tabularx}{\linewidth}" in tex_content
    assert r"\fbox{\strut\hspace{1.5em}}" in tex_content


def test_generate_review_tex_includes_numeric_and_maple_response_data(tmp_path):
    sheet_dir = create_named_sheet_fixture(
        tmp_path,
        "response_data",
        {
            "name": "Response Data Sheet",
            "questions": ["Q1"],
            "number": 1,
        },
        {
            "Q1": {
                "title": "Response Data Question",
                "master_statement": "Check review response metadata.",
                "parts": [
                    {
                        "statement": "Numeric part",
                        "response": {
                            "mode": "Numeric",
                            "answer": {"num": "12.5", "units": "m"},
                            "grading": "toler_perc",
                            "perc": 5.0,
                            "showUnits": True,
                            "numStyle": "thousands scientific",
                        },
                    },
                    {
                        "statement": "Maple part",
                        "response": {
                            "mode": "Maple",
                            "mapleAnswer": "Q^2/(2*g*b0^2*W^2)",
                            "maple": "Nobius:-GradePat($ANSWER, $RESPONSE);",
                        },
                        "input_symbols": [["\\(Q\\)", "Q"], ["\\(g\\)", "g"]],
                    },
                ],
            }
        },
    )

    generate_tex_output(str(sheet_dir), True, "review")

    tex_content = (sheet_dir / "renders" / "Response Data Sheet_review.tex").read_text(encoding="utf-8")

    assert r"\begin{exobox}{Response data (Numeric)}" in tex_content
    assert r"\begin{tabularx}{\linewidth}{@{}lX@{}}" in tex_content
    assert r"\textbf{Target} & \texttt{12.5}\\" in tex_content
    assert r"\textbf{Units} & m\\" in tex_content
    assert r"\textbf{Grading} & toler\_perc, perc=5.0\\" in tex_content
    assert r"\begin{exobox}{Response data (Maple)}" in tex_content
    assert r"\textbf{Accepted expr} & \texttt{Q\^{}2/(2*g*b0\^{}2*W\^{}2)}\\" in tex_content
    assert r"\textbf{Grader} & \texttt{" in tex_content
    assert r"\textbf{Symbols} & Q, g\\" in tex_content


def test_generate_review_tex_renders_multiple_choice_answers_above_data_table(tmp_path):
    sheet_dir = create_named_sheet_fixture(
        tmp_path,
        "mc_review",
        {
            "name": "MC Review Sheet",
            "questions": ["Q1"],
            "number": 1,
        },
        {
            "Q1": {
                "title": "MC Review Question",
                "master_statement": "Inspect review response metadata.",
                "parts": [
                    {
                        "statement": "Choose one option.",
                        "response": {
                            "mode": "Multiple Choice",
                            "answer": "2",
                            "choices": [
                                "<p>First option</p>",
                                "<p>Second option</p>",
                            ],
                            "display": "vertical",
                        },
                    }
                ],
            }
        },
    )

    generate_tex_output(str(sheet_dir), True, "review")

    tex_content = (sheet_dir / "renders" / "MC Review Sheet_review.tex").read_text(encoding="utf-8")

    assert r"\textbf{Answers}" in tex_content
    assert r"\begin{enumerate}" in tex_content
    assert r"\item First option" in tex_content
    assert r"\item Second option" in tex_content
    assert r"\textbf{Choices} & 2\\" in tex_content
    assert r"\textbf{Options} &" not in tex_content


def test_generate_review_tex_formats_numeric_variable_targets_like_placeholders(tmp_path):
    sheet_dir = create_named_sheet_fixture(
        tmp_path,
        "numeric_target",
        {
            "name": "Numeric Target Sheet",
            "questions": ["Q1"],
            "number": 1,
        },
        {
            "Q1": {
                "title": "Numeric Target Question",
                "master_statement": "Check numeric target formatting.",
                "parts": [
                    {
                        "statement": "Numeric variable part",
                        "response": {
                            "mode": "Numeric",
                            "answer": {"num": "$pA", "units": "Pa"},
                            "grading": "toler_perc",
                            "perc": 5.0,
                        },
                    }
                ],
            }
        },
    )

    generate_tex_output(str(sheet_dir), True, "review")

    tex_content = (sheet_dir / "renders" / "Numeric Target Sheet_review.tex").read_text(encoding="utf-8")

    assert r"\textbf{Target} & \texttt{[\$pA]}\\" in tex_content


def test_generate_review_tex_includes_choice_and_custom_response_data(tmp_path):
    sheet_dir = create_named_sheet_fixture(
        tmp_path,
        "choice_data",
        {
            "name": "Choice Data Sheet",
            "questions": ["Q1"],
            "number": 1,
        },
        {
            "Q1": {
                "title": "Choice Data Question",
                "master_statement": "Check non-numeric response metadata.",
                "parts": [
                    {
                        "statement": "Multiple selection part",
                        "response": {
                            "mode": "Multiple Selection",
                            "answer": "1,3",
                            "display": "vertical",
                            "choices": ["<p>A</p>", "<p>B</p>", "<p>C</p>"],
                        },
                    },
                    {
                        "statement": "Custom response part",
                        "custom_response": {
                            "layout": "<table><tr><td><1></td></tr></table>",
                            "responses": [
                                {
                                    "mode": "List",
                                    "answers": ["A", "B"],
                                    "display": {"display": "text", "permute": False},
                                    "grader": "regex",
                                }
                            ],
                        },
                    },
                ],
            }
        },
    )

    generate_tex_output(str(sheet_dir), True, "review")

    tex_content = (sheet_dir / "renders" / "Choice Data Sheet_review.tex").read_text(encoding="utf-8")

    assert r"\begin{exobox}{Response data (Multiple Selection)}" in tex_content
    assert r"\textbf{Answer} & 1,3\\" in tex_content
    assert r"\textbf{Choices} & 3\\" in tex_content
    assert r"\textbf{Answers}" in tex_content
    assert r"\begin{enumerate}[(1)]" in tex_content
    assert r"\item A" in tex_content
    assert r"\item B" in tex_content
    assert r"\item C" in tex_content
    assert r"\textbf{Options} &" not in tex_content
    assert r"\textbf{Display} & vertical\\" in tex_content
    assert r"Multiple selection part\begin{itemize}" not in tex_content
    assert r"\begin{exobox}{Response data (List)}" in tex_content
    assert r"\textbf{Answers} & 2\\" in tex_content
    assert r"\textbf{Grader} & regex\\" in tex_content


def test_protect_unresolved_algorithm_tokens_escapes_placeholder_like_text():
    protected = protect_unresolved_algorithm_tokens(r"Force is $F kN and area is $a cm^2")

    assert r"\texttt{[\$F]}" in protected
    assert r"\texttt{[\$a]}" in protected


def test_protect_unresolved_algorithm_tokens_preserves_inline_tex_math():
    protected = protect_unresolved_algorithm_tokens(
        r"if the wetted perimeter is $P$, the area $A = 0.5\times(P/2)^2$ and force is $F kN"
    )

    assert r"\(P\)" in protected
    assert r"\(A = 0.5\times(P/2)^2\)" in protected
    assert r"\texttt{[\$F]}" in protected


def test_protect_unresolved_algorithm_tokens_escapes_unmatched_currency_dollar_signs():
    protected = protect_unresolved_algorithm_tokens(
        "Assume an energy price of $0.12 per kilowatt-hour (kWh)."
    )

    assert r"\$0.12 per kilowatt-hour (kWh)." in protected


def test_protect_unresolved_algorithm_tokens_escapes_literal_percent_signs():
    protected = protect_unresolved_algorithm_tokens(
        "Assume that the pump efficiency is 90%."
    )

    assert r"90\%." in protected


def test_html_to_tex_converts_html_lists():
    converted = html_to_tex("<ol><li>First</li><li>Second</li></ol>")

    assert r"\begin{enumerate}" in converted
    assert r"\item First" in converted
    assert r"\item Second" in converted
    assert r"\end{enumerate}" in converted


def test_html_to_tex_converts_basic_tables():
    converted = html_to_tex(
        "<table><tr><th>Case</th><th>Value</th></tr><tr><td>A</td><td>1</td></tr></table>"
    )

    assert r"\begin{tabularx}{\linewidth}" in converted
    assert "Case & Value" in converted
    assert "A & 1" in converted


def test_html_to_tex_normalizes_latex_enumerate_label_syntax():
    converted = html_to_tex(r"\begin{enumerate} [label=\alph*)]\item A\end{enumerate}")

    assert r"\begin{enumerate}[(a)]" in converted


def test_html_to_tex_does_not_parse_plain_text_that_only_looks_like_a_locator():
    converted = html_to_tex(r"See figure <1> in file lock.png")

    assert converted == r"See figure <1> in file lock.png"


def test_mark_extraction_counts_statement_and_response_marks():
    assert extract_marks_from_text("degrees [8 MARKS]") == 8
    assert extract_marks_from_text("Draw the figure. [9 MARKS]") == 9

    marks = compute_part_marks(
        {
            "statement": "Draw carefully. [9 MARKS]",
            "responses": [
                {"post_response_text": "[2 MARKS]"},
                {"post_response_text": "degrees [4 MARKS]"},
            ],
        }
    )

    assert marks == 15


def test_part_mark_breakdown_reports_total_and_response_split():
    total, breakdown = get_part_mark_breakdown(
        {
            "statement": "Draw carefully. [9 MARKS]",
            "responses": [
                {"post_response_text": "[2 MARKS]"},
                {"post_response_text": "degrees [4 MARKS]"},
            ],
        }
    )

    assert total == 15
    assert breakdown == "r1=9, r2=2, r3=4"


def test_preprocess_tex_like_text_normalizes_tex_style_unit_exponents():
    from export_pdf import preprocess_tex_like_text

    processed = preprocess_tex_like_text(r"Q = 7.5 \times 10^{-4} m$^3$s$^{-1}$")

    assert r"m\(^3\)s\(^{-1}\)" in processed


def test_namespace_tex_labels_rewrites_labels_and_refs_consistently():
    namespaced = namespace_tex_labels(
        r"see \ref{fig:test}. \begin{figure}\caption{x}\label{fig:test}\end{figure} and \eqref{eq:1}",
        "question-1",
    )

    assert r"\ref{question-1:fig:test}" in namespaced
    assert r"\label{question-1:fig:test}" in namespaced
    assert r"\eqref{question-1:eq:1}" in namespaced


def test_inline_worked_solution_figures_flattens_floats_but_keeps_labels():
    flattened = inline_worked_solution_figures(
        r"see figure \ref{question-4:fig:test}"
        "\n\\begin{figure}[h!]\n\\centering\n"
        r"\includegraphics[width=10cm]{fig.png}"
        "\n\\caption{Energy and hydraulic grade lines}\n"
        r"\label{question-4:fig:test}"
        "\n\\end{figure}"
    )

    assert r"\begin{figure}" not in flattened
    assert r"\refstepcounter{figure}" in flattened
    assert r"\includegraphics[width=10cm]{../media/fig.png}" in flattened
    assert r"\textit{Figure \thefigure: Energy and hydraulic grade lines}" in flattened
    assert r"\label{question-4:fig:test}" in flattened


def test_split_algorithm_commands_breaks_maple_commands_onto_separate_lines():
    commands = split_algorithm_commands("  $f=range(100,300,1);$a=11\n$A=93;$F=$f*$A/$a;  ")

    assert commands == [
        "$f=range(100,300,1);",
        "$a=11;",
        "$A=93;",
        "$F=$f*$A/$a;",
    ]


def test_resolve_pdf_heading_rejects_unknown_profile():
    try:
        resolve_pdf_heading(
            {
                "default_profile": "exam",
                "profiles": {"exam": {"pdf": {"heading": "missing"}}},
                "pdf": {"headings": {}},
            }
        )
    except ValueError as error:
        assert "Unknown PDF heading profile" in str(error)
    else:
        raise AssertionError("resolve_pdf_heading should reject missing heading profiles")
