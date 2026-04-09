import html
import re
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

import bs4

from cli_common import build_render_parser, load_config, resolve_render_profile
from render_common import render_sheet


PLACEHOLDER_RE = re.compile(r"<(\d+)\s*/?>")
THEME_CSS_PATH = Path(__file__).resolve().parent / "templates" / "themes" / "mobius_tabular_question.css"
THEME_PREVIEW_JS_PATH = Path(__file__).resolve().parent / "templates" / "themes" / "mobius_tabular_question_preview.js"
PREVIEW_PLATFORM_CSS_PATH = Path(__file__).resolve().parent / "templates" / "themes" / "mobius_preview_platform.css"

PREVIEW_BASE_CSS = """\
html {
  font-size: 12px;
}

body {
  font-family: "Segoe UI", Arial, sans-serif;
  line-height: 1.45;
  margin: 2rem;
  color: #1f2937;
  background: #f8fafc;
}

.preview-page {
  max-width: 1100px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #dbe3ee;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  padding: 2rem;
}

.preview-note {
  margin-bottom: 1.5rem;
  padding: 0.75rem 1rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}

.preview-widget {
  display: inline-block;
  min-width: 12rem;
  margin: 0.25rem 0;
  vertical-align: middle;
}

.preview-widget input[type="text"],
.preview-widget textarea,
.preview-widget select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #94a3b8;
  border-radius: 0.375rem;
  padding: 0.5rem 0.65rem;
  background: #ffffff;
}

.preview-widget textarea {
  min-height: 7rem;
  resize: vertical;
}

.preview-widget fieldset {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.375rem;
  background: #f8fafc;
}

.preview-widget legend {
  padding: 0 0.35rem;
  font-size: 0.85rem;
  color: #475569;
}

.preview-widget label {
  display: block;
  margin: 0.3rem 0;
}

.preview-choice {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem;
  align-items: start;
  margin: 0.4rem 0;
}

.preview-choice-input {
  padding-top: 0.2rem;
}

.preview-choice-body > :first-child {
  margin-top: 0;
}

.preview-choice-body > :last-child {
  margin-bottom: 0;
}

.preview-matrix {
  border-collapse: collapse;
}

.preview-matrix td {
  padding: 0.25rem;
}

.preview-index ul {
  line-height: 1.8;
}

.preview-index code {
  background: #eef2ff;
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
}
"""

MATHJAX_SCRIPT = """\
<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']]
  },
  svg: {
    fontCache: 'global'
  }
};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
"""


def load_preview_css():
    return (
        PREVIEW_BASE_CSS
        + "\n\n"
        + PREVIEW_PLATFORM_CSS_PATH.read_text(encoding="utf-8")
        + "\n\n"
        + THEME_CSS_PATH.read_text(encoding="utf-8")
    )


def load_preview_script():
    return "<script>\n" + THEME_PREVIEW_JS_PATH.read_text(encoding="utf-8") + "\n</script>"


def parse_args():
    parser = build_render_parser(
        "Render a Nobius sheet and create browser-openable HTML previews for each question.",
        "Path to a Nobius sheet directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory for the generated preview site. Defaults to <sheet>/renders/<sheet>_preview.",
    )
    return parser.parse_args()


def slugify(value):
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "question"


def extract_assets(zip_path, destination):
    assets_dir = destination / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        safe_extract_archive(archive, assets_dir)
    return assets_dir


def safe_extract_archive(archive, destination):
    destination = destination.resolve()
    for member in archive.infolist():
        member_path = destination / member.filename
        resolved_path = member_path.resolve()
        if destination not in resolved_path.parents and resolved_path != destination:
            raise ValueError(f"Refusing to extract unsafe zip member: {member.filename}")
        archive.extract(member, destination)


def fragment_to_html(fragment):
    fragment_soup = bs4.BeautifulSoup(fragment, "html.parser")
    body = fragment_soup.body
    if body is not None:
        return "".join(str(child) for child in body.contents)
    return str(fragment_soup)


def widget_html(part, placeholder_number):
    mode = part.find("mode").get_text(strip=True) if part.find("mode") else "Unknown"

    if mode in {"List", "Numeric", "Maple"}:
        return (
            f'<span class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="{html.escape(mode)}"><input type="text" '
            f'placeholder="{html.escape(mode)} response"></span>'
        )

    if mode == "Essay":
        return (
            f'<span class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="{html.escape(mode)}"><textarea '
            f'placeholder="Essay response"></textarea></span>'
        )

    if mode in {"Non Permuting Multiple Choice", "Multiple Choice"}:
        choices = [fragment_to_html(choice.get_text()) for choice in part.find_all("choice")]
        choice_markup = "".join(
            '<div class="preview-choice">'
            f'<label class="preview-choice-input"><input type="radio" name="preview-{placeholder_number}"></label>'
            f'<div class="preview-choice-body">{choice}</div>'
            "</div>"
            for choice in choices
        )
        return (
            f'<div class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="{html.escape(mode)}"><fieldset><legend>{html.escape(mode)}</legend>'
            f"{choice_markup}</fieldset></div>"
        )

    if mode in {"Non Permuting Multiple Selection", "Multiple Selection"}:
        choices = [fragment_to_html(choice.get_text()) for choice in part.find_all("choice")]
        choice_markup = "".join(
            '<div class="preview-choice">'
            '<label class="preview-choice-input"><input type="checkbox"></label>'
            f'<div class="preview-choice-body">{choice}</div>'
            "</div>"
            for choice in choices
        )
        return (
            f'<div class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="{html.escape(mode)}"><fieldset><legend>{html.escape(mode)}</legend>'
            f"{choice_markup}</fieldset></div>"
        )

    if mode == "Matching":
        matches = []
        for match in part.find_all("match"):
            term = match.find("term").get_text(" ", strip=True) if match.find("term") else ""
            defs = [definition.get_text(" ", strip=True) for definition in match.find_all("def")]
            matches.append((term, defs))
        rows = []
        for index, (term, definitions) in enumerate(matches):
            options = "".join(f'<option>{html.escape(item)}</option>' for item in definitions)
            rows.append(
                "<tr>"
                f"<td>{html.escape(term)}</td>"
                f'<td><select name="preview-match-{placeholder_number}-{index}">{options}</select></td>'
                "</tr>"
            )
        return (
            f'<div class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="{html.escape(mode)}"><table class="preview-matrix">{"".join(rows)}</table></div>'
        )

    return (
        f'<span class="preview-widget" data-placeholder="{placeholder_number}" '
        f'data-mode="{html.escape(mode)}"><input type="text" '
        f'placeholder="{html.escape(mode)} preview"></span>'
    )


