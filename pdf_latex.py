# -*- coding: utf-8 -*-
"""
pdflatex invocation for Nobius PDF export.

Provides a single public function, :func:`generate_pdf_output`, that
compiles a ``.tex`` file to PDF using ``pdflatex``.  All intermediate
artefacts (aux, log, …) are written to a temporary directory and discarded
unless compilation fails, in which case the log is copied next to the
intended PDF path for inspection.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from subprocess import PIPE


def generate_pdf_output(tex_path: str | os.PathLike, pdf_path: str | os.PathLike) -> None:
    """Compile *tex_path* with pdflatex and write the result to *pdf_path*.

    - All intermediate files are written to a temporary directory so that
      only the final ``.pdf`` ends up next to the source.
    - ``pdflatex`` is run twice so that cross-references (page numbers, TOC
      entries) resolve correctly on the second pass.
    - ``cwd`` is set to the directory containing the ``.tex`` file so that
      relative ``\\includegraphics`` paths resolve correctly.
    - Errors are reported to stdout; the LaTeX log is copied to
      ``<pdf_path_stem>.log`` when compilation fails.
    """
    print(f"[PDF] Getting reading to generate {os.path.basename(pdf_path)}")
    tex_path = os.path.abspath(tex_path)
    pdf_path = os.path.abspath(pdf_path)
    tex_dir = os.path.dirname(tex_path)

    if shutil.which("pdflatex") is None:
        print("\033[91m[ERROR] pdflatex is not an executable on this system (check PATH and install)\033[0m")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
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
            print(f"\033[92m[PDF] Success! Created {os.path.basename(pdf_path)} \033[0m")
        else:
            print("\033[91m[ERROR] Something went wrong with running pdflatex\033[0m")
            temp_log_path = os.path.join(temp_dir, "temp_pdf.log")
            if os.path.isfile(temp_log_path):
                failure_log_path = os.path.splitext(pdf_path)[0] + ".log"
                shutil.copyfile(temp_log_path, failure_log_path)
                print(f"\033[93m[PDF] Wrote LaTeX log to {failure_log_path}\033[0m")
            else:
                print("\tLog file wasn't even created, printing CompletedProcess object")
                print(completed)
