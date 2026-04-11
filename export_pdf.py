# -*- coding: utf-8 -*-
"""
Generate LaTeX and optional PDF output from a Nobius sheet.

The script writes TeX files for questions, review, or solutions content and can
optionally run pdflatex to produce PDFs. Some Nobius HTML content does not map
cleanly to LaTeX, and some valid TeX output may still fail to compile depending
on the installed LaTeX toolchain.

Implementation is split across focused modules:

- :mod:`pdf_html`    — HTML-to-LaTeX conversion
- :mod:`pdf_tex`     — TeX escape / format / label helpers
- :mod:`pdf_latex`   — pdflatex invocation
- :mod:`pdf_content` — write_* functions and :func:`~pdf_content.generate_tex_output`
"""

import argparse
import os
import tempfile

from pypdf import PdfReader, PdfWriter

from nobius_config import load_config
from pdf_content import generate_tex_output
from render_common import load_json_file


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


def _print_sheet_tree(parent_dir, sheets):
    """Print a tree-style listing of *sheets* under *parent_dir*."""
    print(f"└───{os.path.basename(parent_dir)}")
    if not sheets:
        print("    (no sheets found)")
        return
    for sheet in sheets[:-1]:
        print(f"    ├─── {sheet}")
    print(f"    └─── {sheets[-1]}")
    print()


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
        sheets = get_batch_sheet_directories(args.sheet_path)

        print("[INIT] Going to render the following sheets in a temporary directory before merging.")
        _print_sheet_tree(args.sheet_path, sheets)

        with tempfile.TemporaryDirectory() as tmp_merge_folder:
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
                if new_pdf is None:
                    print(f"[PDF Merge] Skipping {sheet}: PDF generation failed")
                    continue
                pages_acc += len(PdfReader(new_pdf).pages)
                rendered_pdfs.append(new_pdf)

            if not rendered_pdfs:
                print(f"[PDF Merge] All {len(sheets)} sheet(s) failed PDF generation; nothing to merge.")
                return

            print(f"[PDF Merge] Merging {len(rendered_pdfs)} rendered PDFs")
            merged_file = PdfWriter()
            for pdf in rendered_pdfs:
                merged_file.append(pdf)

            merged_suffix = "" if args.content_mode == "questions" else f"_{args.content_mode}"
            merged_file.write(os.path.join(args.sheet_path, f"MergedSheets{merged_suffix}.pdf"))
        print(f"\033[92m[PDF Merge] Merged all rendered PDFs Successfully! ({len(sheets)} accross {pages_acc} pages)\033[0m")
    else:
        # --batch-mode + --no-pdf: render .tex files for each sheet without merging.
        sheets = get_batch_sheet_directories(args.sheet_path)

        print("[INIT] Going to render the following sheets to their respective 'renders' folder.")
        _print_sheet_tree(args.sheet_path, sheets)

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
