"""Generate the complete themed Scriptronaut QC documentation website."""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any
from datetime import datetime


# HTML elements that never contain child content and therefore do not
# increase indentation when pretty-printing generated pages.
VOID_HTML_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

HTML_TOKEN_RE = re.compile(
    r"(<!--.*?-->|<![^>]*>|<[^>]+>)",
    re.DOTALL,
)


def format_html(source: str, indent_size: int = 4, line_width: int = 120) -> str:
    """
    Pretty-print generated HTML using deterministic 4-space indentation.

    The documentation generator creates controlled HTML, so a lightweight
    formatter is sufficient and avoids adding a third-party dependency such
    as BeautifulSoup or html-tidy to the build process.

    Args:
        source:
            Raw generated HTML.

        indent_size:
            Spaces per nesting level. Defaults to 4.

        line_width:
            Approximate width used when wrapping plain text nodes. Tag lines
            are intentionally kept intact so attributes remain easy to scan.

    Returns:
        Formatted HTML ending with exactly one newline.
    """
    tokens = HTML_TOKEN_RE.split(source)
    lines: list[str] = []
    depth = 0

    def emit(value: str, current_depth: int | None = None) -> None:
        value = value.strip()
        if not value:
            return

        level = depth if current_depth is None else current_depth
        prefix = " " * (level * indent_size)
        lines.append(prefix + value)

    for token in tokens:
        if not token:
            continue

        stripped = token.strip()
        if not stripped:
            continue

        # Comments, doctype and declarations do not alter nesting depth.
        if stripped.startswith("<!--") or stripped.startswith("<!"):
            emit(stripped)
            continue

        # Closing element: move back one level before writing it.
        if stripped.startswith("</"):
            depth = max(0, depth - 1)
            emit(stripped)
            continue

        # Opening / self-closing element.
        if stripped.startswith("<"):
            emit(stripped)

            match = re.match(
                r"<\s*([A-Za-z0-9:_-]+)",
                stripped,
            )

            tag_name = (
                match.group(1).lower()
                if match
                else ""
            )

            is_self_closing = stripped.endswith("/>")

            if (
                tag_name
                and tag_name not in VOID_HTML_ELEMENTS
                and not is_self_closing
            ):
                depth += 1

            continue

        # Plain text between tags. Normal HTML collapses this whitespace, so
        # normalize it and wrap long prose without changing browser output.
        normalized_text = " ".join(stripped.split())

        if not normalized_text:
            continue

        available_width = max(
            40,
            line_width - (depth * indent_size),
        )

        wrapped_lines = textwrap.wrap(
            normalized_text,
            width=available_width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [normalized_text]

        for wrapped_line in wrapped_lines:
            emit(wrapped_line)

    return "\n".join(lines).rstrip() + "\n"


def write_html_file(path: Path, source: str) -> None:
    """Write one generated HTML document in human-readable form."""
    path.write_text(
        format_html(source),
        encoding="utf-8",
    )


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def yes_no(value: Any) -> str:
    return "Yes" if value is True else "No" if value is False else "Unknown"


def severity_label(value: str) -> str:
    return {"critical": "Critical", "warning": "Warning", "info": "Info"}.get(value, "Warning")


def category_slug(record_or_name: Any) -> str:
    if isinstance(record_or_name, dict):
        return str(record_or_name.get("categoryId") or record_or_name.get("category", "")).lower()
    return str(record_or_name).strip().lower().replace(" ", "-")


def relative_prefix(depth: int) -> str:
    return "../" * depth


def navigation(records: list[dict[str, Any]], depth: int, active_category: str = "") -> str:
    prefix = relative_prefix(depth)
    counts = Counter(record["category"] for record in records)
    links = []
    for category in sorted(counts, key=str.lower):
        active = " active" if category == active_category else ""
        links.append(
            f'<a class="nav-link{active}" href="{prefix}categories/{category_slug(category)}.html">'
            f'{esc(category)}<span>{counts[category]}</span></a>'
        )
    return (
        '<aside class="sidebar">'
        '<div class="search-wrap"><input data-site-search type="search" placeholder="Search documentation"></div>'
        '<nav><div class="nav-section"><div class="nav-title">Start</div>'
        f'<a class="nav-link" href="{prefix}index.html">Overview</a>'
        f'<a class="nav-link" href="{prefix}panel.html">Panel guide</a>'
        f'<a class="nav-link" href="{prefix}search.html">Search</a>'
        '</div><div class="nav-section"><div class="nav-title"><b class="hilite-core">Core</b> checks</div>'
        + "".join(links)
        + '</div></nav></aside>'
    )


def page_shell(
    *,
    title: str,
    description: str,
    body: str,
    records: list[dict[str, Any]],
    depth: int = 0,
    active_category: str = "",
    version: str = "1.0",
) -> str:
    """
    Builds a QC Checker documentation page shell.

    depth is relative to /site/docs/qc_checker:
        0 = /docs/qc_checker/index.html
        1 = /docs/qc_checker/categories/*.html
        2 = /docs/qc_checker/checks/<category>/*.html
    """
    qc_prefix = relative_prefix(depth)
    current_year = datetime.now().year

    # /docs/qc_checker is two levels below /site.
    site_prefix = "../../" + qc_prefix

    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="description" content="{esc(description)}">'
        f'<title>{esc(title)} — Scriptronaut QC Docs</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">'
        f'<link rel="stylesheet" href="{site_prefix}css/docs.css"></head><body>'
        '<div class="stars"></div>'
        '<div class="stars stars-medium"></div>'
        '<div class="stars stars-faint"></div>'
        '<header class="topbar">'
        f'<a class="brand" href="{site_prefix}index.html">'
        '<!--<span class="brand-mark">#</span>-->'
        f'<img src="{site_prefix}svg/scriptronaut_name.svg" alt="Scriptronaut"></a>'
        '<div class="top-actions"><span class="hide-mobile"><b>QC Checker</b> Documentation</span>'
        f'<span class="badge hilite-core"><b>Core</b> {esc(version)}</span></div></header>'
        '<div class="shell">'
        + navigation(records, depth, active_category)
        + f'<main class="content">{body}<footer class="footer"><b>Scriptronaut</b> | QC Checker <b class="hilite-core">Core</b> documentation.'
        f'<span style="float:right;">&copy; {current_year}</span></footer></main></div>'
        f'<script src="{qc_prefix}assets/js/checks-data.js"></script>'
        f'<script src="{qc_prefix}assets/js/docs.js"></script></body></html>'
    )

