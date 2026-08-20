"""One-command documentation build for Scriptronaut QC Checker."""
from __future__ import annotations

import argparse
from pathlib import Path

from extract_check_metadata import generate_metadata
from generate_html_pages import generate_site

ROOT = Path(__file__).parent
CHECKS = ROOT.parent / "qc_checker" / "checks"
TEMPLATE = ROOT / "template"
OUTPUT = ROOT / "site"
VERSION = "1.0"

def build_docs(
    checks_dir: str | Path,
    template_site: str | Path,
    output_dir: str | Path,
    version: str = "1.0",
) -> None:
    """
    """
    output_dir = Path(output_dir).resolve()
    build_data_dir = output_dir.parent / ".site_build"
    data_json = build_data_dir / "checks.json"
    data_js = build_data_dir / "checks-data.js"

    records = generate_metadata(
        checks_dir=checks_dir,
        output_json=data_json,
        output_js=data_js,
    )

    generate_site(
        data_path=data_json,
        template_site=template_site,
        output_dir=output_dir,
        version=version,
    )

    print(f"Built {len(records)} check pages in: {output_dir}")


def main() -> int:
    """
    """
    build_docs(
        checks_dir=CHECKS,
        template_site=TEMPLATE,
        output_dir=OUTPUT,
        version=VERSION,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
