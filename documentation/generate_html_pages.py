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



def get_hilite_class(
        tier: str,
        product_id: str,
) -> str:
    """
    Return the CSS highlight class for a documentation product.

    Core / Pro:
        hilite-core
        hilite-pro

    Packs:
        hilite-pack-rigging
        hilite-pack-animation
        hilite-pack-lighting
    """
    tier = str(tier).strip().lower()

    product_id = re.sub(
        r"[^a-z0-9_-]+",
        "-",
        str(product_id).strip().lower(),
    ).strip("-")

    if tier == "pack":
        return "hilite-pack-{}".format(
            product_id
        )

    return "hilite-{}".format(
        tier
    )


def get_product_page_href(
        tier: str,
        product_id: str,
) -> str:
    """Return the site-root-relative marketing/product page for a doc product."""
    if str(tier).strip().lower() == "pack":
        return "products/qc_checker/packs/{}/index.html".format(
            product_id
        )

    return "products/qc_checker/{}/index.html".format(
        product_id
    )

def navigation(
        records: list[dict[str, Any]],
        depth: int,
        tier: str,
        product_id: str,
        product_name: str,
        active_category: str = "",
        has_panel: bool = False,
        features: list[dict[str, Any]] | None = None,
        active_feature: str = "",
        product_depth: int = 1,
) -> str:
    hilite_class = get_hilite_class(
        tier,
        product_id,
    )

    prefix = relative_prefix(depth)
    counts = Counter(
        record["category"]
        for record in records
    )

    features = features or []

    product_label = (
        product_name
        if tier == "pack"
        else tier.title()
    )

    category_links = []

    for category in sorted(
        counts,
        key=str.lower,
    ):
        active = (
            " active"
            if category == active_category
            else ""
        )

        category_links.append(
            f'<a class="nav-link{active}" '
            f'href="{prefix}categories/{category_slug(category)}.html">'
            f'{esc(category)}<span>{counts[category]}</span></a>'
        )

    panel_link = (
        f'<a class="nav-link" href="{prefix}panel.html">Panel guide</a>'
        if has_panel
        else ""
    )

    feature_section = ""

    if features:
        feature_links = []

        for feature in features:
            feature_id = str(
                feature.get(
                    "id",
                    "",
                )
            )

            active = (
                " active"
                if feature_id == active_feature
                else ""
            )

            feature_links.append(
                f'<a class="nav-link{active}" '
                f'href="{prefix}features/{esc(feature_id)}.html">'
                f'{esc(feature.get("label", feature_id))}</a>'
            )

        feature_section = (
            '<div class="nav-section">'
            f'<div class="nav-title"><b class="{hilite_class}">'
            f'{esc(tier.title())}</b> Features</div>'
            + "".join(
                feature_links
            )
            + '</div>'
        )

    return (
        '<aside class="sidebar">'
        '<div class="search-wrap">'
        '<input data-site-search type="search" placeholder="Search documentation">'
        '</div>'
        '<nav>'
        '<div class="nav-section">'
        '<div class="nav-title">Start</div>'
        f'<a class="nav-link" href="{relative_prefix(2 + product_depth + depth)}products/qc_checker/index.html">All Products</a>'
        f'<a class="nav-link" href="{relative_prefix(2 + product_depth + depth)}{get_product_page_href(tier, product_id)}">Product Page</a>'
        f'<a class="nav-link" href="{prefix}index.html">Overview</a>'
        f'{panel_link}'
        f'<a class="nav-link" href="{prefix}search.html">Search</a>'
        '</div>'
        + feature_section
        + '<div class="nav-section">'
        f'<div class="nav-title"><b class="{hilite_class}">'
        f'{esc(product_label)}</b> Checks</div>'
        + "".join(
            category_links
        )
        + '</div>'
        '</nav>'
        '</aside>'
    )


