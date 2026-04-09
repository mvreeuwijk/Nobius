import argparse

from nobius_config import load_config, validate_render_config
from render_common import render_sheet


RENDER_PROFILES = {
    "standard": {
        "template_name": "manifests/assignment.xml",
        "layout_profile": "exam",
        "theme_key": "theme_location",
        "scripts_key": "scripts_location",
    },
    "exercise": {
        "template_name": "manifests/questionbank.xml",
        "layout_profile": "default",
        "theme_key": "theme_location",
        "scripts_key": "scripts_location",
    },
    "exam": {
        "template_name": "manifests/assignment.xml",
        "layout_profile": "exam",
        "theme_key": "exam_theme_location",
        "scripts_key": "exam_scripts_location",
    },
}


def build_render_parser(description, path_help):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "filepath",
        type=str,
        help=path_help,
    )
    parser.add_argument(
        "--reset-uid",
        "-uid",
        action="store_true",
        help="Regenerate sheet and question UIDs before rendering.",
    )
    parser.add_argument(
        "--write-missing-uids",
        action="store_true",
        help="Persist generated UIDs into source JSON files when they are missing.",
    )
    parser.add_argument(
        "--batch-destination",
        "-d",
        type=str,
        help="Batch render destination folder used by export_mobius_batch.py.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a Nobius JSON config file. Defaults to repo-root nobius.json.",
    )
    parser.add_argument(
        "--render-profile",
        choices=sorted(RENDER_PROFILES.keys()),
        default="standard",
        help="Rendering profile controlling template and resource paths.",
    )
    return parser


def resolve_render_profile(config, profile_name):
    profile = RENDER_PROFILES[profile_name]
    validate_render_config(config, exam=(profile_name == "exam"))
    return {
        "template_name": profile["template_name"],
        "render_settings": {
            "theme_location": config["render"][profile["theme_key"]],
            "scripts_location": config["render"][profile["scripts_key"]],
            "layout_profile": profile["layout_profile"],
        },
    }


def run_render_cli(description, path_help):
    parser = build_render_parser(description, path_help)
    args = parser.parse_args()
    config, _ = load_config(args.config)
    render_profile = resolve_render_profile(config, args.render_profile)

    render_sheet(
        args.filepath,
        render_profile["template_name"],
        render_profile["render_settings"],
        reset_uid=args.reset_uid,
        write_missing_uids=args.write_missing_uids,
        output_dir=args.batch_destination,
    )
