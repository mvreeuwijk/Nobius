import argparse

from nobius_config import load_config, resolve_profile, validate_render_config
from render_common import render_sheet


RENDER_MODES = {
    "assignment": {
        "template_name": "manifests/assignment.xml",
        "layout_profile": "exam",
    },
    "exercise": {
        "template_name": "manifests/questionbank.xml",
        "layout_profile": "default",
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
        "--profile",
        help="Named Nobius profile controlling resource paths. Defaults to the config's default_profile.",
    )
    parser.add_argument(
        "--render-mode",
        choices=sorted(RENDER_MODES.keys()),
        default="assignment",
        help="Rendering mode controlling the output manifest/template shape.",
    )
    return parser


def resolve_render_profile(config, render_mode, profile_name=None):
    mode = RENDER_MODES[render_mode]
    resolved_profile_name, _ = resolve_profile(config, profile_name)
    render_config = validate_render_config(config, resolved_profile_name)
    return {
        "template_name": mode["template_name"],
        "render_settings": {
            "theme_location": render_config["theme_location"],
            "scripts_location": render_config["scripts_location"],
            "layout_profile": mode["layout_profile"],
        },
        "profile_name": resolved_profile_name,
        "render_mode": render_mode,
    }


def run_render_cli(description, path_help):
    parser = build_render_parser(description, path_help)
    args = parser.parse_args()
    config, _ = load_config(args.config)
    render_profile = resolve_render_profile(config, args.render_mode, args.profile)

    render_sheet(
        args.filepath,
        render_profile["template_name"],
        render_profile["render_settings"],
        reset_uid=args.reset_uid,
        write_missing_uids=args.write_missing_uids,
        output_dir=args.batch_destination,
    )
