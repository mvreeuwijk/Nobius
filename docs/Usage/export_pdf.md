# export_pdf.py Documentation

## Introduction

`export_pdf.py` converts a Nobius sheet into LaTeX and can optionally compile that LaTeX to PDF with `pdflatex`. This is useful for producing offline exercise, review, or solutions packs from the same JSON source used for Mobius rendering.

## Prerequisites

- Python 3.6 or higher
- a working `pdflatex` executable on your system `PATH` if you want PDF output

## Usage

Run the script from the `Nobius` directory:

```bash
python export_pdf.py --sheet-path SHEET_PATH [--content-mode MODE] [--no-pdf] [--batch-mode]
```

Where:

- `--sheet-path` or `-s` points to the Nobius sheet directory.
- `--content-mode` chooses one of `exercise`, `review`, or `solutions`.
- `--no-pdf` writes LaTeX output without running `pdflatex`.
- `--batch-mode` processes multiple sheets in one run.

## Output

The script writes generated files into the sheet's `media/` directory:

- `<sheet_name>.tex` for exercise content
- `<sheet_name>_review.tex` for review content
- `<sheet_name>_solutions.tex` for solutions content

If PDF generation is enabled and `pdflatex` succeeds, matching PDF files are written alongside the TeX files.

## Notes

- Not all HTML content translates cleanly to LaTeX.
- Some valid TeX output may still fail to compile depending on the installed LaTeX toolchain.
- Media files referenced by the sheet are copied into the generated output flow automatically.
