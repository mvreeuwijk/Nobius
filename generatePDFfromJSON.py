# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 12:41:22 2020

@author: mvreeuwijk

This script turns a set of JSON files into LaTeX and optionally compiled PDF output.
It is experimental in two senses:
    - Not all JSON content converts properly to LaTeX
    - Not all valid .tex files compile successfully with Python PDFLaTeX

With further development it could be incorporated into the Sheet Generator, but
is currently separate.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from subprocess import PIPE

import validation


def load_json_file(filepath):
    # Copied from Pierre/Louis
    with open(filepath, "r", encoding="utf-8") as file:
        try:
            json_dictionary = json.load(file)
        except json.JSONDecodeError as error:
            print(validation.get_path_string([os.path.basename(filepath)]))
            sys.tracebacklimit = 0
            raise error

    return json_dictionary


def html_to_tex(input_text):
    # The JSON includes HTML that needs removing or replacing
    replacements = [
        (r"<ol.*?>(.*?)<\/ol>", r"\\begin{enumerate}[(i)]\1\\end{enumerate}"),
        (r"<ul.*?>(.*?)<\/ul>", r"\\begin{itemize}\1\\end{itemize}"),
        (r"\\begin{array}(.*?)\\end{array}", r"$\\begin{array}\1\\end{array}$"),
        (r"<li>", r"\\item "),
        (r"<br>", r"\n"),
        (r"<p>", r"\\\\ "),
        (r"</p>", r"\\\\ "),
        (r"<i>(.*?)</i>", r"\\emph{\1}"),
        (r"&amp;", r"&"),
        (r"%", r"\\%"),
        (r"&nbsp;", r"~"),
        (r"<(.*?)>", r" "),
        (r"&lt;", r"<"),
        (r"&gt;", r">"),
    ]

    for pattern, replacement in replacements:
        input_text = re.sub(pattern, replacement, input_text)
    return input_text


def clean_algorithm(input_text, pdf_values):
    # The JSON includes algorithmic variables that need replacing
    for variable_name, variable_value in pdf_values:
        input_text = re.sub(r"\$" + variable_name + r"(?!D|2)", str(variable_value), input_text)
        # Note requirement that expression is not followed by 'D'
        # Otherwise e.g. $TAD would be recognised as $TA.
    return input_text


def format_algorithm(input_text):
    replacements = [
        (r"\$", r""),
        (r";", r";}\\newline\\text{"),
    ]

    for pattern, replacement in replacements:
        input_text = re.sub(pattern, replacement, input_text)
    return input_text


def apply_algorithm_values(text, content):
    if "algorithm" in content and "PDF_values" in content:
        return clean_algorithm(text, content["PDF_values"])
    return text


def write_media_block(file_obj, media):
    if not media:
        return

    file_obj.write(r"\begin{center}")
    for pic in media:
        if pic[-3:] in ["jpg", "png", "pdf"]:
            file_obj.write("\\includegraphics[clip=true,height=0.5\\textwidth]{" + pic + "}\\\\")
    file_obj.write(r"\end{center}")


def write_choice_block(file_obj, part, content):
    if "response" not in part:
        return

    mode = part["response"]["mode"]
    if "Non Permuting Multiple Choice" not in mode and "Non Permuting Multiple Selection" not in mode:
        return

    file_obj.write("\\begin{itemize}")
    for choice in part["response"]["choices"]:
        choice_tex = html_to_tex(re.sub("<p>", "", choice))
        choice_tex = apply_algorithm_values(choice_tex, content)
        file_obj.write("\\item " + choice_tex)
    file_obj.write("\\end{itemize}")


def write_worked_solutions(file_obj, part):
    if "worked_solutions" not in part:
        return

    file_obj.write(r"Worked Solution:\\")
    for step in part["worked_solutions"]:
        write_media_block(file_obj, step.get("media", []))
        if "text" in step:
            file_obj.write(html_to_tex(step["text"]) + "\\\\\\\\")


def write_final_answer(file_obj, part, label):
    if "final_answer" not in part:
        return

    file_obj.write(label)
    write_media_block(file_obj, part["final_answer"].get("media", []))
    if "text" in part["final_answer"]:
        file_obj.write(html_to_tex(part["final_answer"]["text"]))


