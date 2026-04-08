"""
Batch wrapper around generateGroup.py.

This preserves the original workflow of rendering all sheet folders in a parent
directory, then merging their generated XML and media into one import bundle.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


SKELETON_XML = """
<courseModule>
    <module>
    <autoModule>true</autoModule>
    </module>

    <questionGroups>
    </questionGroups>

    <questions>
    </questions>

    <webResources>
    <folder id="0">
      <name>
        <![CDATA[  web_folders  ]]>
      </name>
      <description>
        <![CDATA[    ]]>
      </description>
      <uri>
        <![CDATA[  web_folders  ]]>
      </uri>
    </folder>
    </webResources>
</courseModule>
"""

MEDIA_MANIFEST_XML = """
<courseModule>
  <module>
    <autoModule>true</autoModule>
  </module>

  <webResources>
    <folder id="0">
      <name>
        <![CDATA[  web_folders  ]]>
      </name>
      <description>
        <![CDATA[    ]]>
      </description>
      <uri>
        <![CDATA[  web_folders  ]]>
      </uri>
    </folder>
  </webResources>
</courseModule>
"""


def get_question_timings(sheet_directory):
    timings = {"Total": [0, 0]}
    sheet_info_path = sheet_directory / "SheetInfo.json"

    try:
        with open(sheet_info_path, "r", encoding="utf-8") as file:
            sheet_info = json.load(file)
    except (FileNotFoundError, NotADirectoryError):
        print(f"SheetInfo.json not found in {sheet_directory} directory. Moving to next folder")
        return {}

    for question_name in sheet_info["questions"]:
        with open(sheet_directory / f"{question_name}.json", "r", encoding="utf-8") as file:
            question = json.load(file)
            par_time = question.get("icon_data", {}).get("par_time")
            if par_time is None:
                continue
            timings[question_name] = par_time
            timings["Total"][0] += timings[question_name][0]
            timings["Total"][1] += timings[question_name][1]

    return timings


def get_timings_summary(timings_by_sheet):
    lines = []
    for sheet_name, timings in timings_by_sheet.items():
        lines.append(f"{sheet_name}: {timings['Total'][0]}-{timings['Total'][1]} mins total.")
        for question_name, mins in timings.items():
            if question_name != "Total":
                lines.append(f"    {question_name}: {mins[0]}-{mins[1]} mins.")
    return "\n".join(lines) + ("\n" if lines else "")


def ensure_output_structure(output_dir):
    (output_dir / "web_folders").mkdir(parents=True, exist_ok=True)
    (output_dir / "xml").mkdir(parents=True, exist_ok=True)


def iter_sheet_directories(work_dir):
    for child in sorted(work_dir.iterdir()):
        if child.is_dir():
            yield child


def render_sheet_directory(sheet_path, output_dir, reset_uids, write_missing_uids=False, config_path=None, render_profile="standard"):
    command = [
        sys.executable,
        "generateGroup.py",
        str(sheet_path),
        "-d",
        str(output_dir),
        "--render-profile",
        render_profile,
    ]
    if reset_uids:
        command.append("--reset-uid")
    if write_missing_uids:
        command.append("--write-missing-uids")
    if config_path:
        command.extend(["--config", str(config_path)])

    return subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )


def merge_xml(output_dir):
    manifest = ET.fromstring(SKELETON_XML)
    xml_dir = output_dir / "xml"

    for sheet_xml in sorted(xml_dir.glob("*.xml")):
        print(f"[MERGING] {sheet_xml.name}")
        root = ET.parse(sheet_xml).getroot()

        group = root.find("./questionGroups/group")
        match = re.search(r"#(\d+)", group.find("name").text or "")
        if match:
            group.set("weight", f"{match[1]}.0")
        manifest.find("./questionGroups").append(group)

        for question in root.findall("./questions/question"):
            manifest.find("./questions").append(question)

    all_sheets_path = output_dir / "all_sheets.xml"
    with open(all_sheets_path, "wb") as file:
        file.write(ET.tostring(manifest))

    print("[DONE] Saved content to all_sheets.xml")
    return all_sheets_path


def bundle_media(output_dir):
    zip_path = output_dir / "all_media.zip"
    with ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr("manifest.xml", MEDIA_MANIFEST_XML)
        for media_folder in sorted((output_dir / "web_folders").iterdir()):
            if not media_folder.is_dir():
                continue
            for media_file in sorted(media_folder.iterdir()):
                if media_file.is_file():
                    zip_file.write(media_file, arcname=os.path.join("web_folders", media_folder.name, media_file.name))

    print("[DONE] Compiled Media zip file to all_media.zip")
    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="[wrapper for generateGroup.py] Render sheets in batch, merge XML, and bundle media."
    )
    parser.add_argument(
        "sheets_dir",
        type=str,
        help="Path to the folder containing all sheet folders to be converted.",
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Path to destination folder in which to store and merge all XML and media files.",
    )
    parser.add_argument(
        "--reset-uid",
        "-uid",
        help="Reset all UIDs for all question and SheetInfo files before rendering.",
        action="store_true",
    )
    parser.add_argument(
        "--write-missing-uids",
        action="store_true",
        help="Persist generated UIDs into source JSON files when they are missing.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a Nobius JSON config file passed through to generateGroup.py.",
    )
    parser.add_argument(
        "--render-profile",
        choices=["standard", "exam"],
        default="standard",
        help="Rendering profile passed through to generateGroup.py.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue rendering remaining sheets if one sheet fails.",
    )
    args = parser.parse_args()

    work_dir = Path(args.sheets_dir)
    output_dir = Path(args.output_dir)
    ensure_output_structure(output_dir)

    sheet_timings = {}
    for sheet_path in iter_sheet_directories(work_dir):
        result = render_sheet_directory(
            sheet_path,
            output_dir,
            args.reset_uid,
            args.write_missing_uids,
            args.config,
            args.render_profile,
        )
        question_timings = get_question_timings(sheet_path)

        if result.returncode == 0 and question_timings:
            sheet_timings[sheet_path.name] = question_timings
            print(
                f"[RENDERING] Sheet {sheet_path.name} done. "
                f"Sheet length: {question_timings['Total'][0]}-{question_timings['Total'][1]} minutes."
            )
            continue

        print(f"[ERROR] Sheet {sheet_path.name} aborted")
        print(result.stderr)
        if not args.continue_on_error:
            raise SystemExit(1)

    with open(output_dir / "question_timings.txt", "w", encoding="utf-8") as file:
        file.write(get_timings_summary(sheet_timings))

    merge_xml(output_dir)
    bundle_media(output_dir)


if __name__ == "__main__":
    main()