def substitute_placeholders(text_html, parts):
    def replacer(match):
        placeholder_number = int(match.group(1))
        if 1 <= placeholder_number <= len(parts):
            return widget_html(parts[placeholder_number - 1], placeholder_number)
        return (
            f'<span class="preview-widget" data-placeholder="{placeholder_number}" '
            f'data-mode="Unknown"><input type="text" placeholder="Missing part"></span>'
        )

    return PLACEHOLDER_RE.sub(replacer, text_html)


def normalize_preview_html(text_html):
    soup = bs4.BeautifulSoup(text_html, "html.parser")

    for link in soup.find_all("link", href=True):
        href = link["href"]
        if href.startswith("/themes/") or href == "__BASE_URI__QuestionTheme.css":
            link.decompose()

    for script in soup.find_all("script"):
        script.decompose()

    for media_tag in soup.find_all(src=True):
        src = media_tag["src"]
        if src.startswith("__BASE_URI__"):
            media_tag["src"] = "assets/" + src.replace("__BASE_URI__", "web_folders/")

    for element in soup.find_all(string=True):
        if "\u00c2\u00a0" in element:
            element.replace_with(element.replace("\u00c2\u00a0", "\u00a0"))

    return str(soup)


def build_preview_page(question_name, body_html):
    preview_css = load_preview_css()
    preview_script = load_preview_script()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(question_name)} Preview</title>
  <style>
{preview_css}
  </style>
</head>
  <body>
  <main class="preview-page">
    <div class="preview-note">
      Preview generated from rendered question CDATA. Mobius placeholders have been replaced with local widgets.
    </div>
    {body_html}
  </main>
  {MATHJAX_SCRIPT}
  {preview_script}
</body>
</html>
"""


def write_question_previews(xml_path, preview_dir):
    soup = bs4.BeautifulSoup(Path(xml_path).read_text(encoding="utf-8"), "lxml-xml")
    questions = soup.find_all("question")
    index_entries = []
    preview_css = load_preview_css()

    for question_index, question in enumerate(questions, start=1):
        name = question.find("name").get_text(" ", strip=True)
        parts = question.find("parts").find_all("part", recursive=False) if question.find("parts") else []
        text_node = question.find("text")
        text_html = text_node.get_text() if text_node else ""
        text_html = substitute_placeholders(text_html, parts)
        text_html = normalize_preview_html(text_html)

        filename = f"{question_index:02d}-{slugify(name)}.html"
        (preview_dir / filename).write_text(build_preview_page(name, text_html), encoding="utf-8")
        index_entries.append((name, filename))

    index_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nobius HTML Preview</title>
  <style>
{styles}
  </style>
</head>
<body>
  <main class="preview-page preview-index">
    <h1>Nobius HTML Preview</h1>
    <p>Each page below is rendered from the generated question CDATA with placeholder widgets substituted locally.</p>
    <ul>
      {items}
    </ul>
  </main>
</body>
</html>
""".format(
        styles=preview_css,
        items="".join(
            f'<li><a href="{html.escape(filename)}">{html.escape(name)}</a> <code>{html.escape(filename)}</code></li>'
            for name, filename in index_entries
        )
    )
    (preview_dir / "index.html").write_text(index_html, encoding="utf-8")


def main():
    args = parse_args()
    config, _ = load_config(args.config)
    profile = resolve_render_profile(config, args.render_profile)

    render_result = render_sheet(
        args.filepath,
        profile["template_name"],
        profile["render_settings"],
        reset_uid=args.reset_uid,
        write_missing_uids=args.write_missing_uids,
        output_dir=args.batch_destination,
    )

    sheet_path = Path(args.filepath)
    sheet_name = Path(render_result["xml_path"]).stem
    preview_dir = (
        Path(args.output_dir)
        if args.output_dir
        else sheet_path / "renders" / f"{sheet_name}_preview"
    )

    if preview_dir.exists():
        try:
            shutil.rmtree(preview_dir)
        except PermissionError:
            preview_dir = preview_dir.parent / f"{preview_dir.name}_{uuid4().hex[:8]}"
    preview_dir.mkdir(parents=True, exist_ok=True)

    extract_assets(render_result["zip_path"], preview_dir)
    write_question_previews(render_result["xml_path"], preview_dir)

    print(f"[DONE] HTML preview written to {preview_dir}")


if __name__ == "__main__":
    main()
