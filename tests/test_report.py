from import_report import ImportReport


def test_import_report_uses_timezone_aware_utc_timestamp():
    report = ImportReport("source", "zip", "dest", True)

    assert report.created_at.endswith("Z")
    assert "+00:00" not in report.created_at


def test_import_report_write_returns_string_paths(tmp_path):
    report = ImportReport("source", "zip", str(tmp_path), False)

    json_path, text_path = report.write(tmp_path)

    assert isinstance(json_path, str)
    assert isinstance(text_path, str)


def test_import_report_includes_scoped_warning_context_in_text_output():
    report = ImportReport("source", "zip", "dest", False)
    report.metadata["manifest_path"] = "manifest.xml"

    with report.scoped_context(manifest_path="manifest.xml", line=42, item_type="question", item_name="1 Lock"):
        report.warn("Response area tag couldn't be found in element.", "parts.1.response")

    text = report.to_text()

    assert "Manifest: manifest.xml" in text
    assert "question: 1 Lock" in text
    assert "manifest.xml:42" in text
    assert "parts.1.response" in text
