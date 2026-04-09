import json
import subprocess
import sys

import pytest

from nobius_config import DEFAULT_CONFIG, load_config, validate_render_config

from .conftest import REPO_ROOT, make_config_payload, write_json


def test_load_config_uses_defaults_when_file_is_missing(tmp_path):
    config, resolved = load_config(str(tmp_path / "missing.json"))

    assert resolved is None
    assert config == DEFAULT_CONFIG


def test_load_config_merges_nested_override_values(tmp_path):
    config_path = tmp_path / "nobius.json"
    config_path.write_text(
        json.dumps(
            {
                "render": {
                    "theme_location": "/themes/custom",
                },
                "import": {
                    "strip_uids": True,
                },
            }
        ),
        encoding="utf-8",
    )

    config, resolved = load_config(str(config_path))

    assert resolved == str(config_path)
    assert config["render"]["theme_location"] == "/themes/custom"
    assert config["render"]["scripts_location"] == DEFAULT_CONFIG["render"]["scripts_location"]
    assert config["import"]["strip_uids"] is True
    assert config["import"]["media_strategy"] == DEFAULT_CONFIG["import"]["media_strategy"]


def test_load_config_uses_repo_default_path():
    config, resolved = load_config()

    assert resolved is not None
    assert resolved.endswith("nobius.json")
    assert "render" in config
    assert "import" in config


def test_validate_render_config_rejects_placeholder_defaults():
    with pytest.raises(ValueError, match="theme_location, scripts_location"):
        validate_render_config(DEFAULT_CONFIG)


def test_generate_group_cli_fails_cleanly_when_render_config_is_placeholder(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    write_json(config_path, {"render": {"theme_location": "__SET_ME_THEME_LOCATION__"}})

    result = subprocess.run(
        [sys.executable, "export_mobius.py", str(t01_sheet), "--config", str(config_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Nobius render configuration is incomplete" in result.stderr


def test_generate_group_cli_fails_cleanly_when_exam_render_config_is_placeholder(t01_sheet, tmp_path):
    config_path = tmp_path / "nobius.json"
    write_json(
        config_path,
        make_config_payload(exam_theme_location="__SET_ME_EXAM_THEME_LOCATION__"),
    )

    result = subprocess.run(
        [
            sys.executable,
            "export_mobius.py",
            str(t01_sheet),
            "--config",
            str(config_path),
            "--render-profile",
            "exam",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Nobius render configuration is incomplete" in result.stderr
