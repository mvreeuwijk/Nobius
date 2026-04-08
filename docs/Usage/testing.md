# Testing

Nobius now includes a pytest regression suite covering the shared renderer, the Mobius import path, and XML scraping.

## Running the suite

From the repo root:

```bash
python -m pytest -q
python -m ruff check .
```

## Fixture policy

The tests use only public, non-exam fixtures:

- tutorial sheets under `Questions/t01` and `Questions/t02`
- the bundled XML fixture at `xml_scraper/tests/experimental_sheet.xml`

This keeps the public repo free of private assessment material while still testing:

- standard rendering
- exam-template rendering
- ZIP round-trips
- XML import
- config overrides
- custom responses
- algorithmic questions
- batch rendering
- PDF exporter error handling
- report generation

## Temporary files

The test suite creates temporary working copies under `tests_work/` inside the repo and deletes them after each test. The folder is ignored by git.
