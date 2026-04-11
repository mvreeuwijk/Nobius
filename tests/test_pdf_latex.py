"""
Tests for pdf_latex.generate_pdf_output.

pdflatex is not required to be installed for these tests — all subprocess
calls and filesystem side-effects are intercepted via unittest.mock so the
tests run cleanly in any environment.

Each test passes ``work_dir=tmp_path / "work"`` so the function never writes
to the OS temporary directory.  This satisfies the requirement that
``generate_pdf_output`` works in restricted CI environments where the OS temp
tree may not be writable.
"""

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf_latex import generate_pdf_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_completed_process():
    return MagicMock(spec=subprocess.CompletedProcess)


def _make_work_dir(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    return work


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generate_pdf_output_returns_false_when_pdflatex_not_on_path(tmp_path, caplog):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    with patch("shutil.which", return_value=None):
        with caplog.at_level(logging.ERROR, logger="pdf_latex"):
            result = generate_pdf_output(str(tex_path), str(pdf_path), work_dir=_make_work_dir(tmp_path))

    assert result is False
    assert "not on PATH" in caplog.text
    assert not pdf_path.exists()


def test_generate_pdf_output_returns_true_and_moves_pdf_on_success(tmp_path, caplog):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "output" / "sheet.pdf"
    pdf_path.parent.mkdir()
    work_dir = _make_work_dir(tmp_path)

    def fake_run(args, **kwargs):
        temp_dir = next(a for a in args if a.startswith("-output-directory=")).split("=", 1)[1]
        (Path(temp_dir) / "temp_pdf.pdf").write_bytes(b"%PDF-stub")
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        with caplog.at_level(logging.INFO, logger="pdf_latex"):
            result = generate_pdf_output(str(tex_path), str(pdf_path), work_dir=work_dir)

    assert result is True
    assert "Created" in caplog.text
    assert pdf_path.exists()
    assert pdf_path.read_bytes() == b"%PDF-stub"


def test_generate_pdf_output_returns_false_and_copies_log_on_failure(tmp_path, caplog):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"
    work_dir = _make_work_dir(tmp_path)

    def fake_run(args, **kwargs):
        # Write a log but never a PDF — simulates a compilation failure.
        temp_dir = next(a for a in args if a.startswith("-output-directory=")).split("=", 1)[1]
        (Path(temp_dir) / "temp_pdf.log").write_text("! LaTeX Error: stub.", encoding="utf-8")
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        with caplog.at_level(logging.WARNING, logger="pdf_latex"):
            result = generate_pdf_output(str(tex_path), str(pdf_path), work_dir=work_dir)

    assert result is False
    assert "failed to produce a PDF" in caplog.text
    assert "Wrote pdflatex log" in caplog.text

    failure_log = tmp_path / "sheet.log"
    assert failure_log.exists()
    assert "LaTeX Error" in failure_log.read_text(encoding="utf-8")
    assert not pdf_path.exists()


def test_generate_pdf_output_returns_false_without_log_when_log_also_missing(tmp_path, caplog):
    tex_path = tmp_path / "sheet.tex"
    tex_path.write_text("stub", encoding="utf-8")
    pdf_path = tmp_path / "sheet.pdf"

    def fake_run(args, **kwargs):
        # Neither PDF nor log produced — pdflatex didn't even start properly.
        return _fake_completed_process()

    with patch("shutil.which", return_value="/usr/bin/pdflatex"), \
         patch("subprocess.run", side_effect=fake_run):
        with caplog.at_level(logging.ERROR, logger="pdf_latex"):
            result = generate_pdf_output(str(tex_path), str(pdf_path), work_dir=_make_work_dir(tmp_path))

    assert result is False
    assert "no log file" in caplog.text
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
        generate_pdf_output(str(tex_path), str(pdf_path), work_dir=_make_work_dir(tmp_path))

    assert len(run_calls) == 2, "pdflatex must be invoked exactly twice for cross-reference resolution"
    assert run_calls[0] == run_calls[1], "both pdflatex invocations should use identical arguments"
