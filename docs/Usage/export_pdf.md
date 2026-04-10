# export_pdf.py Documentation

## Introduction

`export_pdf.py` converts a Nobius sheet into LaTeX and can optionally compile that LaTeX to PDF with `pdflatex`.

## Usage

Run the script from the `Nobius` directory:

```bash
python export_pdf.py --sheet-path SHEET_PATH [--content-mode MODE] [--no-pdf] [--batch-mode] [--config CONFIG] [--profile PROFILE]
```

Where:

- `--sheet-path` or `-s` points to the Nobius sheet directory.
- `--content-mode` chooses one of `exercise`, `review`, or `solutions`.
- `--no-pdf` writes LaTeX output without running `pdflatex`.
- `--batch-mode` processes multiple sheets in one run.
- `--config` points to the Nobius config JSON. If omitted, `Nobius/nobius.json` is used.
- `--profile` selects the named Nobius profile. If omitted, the config's `default_profile` is used.

## Output

The script writes generated files into the sheet's `renders/` directory:

- `<sheet_name>.tex` for exercise content
- `<sheet_name>_review.tex` for review content
- `<sheet_name>_solutions.tex` for solutions content

If PDF generation is enabled and `pdflatex` succeeds, matching PDF files are written alongside the TeX files in `renders/`. Source figures and other sheet assets continue to be read from the sheet's `media/` directory.

In batch mode, sheets are rendered and merged in `SheetInfo.json` number order so section numbering stays consistent even if folder names sort differently.

## Heading Profiles

The LaTeX preamble contains configurable heading strings such as the section label and footer label.

`export_pdf.py` resolves:

1. a named Nobius profile
2. that profile's `pdf.heading`
3. the concrete heading strings from the top-level `pdf.headings` section

The concrete heading fields control:

- `footer_label`: the label used in the footer before the current sheet/section name and page number context.
- `section_label`: the prefix used in the main section heading, for example `Problem Set #` or `Exam #`.

Example:

```json
{
  "default_profile": "exam",
  "profiles": {
    "exam": {
      "pdf": {
        "heading": "problem_sets"
      }
    },
    "html_preview": {
      "pdf": {
        "heading": "generic"
      }
    }
  },
  "pdf": {
    "headings": {
      "problem_sets": {
        "footer_label": "Set \\#",
        "section_label": "MECH50010 Problem Set \\#"
      },
      "generic": {
        "footer_label": "Sheet \\#",
        "section_label": "Nobius Sheet \\#"
      }
    }
  }
}
```

This means PDF presentation is fully profile-dependent. There is no separate heading override flag anymore.

## Notes

- Not all HTML content translates cleanly to LaTeX.
- Some valid TeX output may still fail to compile depending on the installed LaTeX toolchain.
- Media files referenced by the sheet are copied into the generated output flow automatically.
- The review mode is designed as a QA artifact rather than a polished student handout. It intentionally exposes metadata such as filenames, UIDs, response modes, media counts, and solution availability in a compact summary block.
