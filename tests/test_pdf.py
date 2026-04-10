import json
import subprocess
import sys

from export_pdf import (
    generate_tex_output,
    get_batch_sheet_directories,
    inline_worked_solution_figures,
    namespace_tex_labels,
    protect_unresolved_algorithm_tokens,
    resolve_pdf_heading,
    split_algorithm_commands,
)

from .conftest import REPO_ROOT


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
    assert r"\textbf{Part (a) metadata}" in tex_content
    assert r"\begin{exobox}{Algorithm}" not in tex_content


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

    assert r"\lfoot{\ifnum0<\thesection QA Sheet \# \nouppercase{\leftmark}\fi}" in tex_content
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


def test_generate_exam_tex_uses_section_headings_for_questions(t01_sheet, tmp_path):
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
                            "footer_label": "",
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
    assert r"\section{Fluids}" in tex_content


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
