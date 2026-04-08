# Welcome to the Nobius docs

Nobius is a set of utilities for authoring, rendering, and re-importing [Möbius](https://www.digitaled.com/products/assessment) content from local JSON source files.

The current workflow is built around three ideas:

- keep authored content in version-controlled JSON rather than only in the Möbius editor
- render that content into Möbius-ready XML and ZIP packages
- import Möbius exports back into Nobius when edits are made in the platform

Nobius also supports a first-class `HTML` response mode for custom interactive widgets, in addition to standard response areas and custom response layouts.

Make sure to visit the [Quickstart Guide](quickstart.md) to get started.

## Recommended entry points

- [Quickstart Guide](quickstart.md)
- [generateGroup.py](Usage/generateGroup.md)
  Exam-style rendering uses the same command with `--render-profile exam`.
- [generateJSON.py](Usage/generateJSON.md)
- [HTML response mode](ResponseAreas/Advanced/html.md)
- [Testing](Usage/testing.md)

## Our Philosophy

![Tool Philosophy](Assets/Images/Tool.jpg)

As an author, your time is best spent generating and refining content, not worrying how you should style or lay it out. The separation of these two main aspects of content creation was the main idea behind Nobius.

Questions tend to share a common structure: statements, parts, answers, feedback, and media. Nobius keeps that structure explicit so content is easier to validate, version, and regenerate. At the same time, it still leaves room for controlled customization where that is genuinely needed.
