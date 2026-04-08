import subprocess
import sys

from .conftest import REPO_ROOT


def test_generate_pdf_from_json_surfaces_json_decode_error_without_nameerror(tmp_path):
    sheet_dir = tmp_path / "bad_pdf_sheet"
    media_dir = sheet_dir / "media"
    sheet_dir.mkdir()
    media_dir.mkdir()

    (sheet_dir / "SheetInfo.json").write_text("{ invalid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "generatePDFfromJSON.py",
            "--sheet-path",
            str(sheet_dir),
            "--no-pdf",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode != 0
    assert "JSONDecodeError" in combined_output
    assert "NameError" not in combined_output
