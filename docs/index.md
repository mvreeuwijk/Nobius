# Welcome to the Nobius docs

Nobius is a set of utilities for authoring, exporting, previewing, and re-importing [Mobius](https://www.digitaled.com/products/assessment) content from local JSON source files.

The current workflow is built around four main entry points:

- keep authored content in version-controlled JSON rather than only in the Mobius editor
- export that content into Mobius-ready XML and ZIP packages
- preview the rendered output locally in HTML
- import Mobius exports back into Nobius when edits are made in the platform

Nobius also supports a first-class `HTML` response mode for custom interactive widgets, in addition to standard response areas and custom response layouts.[^fork]

Make sure to visit the [Quickstart Guide](quickstart.md) to get started.

[^fork]: This documentation is published from the fork at [github.com/mvreeuwijk/Nobius](https://github.com/mvreeuwijk/Nobius), based on the original Nobius project.

## Recommended entry points

- [Quickstart Guide](quickstart.md)
- [export_mobius.py](Usage/export_mobius.md)
  Exam-style rendering uses the same command with `--render-profile exam`.
- [preview_html.py](Usage/preview_html.md)
- [export_pdf.py](Usage/export_pdf.md)
- [import_mobius.py](Usage/import_mobius.md)
- [HTML response mode](ResponseAreas/Advanced/html.md)
- [Testing](Usage/testing.md)

## Our Philosophy

![Tool Philosophy](Assets/Images/Tool.jpg)

As an author, your time is best spent generating and refining content, not worrying how you should style or lay it out. The separation of these two main aspects of content creation was the main idea behind Nobius.

Questions tend to share a common structure: statements, parts, answers, feedback, and media. Nobius keeps that structure explicit so content is easier to validate, version, and regenerate. At the same time, it still leaves room for controlled customization where that is genuinely needed.