def page_shell(
    *,
    title: str,
    description: str,
    body: str,
    records: list[dict[str, Any]],
    depth: int = 0,
    active_category: str = "",
    tier: str,
    product_id: str,
    product_name: str,
    has_panel: bool = False,
    features: list[dict[str, Any]] | None = None,
    active_feature: str = "",
    product_depth: int = 1,
    version: str = "1.0",
) -> str:

    hilite_class = get_hilite_class(
        tier,
        product_id,
    )

    """Build one product documentation page under docs/qc_checker/<product>."""
    product_prefix = relative_prefix(
        depth
    )

    qc_prefix = relative_prefix(
        product_depth
        + depth
    )

    site_prefix = relative_prefix(
        2
        + product_depth
        + depth
    )
    current_year = datetime.now().year

    product_label = (
        product_name
        if tier == "pack"
        else tier.title()
    )

    data_script = f"{qc_prefix}assets/js/{product_id}-checks-data.js"
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="description" content="{esc(description)}">'
        f'<title>{esc(title)} — Scriptronaut QC Docs</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">'
        f'<link rel="stylesheet" href="{site_prefix}css/docs.css"></head><body>'
        '<div class="stars"></div><div class="stars stars-medium"></div><div class="stars stars-faint"></div>'
        '<header class="topbar">'
        f'<a class="brand" href="{site_prefix}index.html"><img src="{site_prefix}svg/scriptronaut_name.svg" alt="Scriptronaut"></a>'
        '<div class="top-actions"><span class="hide-mobile"><b>QC Checker</b> Documentation</span>'
        f'<span class="badge {hilite_class}"><b>{esc(product_label)}</b> {esc(version)}</span></div></header>'
        '<div class="shell">'
        + navigation(
            records,
            depth,
            tier,
            product_id,
            product_name,
            active_category,
            has_panel=has_panel,
            features=features,
            active_feature=active_feature,
            product_depth=product_depth,
        )
        + f'<main class="content">{body}<footer class="footer"><b>Scriptronaut</b> | QC Checker <b class="{hilite_class}">{esc(product_label)}</b> documentation.'
        f'<span style="float:right;">&copy; {current_year}</span></footer></main></div>'
        f'<script src="{data_script}"></script>'
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
        setting_row = (
            '<tr>'
            f'<th>{esc(setting.get("label"))}</th>'
            f'<td><code>{esc(setting.get("id"))}</code></td>'
            f'<td>{esc(setting.get("type"))}</td>'
            f'<td>{esc(setting.get("default"))}</td>'
            f'<td>{esc(setting.get("description"))}<div class="small">{" · ".join(limits)}</div></td>'
            '</tr>'
        )

        enum_items = (
            setting.get("items")
            if setting.get("type") == "enum"
            else []
        )
        enum_options = ""
        if isinstance(enum_items, list) and enum_items:
            option_rows = []
            for option in enum_items:
                if not isinstance(option, dict):
                    continue
                option_rows.append(
                    '<tr>'
                    f'<td>{esc(option.get("label"))}</td>'
                    f'<td><code>{esc(option.get("id"))}</code></td>'
                    f'<td>{esc(option.get("description"))}</td>'
                    '</tr>'
                )

            if option_rows:
                enum_options = (
                    '<tr class="enum-options-row"><td colspan="5">'
                    '<div class="enum-options"><div class="enum-options-title">Options</div>'
                    '<div class="table-scroll"><table class="enum-options-table">'
                    '<thead><tr><th>Option</th><th>Value</th><th>Description</th></tr></thead>'
                    '<tbody>' + "".join(option_rows) + '</tbody></table></div></div>'
                    '</td></tr>'
                )

        rows.append(setting_row + enum_options)
    return (
        '<div class="table-scroll"><table class="feature-table"><thead><tr>'
        '<th>Setting</th><th>ID</th><th>Type</th><th>Default</th><th>Description</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def generate_product_site(
    data_path: str | Path,
    output_dir: str | Path,
    product_id: str,
    product_name: str,
    tier: str,
    product_path: str | Path,
    features: list[dict[str, Any]] | None = None,
    notes: list[dict[str, Any]] | None = None,
    version: str = "1.0",
) -> None:
    """Generate one Core, Pro, or Pack documentation subtree."""
    data_path = Path(data_path).resolve()
    output_dir = Path(output_dir).resolve()
    product_path = Path(
        product_path
    )
    product_label = product_id if product_id in["core", "pro"] else product_name

    # Number of directory levels between docs/qc_checker and this product.
    #
    # Core / Pro:
    #     core                 -> 1
    #     pro                  -> 1
    #
    # Packs:
    #     packs/rigging        -> 2
    product_depth = len(
        product_path.parts
    )

    product_site_prefix = relative_prefix(
        2
        + product_depth
    )

    product_hilite_class = get_hilite_class(
        tier,
        product_id,
    )

    records = json.loads(
        data_path.read_text(
            encoding="utf-8"
        )
    )

    features = features or []
    notes = notes or []

    qc_root = output_dir / "docs" / "qc_checker"
    product_output = qc_root / product_path
    product_output.mkdir(parents=True, exist_ok=True)
    has_panel = (product_output / "panel.html").is_file()

    # Shared QC assets; product datasets remain separate.
    data_out = qc_root / "assets" / "data" / product_path / "checks.json"
    data_out.parent.mkdir(parents=True, exist_ok=True)
    data_out.write_text(json.dumps(records, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    js_out = qc_root / "assets" / "js" / f"{product_id}-checks-data.js"
    js_out.parent.mkdir(parents=True, exist_ok=True)
    js_out.write_text(
        "/* Auto-generated. Do not edit manually. */\n\n"
        f"window.QC_CHECKS = {json.dumps(records, indent=4, ensure_ascii=False)};\n",
        encoding="utf-8",
    )

    categories = sorted({record["category"] for record in records}, key=str.lower)
    counts = Counter(record["category"] for record in records)

    def tier_badge(item: dict[str, Any]) -> str:
        source_tier = str(item.get("sourceTier") or tier).lower()
        if tier == "pro" and source_tier == "pro":
            return '<span class="pill hilite-pro">Pro</span>'
        if tier == "pack":
            return '<span class="pill">Pack</span>'
        return ""

    category_cards = "".join(
        f'<a class="card" href="categories/{category_slug(category)}.html"><h3>{esc(category)}</h3>'
        f'<p>Browse the {esc(category.lower())} checks included with {esc(product_name)}.</p>'
        f'<span class="count">{counts[category]} checks →</span></a>'
        for category in categories
    )
    panel_action = '<a class="button primary" href="panel.html">Open panel guide →</a>' if has_panel else ''
    first_category = category_slug(categories[0]) if categories else ""
    browse_action = f'<a class="button" href="categories/{first_category}.html">Browse checks</a>' if first_category else ''
    notes_html = ""
    if notes:
        note_cards = []
        for note in notes:
            if isinstance(note, str):
                note_title = ""
                note_description = note
            elif isinstance(note, dict):
                note_title = str(note.get("title") or "")
                note_description = str(note.get("description") or "")
            else:
                continue

            if not note_title and not note_description:
                continue

            note_cards.append(
                '<article class="general-note">'
                + (f'<h3>{esc(note_title)}</h3>' if note_title else "")
                + f'<p>{esc(note_description)}</p>'
                + '</article>'
            )

        if note_cards:
            notes_html = (
                '<section class="general-notes">'
                '<h2>General Notes</h2>'
                '<div class="general-notes-list">'
                + "".join(note_cards)
                + '</div></section>'
            )

    index_body = (
        f'<div class="eyebrow">Official Documentation</div><h1 class="{product_hilite_class}">{esc(product_label).title()}</h1>'
        f'<p class="lead">Production-focused documentation for the <b class="{product_hilite_class}">{len(records)}</b> checks included with {esc(product_name)}.</p>'
        '<section class="hero-card"><div><h2 style="margin-top:0">Documentation</h2>'
        '<p class="lead" style="font-size:1rem">Browse checks by category, search the documentation, and review check behavior, settings, severity and fix support.</p>'
        f'<div class="actions">{panel_action}{browse_action}</div></div>'
        '<div class="astronaut-wrap" id="astronaut">'
        f'<img src="{product_site_prefix}svg/scriptronaut_character.svg" '
        'alt="Scriptronaut character"></div></section>'
        + notes_html
        + (
            f'<h2><b class="{product_hilite_class}">{esc(product_label).title()}</b> Features</h2>'
            '<div class="grid">'
            + "".join(
                f'<a class="card" href="features/{esc(feature.get("id"))}.html">'
                f'<h3>{esc(feature.get("label"))}</h3>'
                f'<p>{esc(feature.get("description"))}</p>'
                f'<span class="count hilite-{tier}">Learn more →</span></a>'
                for feature in features
            )
            + '</div>'
            if features
            else ""
        )
        + f'<h2><b class="{product_hilite_class}">{esc(product_label).title()}</b> Categories</h2>'
        f'<div class="grid">{category_cards}</div>'
    )
    write_html_file(
        product_output / "index.html",
        page_shell(title=product_name, description=f"Scriptronaut {product_name} documentation", body=index_body,
                   records=records, tier=tier, product_id=product_id, product_name=product_name, has_panel=has_panel, features=features, product_depth=product_depth, version=version),
    )

    (product_output / "categories").mkdir(parents=True, exist_ok=True)
    (product_output / "checks").mkdir(parents=True, exist_ok=True)
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
                f'{tier_badge(item)}</div></a>'
            )
        category_body = (
            f'<div class="breadcrumbs"><a href="../index.html">{esc(product_name)}</a><span>›</span>{esc(category)}</div>'
            '<div class="eyebrow">Category</div>'
            f'<h1>{esc(category)}</h1><p class="lead"><b class="{product_hilite_class}">{len(items)}</b> checks, listed alphabetically.</p>'
            '<div class="grid">' + "".join(cards) + '</div>'
        )
        write_html_file(
            product_output / "categories" / f"{category_slug(category)}.html",
            page_shell(title=f"{category} Checks", description=f"{category} QC checks", body=category_body,
                       records=records, depth=1, active_category=category, tier=tier, product_id=product_id, product_name=product_name,
                       has_panel=has_panel, features=features, product_depth=product_depth, version=version),
        )

        check_dir = product_output / "checks" / category_slug(category)
        check_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            why = item.get("why") or "This check protects scene quality and helps catch production issues before publishing or rendering."
            notes = item.get("notes") or []
            notes_html = '<h2>Notes</h2><ul>' + "".join(f'<li>{esc(note)}</li>' for note in notes) + '</ul>' if notes else ""
            fix_details = item.get("fixDescription") or ("An automatic fix is available." if item.get("hasFix") else "This check requires manual review or correction.")
            check_body = (
                '<div class="breadcrumbs"><a href="../../index.html">' + esc(product_name) + '</a><span>›</span>'
                f'<a href="../../categories/{category_slug(category)}.html">{esc(category)}</a><span>›</span>{esc(item["label"])}</div>'
                f'<div class="eyebrow">{esc(category)} check</div><h1>{esc(item["label"])}</h1>'
                f'<p class="lead">{esc(item.get("description"))}</p><div class="meta-row">'
                f'<span class="pill"><span class="dot {esc(item.get("severity", "warning"))}"></span>{esc(severity_label(item.get("severity", "warning")))}</span>'
                f'<span class="pill">Automatic fix: {yes_no(item.get("hasFix"))}</span>'
                f'<span class="pill">Settings: {yes_no(item.get("hasSettings"))}</span>'
                f'<span class="pill">Selection: {esc(item.get("selection", "Object"))}</span>{tier_badge(item)}</div>'
                '<section class="detail-card"><h2 style="margin-top:0">Why this check exists</h2>'
                f'<p>{esc(why)}</p></section><h2>Behavior</h2><table class="feature-table"><tbody>'
                f'<tr><th>Module</th><td><code>{esc(item.get("source"))}</code></td></tr>'
                f'<tr><th>Included with</th><td>{esc(str(item.get("sourceTier", tier)).title())}</td></tr>'
                f'<tr><th>Severity</th><td>{esc(severity_label(item.get("severity", "warning")))}</td></tr>'
                f'<tr><th>Automatic fix</th><td>{yes_no(item.get("hasFix"))}</td></tr>'
                f'<tr><th>Fix behavior</th><td>{esc(fix_details)}</td></tr>'
                f'<tr><th>User settings</th><td>{yes_no(item.get("hasSettings"))}</td></tr>'
                f'<tr><th>Selection support</th><td>{esc(item.get("selection", "Object"))}</td></tr>'
                '</tbody></table><h2>Settings</h2>' + settings_table(item.get("settings") or []) + notes_html
            )
            write_html_file(
                check_dir / f'{item["id"]}.html',
                page_shell(title=item["label"], description=item.get("description") or item["label"], body=check_body,
                           records=records, depth=2, active_category=category, tier=tier, product_id=product_id, product_name=product_name,
                           has_panel=has_panel, features=features, product_depth=product_depth, version=version),
            )

    # ---------------------------------------------------------
    # Product Features
    # ---------------------------------------------------------

    if features:
        feature_dir = (
            product_output
            / "features"
        )

        feature_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for feature in features:
            feature_id = str(
                feature.get(
                    "id",
                    "",
                )
            )

            feature_label = str(
                feature.get(
                    "label",
                    feature_id,
                )
            )

            highlights = feature.get(
                "highlights",
                [],
            ) or []

            workflow = feature.get(
                "workflow",
                [],
            ) or []

            notes = feature.get(
                "notes",
                [],
            ) or []

            highlights_html = (
                '<h2>Capabilities</h2><ul>'
                + "".join(
                    f'<li>{esc(item)}</li>'
                    for item in highlights
                )
                + '</ul>'
                if highlights
                else ""
            )

            workflow_html = (
                '<h2>Workflow</h2><ol>'
                + "".join(
                    f'<li>{esc(item)}</li>'
                    for item in workflow
                )
                + '</ol>'
                if workflow
                else ""
            )

            storage_html = (
                '<section class="detail-card">'
                '<h2 style="margin-top:0">Storage and behavior</h2>'
                f'<p>{esc(feature.get("storage"))}</p>'
                '</section>'
                if feature.get(
                    "storage"
                )
                else ""
            )

            notes_html = (
                '<h2>Notes</h2><ul>'
                + "".join(
                    f'<li>{esc(item)}</li>'
                    for item in notes
                )
                + '</ul>'
                if notes
                else ""
            )

            feature_body = (
                '<div class="breadcrumbs">'
                f'<a href="../index.html">{esc(product_name)}</a>'
                '<span>›</span>'
                'Features'
                '<span>›</span>'
                f'{esc(feature_label)}'
                '</div>'
                f'<div class="eyebrow">{esc(tier.title())} Feature</div>'
                f'<h1 class="{product_hilite_class}">{esc(feature_label)}</h1>'
                f'<p class="lead">{esc(feature.get("description"))}</p>'
                '<section class="detail-card">'
                '<h2 style="margin-top:0">Overview</h2>'
                f'<p>{esc(feature.get("summary"))}</p>'
                '</section>'
                + highlights_html
                + workflow_html
                + storage_html
                + notes_html
            )

            write_html_file(
                feature_dir
                / f"{feature_id}.html",
                page_shell(
                    title=feature_label,
                    description=(
                        feature.get(
                            "description"
                        )
                        or feature_label
                    ),
                    body=feature_body,
                    records=records,
                    depth=1,
                    tier=tier,
                    product_id=product_id,
                    product_name=product_name,
                    has_panel=has_panel,
                    features=features,
                    active_feature=feature_id,
                    product_depth=product_depth,
                    version=version,
                ),
            )

    search_body = (
        '<div class="eyebrow">Documentation Search</div><h1>Search QC checks</h1>'
        '<p class="lead">Search by check name, category, description, severity, setting or source module.</p>'
        '<div class="search-page"><input data-search-page-input type="search" placeholder="Search checks…" autofocus>'
        '<div data-search-results class="search-results"></div></div>'
    )
    write_html_file(
        product_output / "search.html",
        page_shell(title="Search", description=f"Search {product_name} checks", body=search_body, records=records,
                   tier=tier, product_id=product_id, product_name=product_name, has_panel=has_panel, features=features, product_depth=product_depth, version=version),
    )

    all_cards = "".join(
        f'<a class="card" href="checks/{category_slug(item["category"])}/{esc(item["id"])}.html"><h3>{esc(item["label"])}</h3>'
        f'<p>{esc(item["category"])}</p><div class="meta-row">{tier_badge(item)}</div></a>'
        for item in sorted(records, key=lambda record: (record["category"].lower(), record["label"].lower()))
    )
    checks_body = f'<div class="eyebrow">{esc(product_name)} Checks</div><h1>All checks</h1><div class="grid">{all_cards}</div>'
    write_html_file(
        product_output / "checks.html",
        page_shell(title="All Checks", description=f"All {product_name} checks", body=checks_body, records=records,
                   tier=tier, product_id=product_id, product_name=product_name, has_panel=has_panel, features=features, product_depth=product_depth, version=version),
    )



def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one QC documentation product subtree.")
    parser.add_argument("data_path")
    parser.add_argument("output_dir")
    parser.add_argument("product_id")
    parser.add_argument("product_name")
    parser.add_argument("tier")
    parser.add_argument("product_path")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()
    generate_product_site(
        args.data_path, args.output_dir, args.product_id, args.product_name,
        args.tier, args.product_path, features=[], notes=[], version=args.version,
    )
    print(f"Generated documentation product: {args.product_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