def settings_table(settings: list[dict[str, Any]]) -> str:
    if not settings:
        return '<p class="status-unknown">This check has no configurable settings.</p>'
    rows = []
    for setting in settings:
        limits = []
        if "min" in setting:
            limits.append(f'Min: {esc(setting["min"])}')
        if "max" in setting:
            limits.append(f'Max: {esc(setting["max"])}')
        rows.append(
            '<tr>'
            f'<th>{esc(setting.get("label"))}</th>'
            f'<td><code>{esc(setting.get("id"))}</code></td>'
            f'<td>{esc(setting.get("type"))}</td>'
            f'<td>{esc(setting.get("default"))}</td>'
            f'<td>{esc(setting.get("description"))}<div class="small">{" · ".join(limits)}</div></td>'
            '</tr>'
        )
    return (
        '<div class="table-scroll"><table class="feature-table"><thead><tr>'
        '<th>Setting</th><th>ID</th><th>Type</th><th>Default</th><th>Description</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def generate_site(
    data_path: str | Path,
    template_site: str | Path,
    output_dir: str | Path,
    version: str = "1.0",
) -> None:
    data_path = Path(data_path).resolve()
    template_site = Path(template_site).resolve()
    output_dir = Path(output_dir).resolve()
    records = json.loads(data_path.read_text(encoding="utf-8"))

    required_template_files = (
        template_site / "css/docs.css",
        template_site / "svg/scriptronaut_name.svg",
        template_site / "svg/scriptronaut_character.svg",
        template_site / "index.html",
        template_site / "docs/qc_checker/panel.html",
        template_site / "docs/qc_checker/assets/js/docs.js",
    )
    missing_template_files = [
        path for path in required_template_files if not path.is_file()
    ]
    if missing_template_files:
        missing_text = "\n".join(
            "  - {}".format(path) for path in missing_template_files
        )
        raise FileNotFoundError(
            "The documentation template is missing required style/assets:\n"
            + missing_text
        )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(template_site, output_dir)

    # Generated QC Checker documentation lives here.
    qc_output = output_dir / "docs" / "qc_checker"
    qc_output.mkdir(parents=True, exist_ok=True)

    categories = sorted({record["category"] for record in records}, key=str.lower)
    counts = Counter(record["category"] for record in records)

    # Generated data files.
    data_out = qc_output / "assets/data/checks.json"
    data_out.parent.mkdir(parents=True, exist_ok=True)
    data_out.write_text(json.dumps(records, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    js_out = qc_output / "assets/js/checks-data.js"
    js_out.parent.mkdir(parents=True, exist_ok=True)
    js_out.write_text(
        "/* Auto-generated. Do not edit manually. */\n\n"
        f"window.QC_CHECKS = {json.dumps(records, indent=4, ensure_ascii=False)};\n",
        encoding="utf-8",
    )

    category_cards = "".join(
        f'<a class="card" href="categories/{category_slug(category)}.html"><h3>{esc(category)}</h3>'
        f'<p>Browse the {esc(category.lower())} checks included with QC Checker <b class="hilite-core">Core</b>.</p>'
        f'<span class="count">{counts[category]} checks →</span></a>'
        for category in categories
    )
    index_body = (
        '<div class="eyebrow">Official Documentation</div><h1>QC Checker <b class="hilite-core">Core</b></h1>'
        f'<p class="lead">Production-focused documentation for the QC Checker interface and the <b class="hilite-core">{len(records)}</b> checks included with the <b class="hilite-core">Core</b> edition.</p>'
        '<section class="hero-card"><div><h2 style="margin-top:0">Start with the panel</h2>'
        '<p class="lead" style="font-size:1rem">Learn how to run checks, read severity, inspect failures, select affected geometry, apply fixes and edit check settings.</p>'
        '<div class="actions"><a class="button primary" href="panel.html">Open panel guide →</a>'
        '<a class="button" href="categories/animation.html">Browse checks</a></div></div>'
        '<div class="astronaut-wrap" id="astronaut">'
        '<img src="../../svg/scriptronaut_character.svg" alt="Scriptronaut character">'
        '</div>'
        '</section>'
        '<h2><b class="hilite-core">Core</b> categories</h2><div class="grid">' + category_cards + '</div>'
        '<!--<h2>Check Packs</h2><div class="callout">Future Packs can use the same generated page system while remaining separate from Core.</div>-->'
        '<!--<h2>Pro edition</h2><p class="lead">The same documentation structure can later cover batch reports, studio profiles, pipeline integrations and advanced automation.</p>-->'
    )
    write_html_file(
        qc_output / "index.html",
        page_shell(
            title="QC Checker Core",
            description="Scriptronaut . QC Checker documentation",
            body=index_body,
            records=records,
            version=version,
        ),
    )

    # Category and check pages.
    (qc_output / "categories").mkdir(parents=True, exist_ok=True)
    (qc_output / "checks").mkdir(parents=True, exist_ok=True)
    for category in categories:
        items = sorted((record for record in records if record["category"] == category), key=lambda item: item["label"].lower())
        cards = []
        for item in items:
            cards.append(
                f'<a class="card" href="../checks/{category_slug(category)}/{esc(item["id"])}.html">'
                f'<h3>{esc(item["label"])}</h3><p>{esc(item.get("description"))}</p>'
                '<div class="meta-row">'
                f'<span class="pill"><span class="dot {esc(item.get("severity", "warning"))}"></span>{esc(severity_label(item.get("severity", "warning")))}</span>'
                f'<span class="pill">Fix: {yes_no(item.get("hasFix"))}</span>'
                f'<span class="pill">Settings: {yes_no(item.get("hasSettings"))}</span>'
                '</div></a>'
            )
        category_body = (
            '<div class="breadcrumbs"><a href="../index.html">Documentation</a><span>›</span><b class="hilite-core">Core</b> checks</div>'
            '<div class="eyebrow">Category</div>'
            f'<h1>{esc(category)}</h1><p class="lead"><b class="hilite-core">{len(items)}</b> checks, listed alphabetically. Open a check for purpose, severity, fix availability, settings and selection behavior.</p>'
            '<div class="grid">' + "".join(cards) + '</div>'
        )
        write_html_file(
            qc_output / "categories" / f"{category_slug(category)}.html",
            page_shell(
                title=f"{category} Checks",
                description=f"{category} QC checks",
                body=category_body,
                records=records,
                depth=1,
                active_category=category,
                version=version,
            ),
        )

        check_dir = qc_output / "checks" / category_slug(category)
        check_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            why = item.get("why") or "This check protects scene quality and helps catch production issues before publishing or rendering."
            notes = item.get("notes") or []
            notes_html = ""
            if notes:
                notes_html = '<h2>Notes</h2><ul>' + "".join(f'<li>{esc(note)}</li>' for note in notes) + '</ul>'
            fix_details = item.get("fixDescription") or (
                "An automatic fix is available." if item.get("hasFix") else "This check requires manual review or correction."
            )
            check_body = (
                '<div class="breadcrumbs"><a href="../../index.html">Documentation</a><span>›</span>'
                f'<a href="../../categories/{category_slug(category)}.html">{esc(category)}</a><span>›</span>{esc(item["label"])}</div>'
                f'<div class="eyebrow">{esc(category)} check</div><h1>{esc(item["label"])}</h1>'
                f'<p class="lead">{esc(item.get("description"))}</p>'
                '<div class="meta-row">'
                f'<span class="pill"><span class="dot {esc(item.get("severity", "warning"))}"></span>{esc(severity_label(item.get("severity", "warning")))}</span>'
                f'<span class="pill">Automatic fix: {yes_no(item.get("hasFix"))}</span>'
                f'<span class="pill">Settings: {yes_no(item.get("hasSettings"))}</span>'
                f'<span class="pill">Selection: {esc(item.get("selection", "Object"))}</span></div>'
                '<section class="detail-card"><h2 style="margin-top:0">Why this check exists</h2>'
                f'<p>{esc(why)}</p></section>'
                '<h2>Behavior</h2><table class="feature-table"><tbody>'
                f'<tr><th>Module</th><td><code>{esc(item.get("source"))}</code></td></tr>'
                f'<tr><th>Severity</th><td>{esc(severity_label(item.get("severity", "warning")))}</td></tr>'
                f'<tr><th>Automatic fix</th><td>{yes_no(item.get("hasFix"))}</td></tr>'
                f'<tr><th>Fix behavior</th><td>{esc(fix_details)}</td></tr>'
                f'<tr><th>User settings</th><td>{yes_no(item.get("hasSettings"))}</td></tr>'
                f'<tr><th>Selection support</th><td>{esc(item.get("selection", "Object"))}</td></tr>'
                '</tbody></table><h2>Settings</h2>'
                + settings_table(item.get("settings") or [])
                + notes_html
            )
            write_html_file(
                check_dir / f'{item["id"]}.html',
                page_shell(
                    title=item["label"],
                    description=item.get("description") or item["label"],
                    body=check_body,
                    records=records,
                    depth=2,
                    active_category=category,
                    version=version,
                ),
            )

    # Search page is generic and powered by checks-data.js.
    search_body = (
        '<div class="eyebrow">Documentation Search</div><h1>Search QC checks</h1>'
        '<p class="lead">Search by check name, category, description, severity, setting or source module.</p>'
        '<div class="search-page"><input data-search-page-input type="search" placeholder="Search checks…" autofocus>'
        '<div data-search-results class="search-results"></div></div>'
    )
    write_html_file(
        qc_output / "search.html",
        page_shell(
            title="Search",
            description="Search Scriptronaut QC checks",
            body=search_body,
            records=records,
            version=version,
        ),
    )

    # Lightweight all-checks page.
    all_cards = "".join(
        f'<a class="card" href="checks/{category_slug(item["category"])}/{esc(item["id"])}.html"><h3>{esc(item["label"])}</h3><p>{esc(item["category"])}</p></a>'
        for item in sorted(records, key=lambda record: (record["category"].lower(), record["label"].lower()))
    )
    checks_body = '<div class="eyebrow">Core Checks</div><h1>All checks</h1><div class="grid">' + all_cards + '</div>'
    write_html_file(
        qc_output / "checks.html",
        page_shell(
            title="All Checks",
            description="All Scriptronaut QC checks",
            body=checks_body,
            records=records,
            version=version,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the themed QC documentation site.")
    parser.add_argument("data_path")
    parser.add_argument("template_site")
    parser.add_argument("output_dir")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()
    generate_site(args.data_path, args.template_site, args.output_dir, version=args.version)
    print(f"Generated documentation website: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
