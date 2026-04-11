"""
Tests for pdf_latex.generate_pdf_output.

pdflatex is not required to be installed for these tests — all subprocess
calls and filesystem side-effects are intercepted via unittest.mock so the
tests run cleanly in any environment.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pdf_latex import generate_pdf_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_completed_process():
    proc = MagicMock(spec=subprocess.CompletedProcess)
    return proc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generate_pdf_output_prints_error_when_pdflatex_not_on_path(tmp_path, capsys):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}\\end{document}", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    with patch("shutil.which", return_value=None):
        generate_pdf_output(str(tex_path), str(pdf_path))

    captured = capsys.readouterr()
    assert "pdflatex is not an executable" in captured.out
    assert not pdf_path.exists()


def test_generate_pdf_output_moves_pdf_to_destination_on_success(tmp_path, capsys):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "output" / "sheet.pdf"
    pdf_path.parent.mkdir()

    def fake_run(args, **kwargs):
        # On the second call (the real pass), create the temp PDF.
        temp_dir = next(a for a in args if a.startswith("-output-directory=")).split("=", 1)[1]
        (Path(temp_dir) / "temp_pdf.pdf").write_bytes(b"%PDF-stub")
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        generate_pdf_output(str(tex_path), str(pdf_path))

    captured = capsys.readouterr()
    assert "Success" in captured.out
    assert pdf_path.exists()
    assert pdf_path.read_bytes() == b"%PDF-stub"


def test_generate_pdf_output_prints_error_and_copies_log_on_failure(tmp_path, capsys):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    def fake_run(args, **kwargs):
        # Write a log but never a PDF — simulates a compilation failure.
        temp_dir = next(a for a in args if a.startswith("-output-directory=")).split("=", 1)[1]
        (Path(temp_dir) / "temp_pdf.log").write_text("! LaTeX Error: stub.", encoding="utf-8")
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        generate_pdf_output(str(tex_path), str(pdf_path))

    captured = capsys.readouterr()
    assert "Something went wrong" in captured.out
    assert "Wrote LaTeX log" in captured.out

    failure_log = tmp_path / "sheet.log"
    assert failure_log.exists()
    assert "LaTeX Error" in failure_log.read_text(encoding="utf-8")
    assert not pdf_path.exists()


def test_generate_pdf_output_prints_error_without_log_when_log_also_missing(tmp_path, capsys):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    def fake_run(args, **kwargs):
        # Neither PDF nor log produced — pdflatex didn't even start properly.
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        generate_pdf_output(str(tex_path), str(pdf_path))

    captured = capsys.readouterr()
    assert "Something went wrong" in captured.out
    assert "Log file wasn't even created" in captured.out
    assert not pdf_path.exists()


def test_generate_pdf_output_runs_pdflatex_twice(tmp_path):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    run_calls = []

    def fake_run(args, **kwargs):
        run_calls.append(args)
        temp_dir = next(a for a in args if a.startswith("-output-directory=")).split("=", 1)[1]
        (Path(temp_dir) / "temp_pdf.pdf").write_bytes(b"%PDF-stub")
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        generate_pdf_output(str(tex_path), str(pdf_path))

    assert len(run_calls) == 2, "pdflatex must be invoked exactly twice for cross-reference resolution"
    assert run_calls[0] == run_calls[1], "both pdflatex invocations should use identical arguments"
