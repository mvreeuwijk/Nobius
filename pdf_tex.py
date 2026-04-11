# -*- coding: utf-8 -*-
"""
Pure TeX text-transformation helpers for Nobius PDF export.

This module contains functions that transform strings into TeX-safe output:
escaping special characters, normalising inline math, protecting unresolved
algorithm tokens, rewriting graphics paths, namespacing cross-reference
labels, and processing worked-solution figures.  None of these functions
depend on Nobius domain objects or configuration; they operate on plain
strings.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Character escaping
# ---------------------------------------------------------------------------


def tex_escape_text(value: object) -> str:
    """Escape a value for use as plain LaTeX text.

    Handles the full set of LaTeX special characters: ``\\ & % # _ { }``.
    ``None`` is converted to an empty string.
    """
    if value is None:
        return ""

    text = str(value)
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def tex_escape_code_text(value: object) -> str:
    """Escape a value for use inside a ``\\texttt{}`` span.

    Extends :func:`tex_escape_text` with ``$`` and ``^`` escapes that are
    needed inside verbatim-like contexts.
    """
    text = tex_escape_text(value)
    text = text.replace("$", r"\$")
    text = text.replace("^", r"\^{}")
    return text


# ---------------------------------------------------------------------------
# Inline math normalisation
# ---------------------------------------------------------------------------


def normalize_inline_tex_math(text: str) -> str:
    """Replace ``$…$`` delimiters with ``\\(…\\)`` where unambiguous.

    Only replaces single ``$`` pairs that are delimited by whitespace,
    punctuation, or line boundaries — never ``$$`` display math.
    """
    if not text:
        return text

    return re.sub(
        r"(?:(?<=^)|(?<=[\s(\[{]))\$(?!\$)(.+?)(?<!\$)\$(?=(?:[\s\\\.,;:!?\)\]}]|$))",
        lambda match: r"\(" + match.group(1).strip() + r"\)",
        text,
        flags=re.S,
    )


def escape_unmatched_numeric_dollar_signs(text: str) -> str:
    """Escape ``$`` signs immediately followed by a digit (currency amounts)."""
    if not text:
        return text

    return re.sub(r"(?<!\\)\$(?=\d)", r"\\$", text)


def escape_literal_percent_signs(text: str) -> str:
    """Escape unescaped ``%`` signs that would otherwise start TeX comments."""
    if not text:
        return text

    return re.sub(r"(?<!\\)%", r"\\%", text)


def protect_unresolved_algorithm_tokens(text: str) -> str:
    """Protect any ``$VAR`` algorithm tokens that were not substituted.

    First normalises inline math and currency dollar signs, then wraps each
    remaining ``$IDENTIFIER`` in ``\\texttt{[$...]}`` so the PDF shows a
    visible placeholder rather than breaking compilation.
    """
    if not text:
        return text

    text = normalize_inline_tex_math(text)
    text = escape_unmatched_numeric_dollar_signs(text)
    text = escape_literal_percent_signs(text)

    return re.sub(
        r"(?<!\\)\$([A-Za-z][A-Za-z0-9_]*)",
        lambda match: r"\texttt{[\$" + match.group(1) + "]}",
        text,
    )


def format_response_target_value(value: object) -> str:
    """Format a numeric response target for display in review sheets.

    If the value still contains an unresolved algorithm token the result is
    already wrapped in ``\\texttt``; otherwise the value is escaped and
    wrapped in ``\\texttt`` explicitly.
    """
    raw = "" if value is None else str(value)
    protected = protect_unresolved_algorithm_tokens(raw)
    if r"\texttt{[\$" in protected:
        return protected
    return r"\texttt{" + tex_escape_code_text(raw) + "}"


# ---------------------------------------------------------------------------
# TeX source pre-processing
# ---------------------------------------------------------------------------


def preprocess_tex_like_text(text: str) -> str:
    """Apply a small set of fixes to raw TeX source before further processing.

    - Strips TeX comment lines (lines whose first non-whitespace char is ``%``).
    - Normalises ``\\d`` (derivative operator) to ``\\mathrm{d}``.
    - Rewrites ``X$^{…}$`` unit-exponent shorthand to ``X\\(^{…}\\)``.
    """
    if not text:
        return text

    lines = []
    for line in str(text).splitlines():
        if line.lstrip().startswith("%"):
            continue
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\\d(?=\s*[A-Za-z({])", r"\\mathrm{d}", text)
    text = re.sub(r"([A-Za-z])\$\^(\{[^}]+\}|[^$]+)\$", r"\1\\(^\2\\)", text)
    return text


# ---------------------------------------------------------------------------
# Graphics path helpers
# ---------------------------------------------------------------------------


def tex_graphics_path(path: str) -> str:
    """Return the path as it should appear inside ``\\includegraphics{}``.

    Bare filenames (no directory component) are resolved relative to the
    sheet's ``../media/`` directory.  Paths that already include a ``/`` or
    start with ``.`` are returned unchanged.
    """
    if not path:
        return path

    normalized = str(path).replace("\\", "/")
    if "/" in normalized or normalized.startswith("."):
        return normalized
    return "../media/" + normalized


def prefix_includegraphics_paths(text: str) -> str:
    """Rewrite bare filenames in ``\\includegraphics`` commands to media paths."""
    if not text:
        return text

    pattern = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")

    def replace(match: re.Match) -> str:
        return match.group(1) + tex_graphics_path(match.group(2)) + match.group(3)

    return pattern.sub(replace, text)


def inline_worked_solution_figures(text: str) -> str:
    """Replace ``figure`` floats with inline centred images.

    LaTeX floats do not behave well inside the ``exobox`` and enumeration
    environments used in solution sheets, so each ``\\begin{figure}…\\end{figure}``
    block is flattened into a ``\\begin{center}`` group with an inline caption.
    """
    if not text:
        return text

    figure_pattern = re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.S)

    def replace(match: re.Match) -> str:
        body = match.group(1)
        images = re.findall(r"(\\includegraphics(?:\[[^\]]*\])?\{[^}]+\})", body)
        images = [prefix_includegraphics_paths(image) for image in images]
        caption_match = re.search(r"\\caption(?:\[[^\]]*\])?\{(.*?)\}", body, re.S)
        labels = re.findall(r"\\label\{([^}]+)\}", body)

        lines = [r"\par\begin{center}", r"\refstepcounter{figure}"]
        lines.extend(images)

        caption_text = caption_match.group(1).strip() if caption_match else ""
        if caption_text:
            lines.append(r"\par\small\textit{Figure \thefigure: " + caption_text + "}")

        for label in labels:
            lines.append(r"\label{" + label + "}")

        lines.append(r"\end{center}\par")
        return "\n".join(lines)

    return figure_pattern.sub(replace, text)


# ---------------------------------------------------------------------------
# Cross-reference label namespacing
# ---------------------------------------------------------------------------


def make_tex_label_namespace(value: object) -> str:
    """Derive a safe TeX label namespace from an arbitrary string.

    Non-alphanumeric runs are replaced with ``-``; the result is lowercased.
    Falls back to ``"nobius"`` if the input is empty or ``None``.
    """
    if value is None:
        return "nobius"

    namespace = re.sub(r"[^A-Za-z0-9]+", "-", str(value)).strip("-").lower()
    return namespace or "nobius"


def namespace_tex_labels(text: str, namespace: str) -> str:
    """Prefix all ``\\label``, ``\\ref``, ``\\eqref`` etc. with *namespace*.

    This prevents label collisions when multiple questions are assembled into
    a single document.  The set of rewritten commands is:
    ``label``, ``ref``, ``eqref``, ``pageref``, ``autoref``, ``nameref``.
    """
    if not text or not namespace:
        return text

    commands = ("label", "ref", "eqref", "pageref", "autoref", "nameref")

    def replace(match: re.Match) -> str:
        command = match.group(1)
        label = match.group(2)
        return "\\" + command + "{" + namespace + ":" + label + "}"

    pattern = r"\\(" + "|".join(commands) + r")\{([^}]+)\}"
    return re.sub(pattern, replace, text)


# ---------------------------------------------------------------------------
# Algorithm helpers
# ---------------------------------------------------------------------------


def clean_algorithm(input_text: str, pdf_values: list) -> str:
    """Substitute algorithmic variable values into *input_text*.

    ``pdf_values`` is a list of ``(variable_name, variable_value)`` pairs as
    stored in the JSON ``PDF_values`` field.  The regex excludes matches
    followed by ``D`` or ``2`` to avoid partial matches (e.g. ``$TA`` inside
    ``$TAD``).
    """
    for variable_name, variable_value in pdf_values:
        input_text = re.sub(r"\$" + variable_name + r"(?!D|2)", str(variable_value), input_text)
    return input_text


def format_algorithm(input_text: str) -> str:
    """Format an algorithm string for display (strips ``$`` prefixes, expands ``;``)."""
    replacements = [
        (r"\$", r""),
        (r";", r";}\\newline\\text{"),
    ]

    for pattern, replacement in replacements:
        input_text = re.sub(pattern, replacement, input_text)
    return input_text


def split_algorithm_commands(input_text: str) -> list[str]:
    """Split an algorithm string into individual semicolon-terminated commands.

    Empty lines and blank fragments are skipped.  Each returned command ends
    with a ``;``.
    """
    if not input_text:
        return []

    commands = []
    for line in str(input_text).splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue

        fragments = [fragment.strip() for fragment in stripped_line.split(";")]
        for fragment in fragments:
            if fragment:
                commands.append(fragment + ";")

    return commands


def apply_algorithm_values(text: str, content: dict) -> str:
    """Substitute PDF algorithm values into *text* if the content has an algorithm.

    A thin wrapper around :func:`clean_algorithm` that checks for the
    ``algorithm`` and ``PDF_values`` keys before substituting.
    """
    if "algorithm" in content and "PDF_values" in content:
        return clean_algorithm(text, content["PDF_values"])
    return text
