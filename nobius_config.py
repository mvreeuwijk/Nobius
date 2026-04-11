from __future__ import annotations

import copy
import json
import os


DEFAULT_CONFIG = {
    "default_profile": "exam",
    "html_preview_profile": "html_preview",
    "profiles": {
        "problem_set": {
            "render": {
                "theme_location": "/themes/b06b01fb-1810-4bde-bc67-60630d13a866",
                "scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt",
            },
            "pdf": {
                "heading": "problem_sets",
            },
        },
        "exam": {
            "render": {
                "theme_location": "/themes/b06b01fb-1810-4bde-bc67-60630d13a866",
                "scripts_location": "__BASE_URI__Scripts/QuestionJavaScript.txt",
            },
            "pdf": {
                "heading": "exam",
            },
        },
        "html_preview": {
            "render": {
                "theme_location": "/themes/test-theme",
                "scripts_location": "/web/test/scripts.js",
            },
            "pdf": {
                "heading": "generic",
            },
        },
    },
    "import": {
        "strip_uids": False,
        "media_strategy": "copy",
    },
    "pdf": {
        "headings": {
            "problem_sets": {
                "footer_label": r"Set \#",
                "section_label": r"MECH50010 Problem Set \#",
            },
            "exam": {
                "footer_label": "",
                "section_label": "",
            },
            "generic": {
                "footer_label": r"Sheet \#",
                "section_label": r"Nobius Sheet \#",
            },
        },
    },
}


def _merge_dicts(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_dicts(base[key], value)
        else:
            base[key] = value


def _default_config_path():
    return os.path.join(os.path.dirname(__file__), "nobius.json")


def load_config(config_path: str | None = None) -> tuple[dict, str | None]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    resolved_path = config_path or _default_config_path()

    if os.path.exists(resolved_path):
        with open(resolved_path, "r", encoding="utf-8") as file:
            user_config = json.load(file)
        _merge_dicts(config, user_config)
        return config, resolved_path

    return config, None


def resolve_profile_name(config, profile_name=None, *, for_preview=False):
    if profile_name:
        resolved_profile = profile_name
    elif for_preview:
        resolved_profile = config.get("html_preview_profile", config.get("default_profile"))
    else:
        resolved_profile = config.get("default_profile")

    profiles = config.get("profiles", {})
    if resolved_profile not in profiles:
        available_profiles = ", ".join(sorted(profiles)) or "none"
        raise ValueError(
            f"Unknown Nobius profile '{resolved_profile}'. Available profiles: {available_profiles}"
        )

    return resolved_profile


def resolve_profile(config, profile_name=None, *, for_preview=False):
    resolved_name = resolve_profile_name(config, profile_name, for_preview=for_preview)
    return resolved_name, config["profiles"][resolved_name]


def validate_render_config(config, profile_name):
    _, profile = resolve_profile(config, profile_name)
    render_config = profile.get("render", {})

    unresolved = [
        key
        for key in ("theme_location", "scripts_location")
        if str(render_config.get(key, "")).startswith("__SET_ME_")
    ]

    if unresolved:
        raise ValueError(
            "Nobius render configuration is incomplete. "
            f"Set the following values in the active Nobius profile '{profile_name}': {', '.join(unresolved)}"
        )

    return render_config


def resolve_pdf_profile(config, profile_name=None):
    resolved_name, profile = resolve_profile(config, profile_name)
    return resolved_name, profile.get("pdf", {})