def generate_pdf_output(tex_path, pdf_path):
    """
    Generate a PDF file from TeX using pdflatex.

    - output dir: pdflatex generates a lot of unwanted files, so we output
      everything to temp and copy the pdf over afterwards
    - interaction: batchmode will essentially suppress all the errors
      (not very nice for debugging)

    We have to move to the directory the tex_path is in so that images can be
    rendered properly.
    """
    print(f"[PDF] Getting reading to generate {os.path.basename(pdf_path)}")

    if shutil.which("pdflatex") is None:
        print("\033[91m[ERROR] pdflatex is not an executable on this system (check PATH and install)\033[0m")
        return

    initial_dir = os.getcwd()
    os.chdir(os.path.split(tex_path)[0])

    with tempfile.TemporaryDirectory() as temp_dir:
        args = [
            "pdflatex",
            f"-output-directory={temp_dir}",
            "-jobname=temp_pdf",
            "-interaction=batchmode",
            os.path.basename(tex_path),
        ]

        completed = subprocess.run(args, timeout=15, stdout=PIPE, stderr=PIPE)

        temp_pdf_path = os.path.join(temp_dir, "temp_pdf.pdf")
        if os.path.isfile(temp_pdf_path):
            shutil.move(temp_pdf_path, pdf_path)
            print(f"\033[92m[PDF] Success! Created {os.path.basename(pdf_path)} \033[0m")
        else:
            print("\033[91m[ERROR] Something went wrong with running pdflatex\033[0m")
            temp_log_path = os.path.join(temp_dir, "temp_pdf.log")
            if os.path.isfile(temp_log_path):
                print("\033[96m[PDF] Log available, print? [Y/N]: \033[0m", end="")
                if str(input()).lower() == "y":
                    with open(temp_log_path, "r", encoding="utf-8") as file:
                        for line in file.readlines():
                            print("\033[93m" + line.rstrip() + "\033[0m")
            else:
                print("\tLog file wasn't even created, printing CompletedProcess object")
                print(completed)

    os.chdir(initial_dir)


def import_pypdf2():
    from PyPDF2 import PdfFileMerger, PdfFileReader

    return PdfFileMerger, PdfFileReader


def generate_tex_output(sheet_dir, no_pdf, content_mode, pages_acc=None, tmp_merge_folder=None):
    header_file = os.path.abspath("templates/header.tex")

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

    outputfile_tex = os.path.join(sheet_dir, "media", sheet_info["name"] + suffix + ".tex")
    if tmp_merge_folder:
        outputfile_pdf = os.path.join(tmp_merge_folder, sheet_info["name"] + suffix + ".pdf")
    else:
        outputfile_pdf = os.path.join(sheet_dir, "media", sheet_info["name"] + suffix + ".pdf")

    with open(outputfile_tex, "w", encoding="utf-8") as file:
        with open(header_file, "r", encoding="utf-8") as header:
            for line in header:
                file.write(line)

        if pages_acc:
            file.write(r"\setcounter{page}{" + str(pages_acc + 1) + "}")

        if pages_acc == 0:
            file.write(r"\maketitle")
            file.write(r"\pagebreak")

        file.write("\\ETrule")
        file.write("\\setcounter{section}{" + str(sheet_info["number"] - 1) + "}")
        file.write("\\section{" + sheet_info["name"] + "}")
        file.write(
            "\\ETrule Note: this sheet was automatically generated from online Problem Sets. "
            "Not all content translates to the offline version, please visit the online version, "
            "accessible via BB, for full content."
        )

        for question_index in range(len(sheet_info["questions"])):
            content = load_json_file(os.path.join(sheet_dir, sheet_info["questions"][question_index] + ".json"))

            file.write("")
            file.write("\\ETrule")
            file.write(r"\subsection{")
            file.write(content["title"])
            file.write("}\n")

            if content_mode in ["questions", "review"]:
                new_master = html_to_tex(content["master_statement"])
                new_master = apply_algorithm_values(new_master, content)
                file.write(new_master)
                write_media_block(file, content.get("media", []))

            num_parts = len(content["parts"])
            if num_parts > 1:
                file.write(r"\begin{enumerate}[(a)]")
            for part_index in range(num_parts):
                if num_parts > 1:
                    file.write("\\item ")
                part = content["parts"][part_index]

                if content_mode in ["questions", "review"]:
                    new_content = html_to_tex(part["statement"])
                    new_content = apply_algorithm_values(new_content, content)
                    file.write(new_content)
                    if "latex_only" in part:
                        file.write(part["latex_only"])
                    write_choice_block(file, part, content)

                if content_mode == "review":
                    file.write(r"\\\\")
                    write_worked_solutions(file, part)
                    file.write(r"\\\\")
                    write_final_answer(file, part, r"Final Answer:\\")
                elif content_mode == "solutions":
                    write_worked_solutions(file, part)
                    write_final_answer(file, part, r"Solution:\\")

            if num_parts > 1:
                file.write("\\end{enumerate}")

            if content_mode == "review" and "algorithm" in content:
                file.write("\\text{" + format_algorithm(content["algorithm"]) + "}\\newline")

        file.write("\\ETrule\\end{document}")

    print(f"[TEX] Sheet tex compiled and saved to {sheet_info['name']}.tex")

    if not no_pdf:
        generate_pdf_output(outputfile_tex, outputfile_pdf)

    return outputfile_pdf


