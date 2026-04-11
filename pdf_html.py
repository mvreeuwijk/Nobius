# -*- coding: utf-8 -*-
"""
HTML-to-LaTeX conversion for Nobius PDF export.

Converts a subset of HTML (as produced by the Mobius editor) into LaTeX
fragments suitable for inclusion in the generated .tex files.  Only tags
listed in ``_HTML_SUPPORTED_TAGS`` receive explicit LaTeX wrappers; tags
in ``_HTML_TRANSPARENT_TAGS`` are rendered by descending into their
children; any other tag triggers a one-time warning and is also descended
transparently so that text content is never silently dropped.
"""

from __future__ import annotations

import re

import bs4


def escape_tex_text(text: str) -> str:
    """Escape the handful of special characters that appear in raw HTML text nodes.

    This is a light-touch escape intended for HTML text content where the
    author may have used ``&``, ``%``, or ``#`` as literal characters.  It
    does *not* escape backslash or braces because those are already valid TeX
    in this context.
    """
    if not text:
        return ""

    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("\xa0", "~"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def normalize_tex_list_environments(text: str) -> str:
    """Normalise ``enumitem`` label syntax to the ``enumerate`` package style.

    Mobius sometimes emits ``\\begin{enumerate}[label=\\alph*)]``; the
    generated .tex files use the ``enumerate`` package which expects
    ``\\begin{enumerate}[(a)]`` style instead.
    """
    if not text:
        return text

    replacements = [
        (r"\\begin\{enumerate\}\s*\[label=\\alph\*\)\]", r"\\begin{enumerate}[(a)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\Alph\*\)\]", r"\\begin{enumerate}[(A)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\roman\*\)\]", r"\\begin{enumerate}[(i)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\Roman\*\)\]", r"\\begin{enumerate}[(I)]"),
        (r"\\begin\{enumerate\}\s*\[label=\\arabic\*\)\]", r"\\begin{enumerate}[1.]"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def render_html_table(table_tag: bs4.element.Tag) -> str:
    """Convert a ``<table>`` BS4 tag to a LaTeX ``tabularx`` environment."""
    rows = []
    for tr in table_tag.find_all("tr", recursive=False):
        cells = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            cell_text = render_html_fragment(cell).strip()
            cell_text = re.sub(r"\s+", " ", cell_text)
            cells.append(cell_text)
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    colspec = "@{}" + "X" * max_cols + "@{}"

    lines = [r"\begin{center}", rf"\begin{{tabularx}}{{\linewidth}}{{{colspec}}}"]
    if normalized_rows:
        lines.append(r"\toprule")
        header = normalized_rows[0]
        lines.append(" & ".join(header) + r"\\")
        if len(normalized_rows) > 1:
            lines.append(r"\midrule")
            for row in normalized_rows[1:]:
                lines.append(" & ".join(row) + r"\\")
        lines.append(r"\bottomrule")
    lines.append(r"\end{tabularx}")
    lines.append(r"\end{center}")
    return "\n".join(lines)


# Tags that render_html_fragment actively converts to LaTeX equivalents.
_HTML_SUPPORTED_TAGS = {"br", "i", "em", "b", "strong", "p", "ul", "ol", "li", "table"}

# Tags whose children are rendered transparently (no LaTeX wrapper emitted).
_HTML_TRANSPARENT_TAGS = {"thead", "tbody", "tr", "td", "th", "div", "span"}

# Tracks unsupported tags already warned about this process to avoid log spam.
_html_warned_tags: set[str] = set()


def reset_html_warnings() -> None:
    """Clear the set of already-warned unsupported HTML tags.

    Call this between test cases to ensure each test sees warnings independently.
    """
    _html_warned_tags.clear()


def render_html_fragment(node: bs4.element.PageElement | None) -> str:
    """Recursively convert a BS4 node to a LaTeX string fragment."""
    if node is None:
        return ""

    if isinstance(node, bs4.element.NavigableString):
        return escape_tex_text(str(node))

    if not isinstance(node, bs4.element.Tag):
        return ""

    name = node.name.lower()

    if name == "br":
        return "\n"
    if name in {"i", "em"}:
        return r"\emph{" + "".join(render_html_fragment(child) for child in node.children) + "}"
    if name in {"b", "strong"}:
        return r"\textbf{" + "".join(render_html_fragment(child) for child in node.children) + "}"
    if name == "p":
        return "\n\n" + "".join(render_html_fragment(child) for child in node.children).strip() + "\n\n"
    if name == "ul":
        items = []
        for child in node.find_all("li", recursive=False):
            item_text = "".join(render_html_fragment(grandchild) for grandchild in child.children).strip()
            items.append(r"\item " + item_text)
        return "\n\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}\n"
    if name == "ol":
        items = []
        for child in node.find_all("li", recursive=False):
            item_text = "".join(render_html_fragment(grandchild) for grandchild in child.children).strip()
            items.append(r"\item " + item_text)
        return "\n\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n"
    if name == "table":
        return "\n" + render_html_table(node) + "\n"
    if name in _HTML_TRANSPARENT_TAGS:
        return "".join(render_html_fragment(child) for child in node.children)

    if name not in _html_warned_tags:
        print(f"[WARNING] html_to_tex: unsupported HTML tag <{name}> — children rendered as plain text")
        _html_warned_tags.add(name)
    return "".join(render_html_fragment(child) for child in node.children)


HTML_TAG_PATTERN = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")
HTML_ENTITY_PATTERN = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);")


def looks_like_html_markup(input_text: str) -> bool:
    """Return ``True`` if *input_text* contains HTML tags or entities."""
    if not isinstance(input_text, str):
        return False
    return bool(HTML_TAG_PATTERN.search(input_text) or HTML_ENTITY_PATTERN.search(input_text))


def html_to_tex(input_text: str) -> str:
    """Convert an HTML string (or plain-text TeX) to a LaTeX fragment.

    If the input contains no HTML markup the string is returned unchanged
    (after normalising list environment syntax).  This means plain-text TeX
    authored directly in Mobius passes through untouched.
    """
    if not input_text:
        return ""

    input_text = normalize_tex_list_environments(input_text)

    if not looks_like_html_markup(input_text):
        return input_text

    soup = bs4.BeautifulSoup(input_text, "html.parser")
    rendered = "".join(render_html_fragment(child) for child in soup.contents)
    rendered = normalize_tex_list_environments(rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()
