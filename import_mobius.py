import argparse
import json
import os
import re
import shutil
import zipfile

import bs4
from lxml import etree as LET

from import_report import ImportReport
from nobius_config import load_config
import xml_scraper


DEFAULT_IMPORT_MEDIA_STRATEGY = "copy"


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


def safe_directory_basename(title, used_names):
    return safe_question_basename(title, used_names)


def resolve_group_destination(root_dest, group, used_directory_names):
    path_parts = group.get("_path_parts")
    if not path_parts:
        return root_dest

    destination = root_dest
    parent_key = ()
    for part in path_parts:
        parent_state = used_directory_names.setdefault(parent_key, {"used": set(), "resolved": {}})
        part_key = (part or "").strip().lower()

        safe_part = parent_state["resolved"].get(part_key)
        if safe_part is None:
            safe_part = safe_directory_basename(part, parent_state["used"])
            parent_state["resolved"][part_key] = safe_part

        destination = os.path.join(destination, safe_part)
        parent_key = (*parent_key, safe_part)

    return destination


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


def build_manifest_line_maps(manifest_xml):
    parser = LET.XMLParser(recover=True)
    root = LET.fromstring(manifest_xml.encode("utf-8"), parser=parser)

    line_maps = {
        "questions": {},
        "assignments": {},
        "assignment_units": {},
    }

    for question in root.xpath(".//question[@uid]"):
        line_maps["questions"][question.get("uid")] = question.sourceline

    for assignment in root.xpath(".//assignment[@uid]"):
        line_maps["assignments"][assignment.get("uid")] = assignment.sourceline

    for unit in root.xpath(".//unit[@uid]"):
        line_maps["assignment_units"][unit.get("uid")] = unit.sourceline

    return line_maps


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


def _tokenize_media_hint(value):
    if not isinstance(value, str):
        return []

    tokens = []
    for token in re.findall(r"[A-Za-z]+|\d+", value.lower()):
        if token.isdigit():
            token = str(int(token))
        tokens.append(token)
    return tokens


def _candidate_path_segments(candidate):
    normalized = str(candidate).replace("/", os.sep).replace("\\", os.sep)
    return [segment for segment in normalized.split(os.sep) if segment]


def _media_match_score(candidate, group):
    path_parts = [part for part in (group.get("_path_parts") or []) if isinstance(part, str) and part.strip()]
    if not path_parts:
        return (0, 0, 0)

    candidate_segments = _candidate_path_segments(candidate)
    if not candidate_segments:
        return (0, 0, 0)

    score_exact = 0
    score_overlap = 0
    score_unit_overlap = 0
    normalized_parts = [tuple(_tokenize_media_hint(part)) for part in path_parts]
    normalized_segments = [tuple(_tokenize_media_hint(segment)) for segment in candidate_segments]

    for part_tokens in normalized_parts:
        if not part_tokens:
            continue
        part_set = set(part_tokens)
        for segment_tokens in normalized_segments:
            if not segment_tokens:
                continue
            segment_set = set(segment_tokens)
            overlap = len(part_set & segment_set)
            if overlap == 0:
                continue
            score_overlap += overlap
            if segment_tokens == part_tokens:
                score_exact += 1

    parent_unit = group.get("_parent_unit")
    if isinstance(parent_unit, str) and parent_unit.strip():
        unit_tokens = set(_tokenize_media_hint(parent_unit))
        for segment_tokens in normalized_segments:
            score_unit_overlap = max(score_unit_overlap, len(unit_tokens & set(segment_tokens)))

    return (score_exact, score_overlap, score_unit_overlap)


def select_media_match(matches, group):
    if len(matches) <= 1:
        return matches[0] if matches else None, False

    ranked_matches = sorted(
        matches,
        key=lambda candidate: (_media_match_score(candidate, group), str(candidate)),
        reverse=True,
    )
    best_match = ranked_matches[0]
    best_score = _media_match_score(best_match, group)
    second_score = _media_match_score(ranked_matches[1], group)

    if best_score > second_score and best_score > (0, 0, 0):
        return best_match, True

    return matches[0], False


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

        if not matches:
            report.warn("Referenced media could not be found in the Mobius export.", filename)
            report.add_missing_media(filename)
            continue

        src, matched_by_context = select_media_match(matches, group)
        if len(matches) > 1 and not matched_by_context:
            report.warn("Multiple media files matched the same filename; copying the first match.", filename)
        elif len(matches) > 1 and matched_by_context:
            report.info("Multiple media files matched the same filename; selected the best assignment-specific match.", filename)
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


def get_import_media_strategy(config):
    if not isinstance(config, dict):
        return DEFAULT_IMPORT_MEDIA_STRATEGY

    import_config = config.get("import", {})
    if not isinstance(import_config, dict):
        return DEFAULT_IMPORT_MEDIA_STRATEGY

    return import_config.get("media_strategy", DEFAULT_IMPORT_MEDIA_STRATEGY)


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
    report.metadata["line_maps"] = build_manifest_line_maps(manifest_xml)
    groups = getattr(xml_scraper, "get_sheets_data_from_xml", None)
    if groups is None:
        groups = [xml_scraper.get_sheet_data_from_xml(xml, report=report)]
    else:
        groups = groups(xml, report=report)

    use_subdirectories = len(groups) > 1
    used_directory_names = {}

    for group in groups:
        if strip_uids:
            remove_group_ids(group)

        group_dest = dest
        if use_subdirectories:
            group_dest = resolve_group_destination(dest, group, used_directory_names)

        outputs = write_group_json(group, group_dest)
        for output in outputs:
            report.add_output(output)

        copy_media(group, group_dest, source_info, get_import_media_strategy(config), report)

    json_report = os.path.join(dest, "import_report.json")
    text_report = os.path.join(dest, "import_report.txt")
    report.add_output(json_report)
    report.add_output(text_report)
    report.write(dest)

    total_questions = sum(len(group["questions"]) for group in groups)
    if use_subdirectories:
        print(f"Imported {total_questions} questions across {len(groups)} assessments into {dest}")
    else:
        print(f"Imported {total_questions} questions into {dest}")
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