def main():
    parser = argparse.ArgumentParser(description="Problem Set PDF compiler based on JSON files")
    parser.add_argument("--sheet-path", "-s", help="Path to the Sheet folder (if the -batch flag is set, this is interpreted as a directory containing multiple sheet folders)", required=True)
    parser.add_argument("--no-pdf", help="Set this flag to disable converting the rendered .tex file into a PDF", action="store_true")
    parser.add_argument("--batch-mode", "-b", help="Set this flag to render multiple sheets at once", action="store_true")
    parser.add_argument("--content-mode", choices=["questions", "review", "solutions"], default="questions", help="Select whether to render normal question sheets, review sheets, or solutions sheets")
    args = parser.parse_args()

    if not args.batch_mode:
        print(f"[INIT] Starting generatePDFfromJSON with sheet {os.path.basename(args.sheet_path)} (pdf_write={bool(args.no_pdf)}) (batchmode=False) (content_mode={args.content_mode})")
        generate_tex_output(args.sheet_path, args.no_pdf, args.content_mode)
    elif not args.no_pdf:
        print(f"[INIT] Starting generatePDFfromJSON with sheets in {os.path.basename(args.sheet_path)} (pdf_write={bool(args.no_pdf)}) (batchmode=True) (content_mode={args.content_mode})")
        PdfFileMerger, PdfFileReader = import_pypdf2()
        sheets = [item for item in os.listdir(args.sheet_path) if os.path.isfile(os.path.join(args.sheet_path, item, "SheetInfo.json"))]

        print("[INIT] Going to render the following sheets in a temporary directory before merging.")
        print(f"└───{os.path.basename(args.sheet_path)}", end="")
        print("\n    ├─── " + "\n    ├─── ".join(sheets[:-1]), end="")
        print(f"\n    └─── {sheets[-1]}\n")

        with tempfile.TemporaryDirectory() as tmp_merge_folder:
            print(f"[DEBUG] Temp dir is in {tmp_merge_folder}")
            rendered_pdfs = []
            pages_acc = 0
            for sheet in sheets:
                new_pdf = generate_tex_output(
                    os.path.join(args.sheet_path, sheet),
                    args.no_pdf,
                    args.content_mode,
                    pages_acc,
                    tmp_merge_folder,
                )
                pages_acc += PdfFileReader(new_pdf).numPages
                rendered_pdfs.append(new_pdf)

            print(f"[PDF Merge] Merging {len(rendered_pdfs)} rendered PDFs")
            merged_file = PdfFileMerger()
            for pdf in rendered_pdfs:
                merged_file.append(PdfFileReader(pdf, "rb"))

        merged_suffix = "" if args.content_mode == "questions" else f"_{args.content_mode}"
        merged_file.write(os.path.join(args.sheet_path, f"MergedSheets{merged_suffix}.pdf"))
        print(f"\033[92m[PDF Merge] Merged all rendered PDFs Successfully! ({len(sheets)} accross {pages_acc} pages)\033[0m")
    else:
        print("[ERROR] Both Batchmode and No_PDF were set - currently batchmode merging requires individual pdfs to be created")
        print("[ERROR] Render .tex files for each sheet instead (no merging or pdf) (Y/N)? ", end="")
        if str(input()).lower() == "y":
            sheets = [item for item in os.listdir(args.sheet_path) if os.path.isfile(os.path.join(args.sheet_path, item, "SheetInfo.json"))]

            print("[INIT] Going to render the following sheets to their respective 'media' folder.")
            print(f"└───{os.path.basename(args.sheet_path)}", end="")
            print("\n    ├─── " + "\n    ├─── ".join(sheets[:-1]), end="")
            print(f"\n    └─── {sheets[-1]}\n")

            for sheet in sheets:
                generate_tex_output(os.path.join(args.sheet_path, sheet), args.no_pdf, args.content_mode)


if __name__ == "__main__":
    main()
