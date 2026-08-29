"""Generate Scriptronaut QC Checker product/marketing pages."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

from product_pages import get_product_page_content
from generate_html_pages import format_html


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def hilite_class(tier: str, product_id: str) -> str:
    if tier == "pack":
        return "hilite-pack-{}".format(product_id)
    return "hilite-{}".format(tier)


def product_output_path(product_id: str, tier: str) -> Path:
    if tier == "pack":
        return Path("products") / "qc_checker" / "packs" / product_id
    return Path("products") / "qc_checker" / product_id


def documentation_href(product_id: str, tier: str) -> str:
    if tier == "pack":
        return "docs/qc_checker/packs/{}/index.html".format(product_id)
    return "docs/qc_checker/{}/index.html".format(product_id)


def _benefits_html(benefits: list[dict[str, Any]], css_class: str) -> str:
    if not benefits:
        return ""

    cards = []
    for item in benefits:
        cards.append(
            '<article class="detail-card product-benefit">'
            '<h3>{}</h3><p>{}</p></article>'.format(
                esc(item.get("feature")),
                esc(item.get("benefit")),
            )
        )

    return (
        '<section class="product-section">'
        '<h2 class="{}">Features → benefits</h2>'
        '<div class="grid">{}</div>'
        '</section>'
    ).format(css_class, "".join(cards))


def generate_product_page(
        output_dir: str | Path,
        product_id: str,
        product_name: str,
        tier: str,
        check_count: int = 0,
        feature_count: int = 0,
        version: str = "1.0",
) -> Path:
    output_dir = Path(output_dir).resolve()
    tier = str(tier).lower()
    content = get_product_page_content(product_id, product_name, tier)
    css_class = hilite_class(tier, product_id)

    output_path = output_dir / product_output_path(product_id, tier) / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    depth_to_site = len(output_path.parent.relative_to(output_dir).parts)
    site_prefix = "../" * depth_to_site

    docs_href = site_prefix + documentation_href(product_id, tier)
    family_href = site_prefix + "products/qc_checker/index.html"
    home_href = site_prefix + "index.html"

    buy_url = str(content.get("buy_url") or "").strip()
    buy_button = (
        '<a class="button primary" href="{}">Buy Now</a>'.format(esc(buy_url))
        if buy_url
        else '<span class="button product-button-disabled">Buy Now</span>'
    )

    counts = []
    if check_count:
        counts.append("{} check{}".format(check_count, "" if check_count == 1 else "s"))
    if feature_count:
        counts.append("{} Pro feature{}".format(feature_count, "" if feature_count == 1 else "s"))

    count_line = (
        '<p class="small product-count">{}</p>'.format(esc(" · ".join(counts)))
        if counts
        else ""
    )

    year = datetime.now().year

    parts = [
        '<!doctype html><html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="description" content="{}">'.format(esc(content.get("primary_outcome"))),
        '<title>{} — Scriptronaut</title>'.format(esc(product_name)),
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">',
        '<link rel="stylesheet" href="{}css/docs.css">'.format(site_prefix),
        '</head><body>',
        '<div class="stars"></div><div class="stars stars-medium"></div><div class="stars stars-faint"></div>',
        '<header class="topbar">',
        '<a class="brand" href="{}"><img src="{}svg/scriptronaut_name.svg" alt="Scriptronaut"></a>'.format(home_href, site_prefix),
        '<div class="top-actions"><a href="{}">QC Checker</a>'.format(family_href),
        '<span class="badge {}"><b>{}</b> {}</span></div>'.format(css_class, esc(product_name), esc(version)),
        '</header>',
        '<main class="product-page">',
        '<section class="product-hero">',
        '<div class="eyebrow">{}</div>'.format(esc(content.get("eyebrow"))),
        '<h1 class="{}">{}</h1>'.format(css_class, esc(product_name)),
        '<p class="lead"><b>Primary outcome:</b> {}</p>'.format(esc(content.get("primary_outcome"))),
        count_line,
        '<div class="product-visual"><span>{}</span></div>'.format(esc(content.get("hero_label"))),
        '<div class="product-cta">',
        '<div><div class="small">Primary Call To Action</div>',
        '<p>Choose the product when it fits your workflow, or review the technical documentation first.</p></div>',
        '<div class="actions">{}<a class="button" href="{}">Documentation</a></div>'.format(buy_button, docs_href),
        '</div></section>',
        '<section class="product-section"><h2 class="{}">The problem</h2><p>{}</p></section>'.format(css_class, esc(content.get("problem"))),
        '<section class="product-section"><h2 class="{}">Before / after workflow</h2><p>{}</p></section>'.format(css_class, esc(content.get("before_after"))),
        _benefits_html(content.get("benefits") or [], css_class),
        '<section class="product-section"><h2 class="{}">Who it is for</h2><p>{}</p></section>'.format(css_class, esc(content.get("who_for"))),
        '<section class="product-section"><h2 class="{}">Requirements / compatibility</h2><p>{}</p></section>'.format(css_class, esc(content.get("requirements"))),
        '<section class="product-final-cta"><h2 class="{}">Ready to inspect the details?</h2>'.format(css_class),
        '<div class="actions">{}<a class="button" href="{}">Open Documentation</a></div></section>'.format(buy_button, docs_href),
        '<footer class="footer"><b>Scriptronaut</b> | <b class="{}">{}</b><span style="float:right;">&copy; {}</span></footer>'.format(css_class, esc(product_name), year),
        '</main></body></html>',
    ]

    output_path.write_text(
        format_html(
            "".join(
                parts
            )
        ),
        encoding="utf-8",
    )
    return output_path


def generate_qc_checker_product_index(
        output_dir: str | Path,
        products: list[dict[str, Any]],
        version: str = "1.0",
) -> Path:
    output_dir = Path(output_dir).resolve()
    output_path = output_dir / "products" / "qc_checker" / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    site_prefix = "../../"
    cards = []

    for product in products:
        product_id = str(product["id"])
        tier = str(product["tier"])
        name = str(product["name"])
        css_class = hilite_class(tier, product_id)

        href = (
            "packs/{}/index.html".format(
                product_id
            )
            if tier == "pack"
            else "{}/index.html".format(
                product_id
            )
        )

        check_count = int(product.get("check_count", 0))
        cards.append(
            (
                '            <a class="card" href="{}">\n'
                '                <div class="eyebrow">{}</div>\n'
                '                <h3 class="{}">{}</h3>\n'
                '                <p>{} check{}</p>\n'
                '                <span class="count">View product →</span>\n'
                '            </a>'
            ).format(
                href,
                esc("Pack" if tier == "pack" else tier.title()),
                css_class,
                esc(name),
                check_count,
                "" if check_count == 1 else "s",
            )
        )

    parts = [
        '<!doctype html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="utf-8">',
        '    <meta name="viewport" content="width=device-width,initial-scale=1">',
        '    <meta name="description" content="QC Checker products">',
        '    <title>QC Checker — Scriptronaut</title>',
        '    <link rel="stylesheet" href="{}css/docs.css">'.format(site_prefix),
        '</head>',
        '<body>',
        '    <div class="stars"></div>',
        '    <div class="stars stars-medium"></div>',
        '    <div class="stars stars-faint"></div>',
        '    <header class="topbar">',
        '        <a class="brand" href="{}index.html">'.format(site_prefix),
        '            <img src="{}svg/scriptronaut_name.svg" alt="Scriptronaut">'.format(site_prefix),
        '        </a>',
        '        <div class="top-actions">',
        '            <span class="badge">QC Checker {}</span>'.format(esc(version)),
        '        </div>',
        '    </header>',
        '    <main class="product-page">',
        '        <div class="eyebrow">Product Family</div>',
        '        <h1>QC Checker</h1>',
        '        <p class="lead">Choose the QC Checker product or specialist Pack that fits your Blender workflow.</p>',
        '        <div class="grid">',
        "\n".join(cards),
        '        </div>',
        '    </main>',
        '</body>',
        '</html>',
    ]

    output_path.write_text(
        format_html(
            "".join(
                parts
            )
        ),
        encoding="utf-8",
    )
    return output_path
