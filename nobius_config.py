import copy
import json
import os


DEFAULT_CONFIG = {
    "render": {
        "theme_location": "__SET_ME_THEME_LOCATION__",
        "scripts_location": "__SET_ME_SCRIPTS_LOCATION__",
        "exam_theme_location": "__SET_ME_EXAM_THEME_LOCATION__",
        "exam_scripts_location": "__SET_ME_EXAM_SCRIPTS_LOCATION__",
    },
    "import": {
        "strip_uids": False,
        "media_strategy": "copy",
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


def load_config(config_path=None):
    config = copy.deepcopy(DEFAULT_CONFIG)
    resolved_path = config_path or _default_config_path()

    if os.path.exists(resolved_path):
        with open(resolved_path, "r", encoding="utf-8") as file:
            user_config = json.load(file)
        _merge_dicts(config, user_config)
        return config, resolved_path

    return config, None


def validate_render_config(config, exam=False):
    keys = (
        ("exam_theme_location", "exam_scripts_location")
        if exam else
        ("theme_location", "scripts_location")
    )

    unresolved = [
        key for key in keys
        if str(config["render"].get(key, "")).startswith("__SET_ME_")
    ]

    if unresolved:
        raise ValueError(
            "Nobius render configuration is incomplete. "
            f"Set the following values in the active Nobius config before rendering: {', '.join(unresolved)}"
        )
