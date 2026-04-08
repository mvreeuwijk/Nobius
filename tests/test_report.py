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
