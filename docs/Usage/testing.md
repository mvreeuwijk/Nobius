# Testing

Nobius includes a pytest regression suite covering the shared renderer, the Mobius import path, and XML scraping.

## Running the suite

From the repo root:

```bash
python -m pytest -q
python -m ruff check .
```

## Fixture policy

The tests use only public, non-exam fixtures:

- repo-local authored sheet fixtures under `tests/fixtures/t01` and `tests/fixtures/t02`
- a real Mobius export fixture at `tests/fixtures/mobius_exports/QuestionTypesDemo.zip`
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

The test suite creates temporary working copies under the system temporary directory (for example `%TEMP%` on Windows) inside a `nobius_pytest/` folder and deletes them after each test.
