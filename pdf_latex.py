# -*- coding: utf-8 -*-
"""
pdflatex invocation for Nobius PDF export.

Provides a single public function, :func:`generate_pdf_output`, that
compiles a ``.tex`` file to PDF using ``pdflatex``.  All intermediate
artefacts (aux, log, …) are written to a scratch directory and discarded
unless compilation fails, in which case the log is copied next to the
intended PDF path for inspection.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from subprocess import PIPE

logger = logging.getLogger(__name__)


@contextmanager
def _working_temp(work_dir: str | os.PathLike | None):
    """Yield a writable scratch directory for intermediate pdflatex artefacts.

    When *work_dir* is ``None`` (the default), a temporary directory is created
    and removed automatically on exit.  When a path is supplied it is yielded
    as-is so the caller controls the lifetime — useful in CI environments where
    the OS temp directory may not be writable, or in tests that need to inspect
    intermediate files afterwards.
    """
    if work_dir is None:
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp
    else:
        yield os.fspath(work_dir)


def generate_pdf_output(
    tex_path: str | os.PathLike,
    pdf_path: str | os.PathLike,
    work_dir: str | os.PathLike | None = None,
) -> bool:
    """Compile *tex_path* with pdflatex and write the result to *pdf_path*.

    Returns ``True`` if the PDF was produced successfully, ``False`` otherwise.

    Parameters
    ----------
    tex_path:
        Source ``.tex`` file to compile.
    pdf_path:
        Destination path for the produced PDF.
    work_dir:
        Directory for intermediate pdflatex artefacts (aux, log, …).  When
        ``None`` (default) an OS temporary directory is used and cleaned up
        automatically.  Supply an explicit caller-controlled path to avoid
        writing to OS temp — e.g. in tests (pass ``tmp_path``) or in restricted
        CI environments where ``/tmp`` is not writable.

    Notes
    -----
    - ``pdflatex`` is run twice so that cross-references resolve correctly.
    - ``cwd`` is set to the ``.tex`` file's directory for relative
      ``\\includegraphics`` paths.
    - On failure the LaTeX log is copied to ``<pdf_path_stem>.log``.
    """
    logger.info("Generating %s", os.path.basename(pdf_path))
    tex_path = os.path.abspath(tex_path)
    pdf_path = os.path.abspath(pdf_path)
    tex_dir = os.path.dirname(tex_path)

    if shutil.which("pdflatex") is None:
        logger.error("pdflatex is not on PATH — install it and ensure it is accessible")
        return False

    with _working_temp(work_dir) as temp_dir:
        args = [
            "pdflatex",
            f"-output-directory={temp_dir}",
            "-jobname=temp_pdf",
            "-interaction=batchmode",
            os.path.basename(tex_path),
        ]

        # Run pdflatex twice: the first pass builds the document, the second
        # resolves cross-references (page numbers, TOC entries, etc.).
        subprocess.run(args, timeout=60, stdout=PIPE, stderr=PIPE, cwd=tex_dir)
        completed = subprocess.run(args, timeout=60, stdout=PIPE, stderr=PIPE, cwd=tex_dir)

        temp_pdf_path = os.path.join(temp_dir, "temp_pdf.pdf")
        if os.path.isfile(temp_pdf_path):
            shutil.move(temp_pdf_path, pdf_path)
            logger.info("Created %s", os.path.basename(pdf_path))
            return True

        logger.error("pdflatex failed to produce a PDF for %s", os.path.basename(tex_path))
        temp_log_path = os.path.join(temp_dir, "temp_pdf.log")
        if os.path.isfile(temp_log_path):
            failure_log_path = os.path.splitext(pdf_path)[0] + ".log"
            shutil.copyfile(temp_log_path, failure_log_path)
            logger.warning("Wrote pdflatex log to %s", failure_log_path)
        else:
            logger.error("pdflatex produced no log file; CompletedProcess: %s", completed)
        return False
