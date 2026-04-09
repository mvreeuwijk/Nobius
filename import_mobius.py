import argparse
import json
import os
import re
import shutil
import zipfile

import bs4

from import_report import ImportReport
from nobius_config import load_config
import xml_scraper


def remove_group_ids(group):
    if "uid" in group["info"]:
        del group["info"]["uid"]

    for question in group["questions"]:
        if "uid" in question:
            del question["uid"]


def safe_question_basename(title, used_names):
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title or "").strip()
    base = re.sub(r"\s+", " ", base).strip().rstrip(".")
    if not base:
        base = "Question"

    candidate = base
    counter = 2
    lowered = {name.lower() for name in used_names}
    while candidate.lower() in lowered:
        candidate = f"{base} ({counter})"
        counter += 1

    used_names.add(candidate)
    return candidate


def resolve_manifest_path(source_path):
    if zipfile.is_zipfile(source_path):
        with zipfile.ZipFile(source_path, "r") as zip_file:
            manifest_name = find_manifest_entry(zip_file)
        if manifest_name is None:
            raise FileNotFoundError("Could not locate manifest.xml inside the supplied ZIP export.")

        return {
            "source_type": "zip",
            "manifest_path": manifest_name,
            "zip_path": source_path,
        }

    return {
        "source_type": "xml",
        "manifest_path": source_path,
        "media_root": find_web_folders_root(os.path.dirname(source_path)),
    }


def find_manifest_entry(zip_file):
    for name in zip_file.namelist():
        if os.path.basename(name) == "manifest.xml":
            return name
    return None


def find_web_folders_root(root_dir):
    candidate = os.path.join(root_dir, "web_folders")
    if os.path.isdir(candidate):
        return candidate

    for current_root, dirnames, _ in os.walk(root_dir):
        if "web_folders" in dirnames:
            return os.path.join(current_root, "web_folders")

    return None


def gather_media_references(node, output=None):
    if output is None:
        output = set()

    if isinstance(node, dict):
        for key, value in node.items():
            if key == "media" and isinstance(value, list):
                output.update([item for item in value if item])
            else:
                gather_media_references(value, output)
    elif isinstance(node, list):
        for item in node:
            gather_media_references(item, output)

    return output


def index_media_files(media_root):
    media_index = {}

    if not media_root or not os.path.isdir(media_root):
        return media_index

    for current_root, _, files in os.walk(media_root):
        for filename in files:
            media_index.setdefault(filename, []).append(os.path.join(current_root, filename))

    return media_index


def index_media_entries(zip_path):
    media_index = {}
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        for name in zip_file.namelist():
            if name.endswith("/") or "web_folders/" not in name:
                continue
            media_index.setdefault(os.path.basename(name), []).append(name)
    return media_index


def copy_media(group, destination, source_info, media_strategy, report):
    media_refs = gather_media_references(group)
    if source_info["source_type"] == "zip":
        media_index = index_media_entries(source_info["zip_path"])
    else:
        media_index = index_media_files(source_info["media_root"])

    report.metadata["referenced_media"] = sorted(media_refs)

    if media_strategy != "copy":
        report.warn("Unsupported media strategy requested; skipping media copy.", media_strategy)
        return

    if not media_refs:
        return

    media_dest = os.path.join(destination, "media")
    os.makedirs(media_dest, exist_ok=True)

    for filename in sorted(media_refs):
        matches = media_index.get(filename, [])

        if len(matches) > 1:
            report.warn("Multiple media files matched the same filename; copying the first match.", filename)

        if not matches:
            report.warn("Referenced media could not be found in the Mobius export.", filename)
            report.add_missing_media(filename)
            continue

        src = matches[0]
        target_path = os.path.join(media_dest, filename)

        if source_info["source_type"] == "zip":
            with zipfile.ZipFile(source_info["zip_path"], "r") as zip_file:
                with zip_file.open(src, "r") as source_file, open(target_path, "wb") as target_file:
                    shutil.copyfileobj(source_file, target_file)
        else:
            shutil.copy(src, target_path)

        report.add_copied_media(filename, src)


def write_group_json(group, destination):
    os.makedirs(destination, exist_ok=True)

    used_names = set()
    question_filenames = []
    for question in group["questions"]:
        question_filenames.append(safe_question_basename(question["title"], used_names))

    group["info"]["questions"] = question_filenames

    sheet_info_filename = os.path.join(destination, "SheetInfo.json")
    with open(sheet_info_filename, "w", encoding="utf-8") as sheet_info_file:
        json.dump(group["info"], sheet_info_file, indent=4)

    outputs = [sheet_info_filename]

    for question, basename in zip(group["questions"], question_filenames):
        filename = f"{basename}.json"
        filepath = os.path.join(destination, filename)
        with open(filepath, "w", encoding="utf-8") as question_file:
            json.dump(question, question_file, indent=4)
        outputs.append(filepath)

    return outputs


def import_mobius_package(target, dest, strip_uids, config):
    source_info = resolve_manifest_path(target)
    report = ImportReport(target, source_info["source_type"], dest, strip_uids)

    if source_info["source_type"] == "zip":
        with zipfile.ZipFile(source_info["zip_path"], "r") as zip_file:
            manifest_xml = zip_file.read(source_info["manifest_path"]).decode("utf-8")
    else:
        with open(source_info["manifest_path"], "r", encoding="utf-8") as xml_file:
            manifest_xml = xml_file.read()

    xml = bs4.BeautifulSoup(manifest_xml, "lxml-xml")

    report.metadata["manifest_path"] = source_info["manifest_path"]
    group = xml_scraper.get_sheet_data_from_xml(xml, report=report)

    if strip_uids:
        remove_group_ids(group)

    outputs = write_group_json(group, dest)
    for output in outputs:
        report.add_output(output)

    copy_media(group, dest, source_info, config["import"]["media_strategy"], report)
    json_report = os.path.join(dest, "import_report.json")
    text_report = os.path.join(dest, "import_report.txt")
    report.add_output(json_report)
    report.add_output(text_report)
    report.write(dest)

    print(f"Imported {len(group['questions'])} questions into {dest}")
    print(f"Wrote import reports to {json_report} and {text_report}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import a Mobius XML file or exported ZIP back into Nobius JSON files."
    )
    parser.add_argument("filepath", type=str, help="Path to the XML file or exported ZIP to import")
    parser.add_argument(
        "--destination",
        "-d",
        type=str,
        help="Directory where imported JSON and media should be written",
    )
    parser.add_argument(
        "--no-uid",
        action="store_true",
        help="Remove UIDs from all imported JSON files",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a Nobius JSON config file. Defaults to repo-root nobius.json.",
    )

    args = parser.parse_args()
    config, _ = load_config(args.config)

    destination = args.destination if args.destination is not None else os.path.dirname(args.filepath)
    strip_uids = args.no_uid or config["import"]["strip_uids"]

    import_mobius_package(args.filepath, destination, strip_uids, config)
