# Testing

Nobius includes a pytest regression suite covering the shared renderer, the Mobius import path, and XML scraping.

## Running the suite

From the Nobius repo root:

```bash
pytest -q tests
python -m ruff check Nobius
```

If you are already inside the `Nobius/` directory, the equivalent commands are:

```bash
pytest -q tests
python -m ruff check .
```

The recommended local validation before pushing changes is:

- `python -m ruff check Nobius` from the outer repo root, or `python -m ruff check .` from `Nobius/`
- `pytest -q tests` from `Nobius/`

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
- assignment-unit and multi-assignment import hierarchy
- config overrides
- custom responses
- algorithmic questions
- batch rendering
- PDF exporter error handling
- report generation and warning formatting

## Temporary files

The test suite creates temporary working copies under the system temporary directory (for example `%TEMP%` on Windows) inside a `nobius_pytest/` folder and deletes them after each test.
