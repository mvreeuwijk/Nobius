"""
Tests for preview_html: safe_extract_archive path-traversal protection,
widget_html rendering, and write_question_previews smoke tests.
"""

import zipfile
from pathlib import Path

import bs4
import pytest

from preview_html import (
    safe_extract_archive,
    slugify,
    substitute_placeholders,
    widget_html,
    write_question_previews,
)


# ---------------------------------------------------------------------------
# safe_extract_archive
# ---------------------------------------------------------------------------


def _make_zip(tmp_path, members):
    """Create a zip file containing the given {name: content} members."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


def test_safe_extract_archive_extracts_normal_members(tmp_path):
    zip_path = _make_zip(tmp_path, {"file.txt": "hello", "subdir/other.txt": "world"})
    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "r") as archive:
        safe_extract_archive(archive, dest)

    assert (dest / "file.txt").read_text() == "hello"
    assert (dest / "subdir" / "other.txt").read_text() == "world"


def test_safe_extract_archive_rejects_parent_traversal(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "pwned")

    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "r") as archive:
        with pytest.raises(ValueError, match="unsafe zip member"):
            safe_extract_archive(archive, dest)


def test_safe_extract_archive_rejects_absolute_path_member(tmp_path):
    zip_path = tmp_path / "evil.zip"
    # zipfile won't store truly absolute paths on all platforms, so we
    # construct the member name manually to bypass that check.
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../sibling/evil.txt", "pwned")

    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "r") as archive:
        with pytest.raises(ValueError, match="unsafe zip member"):
            safe_extract_archive(archive, dest)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_lowercases_and_replaces_non_alphanumeric():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("A & B") == "a-b"


def test_slugify_returns_question_for_empty_string():
    assert slugify("") == "question"
    assert slugify("---") == "question"


# ---------------------------------------------------------------------------
# widget_html — rendering smoke tests
# ---------------------------------------------------------------------------


def _make_part_xml(mode, choices=None):
    choices_xml = "".join(f"<choice>{c}</choice>" for c in (choices or []))
    return bs4.BeautifulSoup(
        f"<part><mode>{mode}</mode>{choices_xml}</part>", "lxml-xml"
    ).find("part")


def test_widget_html_numeric_renders_text_input():
    part = _make_part_xml("Numeric")
    result = widget_html(part, 1)
    assert 'type="text"' in result
    assert 'data-mode="Numeric"' in result


def test_widget_html_essay_renders_textarea():
    part = _make_part_xml("Essay")
    result = widget_html(part, 1)
    assert "<textarea" in result
    assert 'data-mode="Essay"' in result


def test_widget_html_multiple_choice_renders_radio_buttons():
    part = _make_part_xml("Multiple Choice", choices=["Option A", "Option B"])
    result = widget_html(part, 1)
    assert 'type="radio"' in result
    assert "Option A" in result
    assert "Option B" in result


def test_widget_html_multiple_selection_renders_checkboxes():
    part = _make_part_xml("Multiple Selection", choices=["X", "Y"])
    result = widget_html(part, 1)
    assert 'type="checkbox"' in result
    assert "X" in result


def test_widget_html_unknown_mode_renders_fallback_input():
    part = _make_part_xml("FutureModeNotYetKnown")
    result = widget_html(part, 1)
    assert 'type="text"' in result
    assert "FutureModeNotYetKnown" in result


# ---------------------------------------------------------------------------
# write_question_previews — smoke test
# ---------------------------------------------------------------------------


def _make_minimal_xml(tmp_path, question_name="Test Question", mode="Numeric"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<root>
  <question>
    <name>{question_name}</name>
    <parts>
      <part><mode>{mode}</mode></part>
    </parts>
    <text><![CDATA[<p>What is 2+2? <1/></p>]]></text>
  </question>
</root>
"""
    xml_path = tmp_path / "sheet.xml"
    xml_path.write_text(xml, encoding="utf-8")
    return xml_path


def test_write_question_previews_creates_html_files_and_index(tmp_path):
    xml_path = _make_minimal_xml(tmp_path)
    preview_dir = tmp_path / "preview"
    preview_dir.mkdir()

    write_question_previews(str(xml_path), preview_dir)

    assert (preview_dir / "index.html").exists()
    question_pages = list(preview_dir.glob("*.html"))
    # index.html + at least one question page
    assert len(question_pages) >= 2


def test_write_question_previews_index_links_to_question_pages(tmp_path):
    xml_path = _make_minimal_xml(tmp_path, question_name="Fluid Dynamics")
    preview_dir = tmp_path / "preview"
    preview_dir.mkdir()

    write_question_previews(str(xml_path), preview_dir)

    index_html = (preview_dir / "index.html").read_text(encoding="utf-8")
    assert "Fluid Dynamics" in index_html
    assert "01-fluid-dynamics.html" in index_html


def test_write_question_previews_substitutes_placeholder_with_widget(tmp_path):
    xml_path = _make_minimal_xml(tmp_path, mode="Numeric")
    preview_dir = tmp_path / "preview"
    preview_dir.mkdir()

    write_question_previews(str(xml_path), preview_dir)

    question_pages = sorted(p for p in preview_dir.glob("0*.html"))
    assert question_pages, "expected at least one question page"
    content = question_pages[0].read_text(encoding="utf-8")
    # Placeholder <1/> should have been replaced with a widget input
    assert 'type="text"' in content
    assert "<1/>" not in content
