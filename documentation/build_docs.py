"""Build Scriptronaut QC Checker documentation products."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from extract_check_metadata import generate_metadata
from generate_html_pages import generate_product_site
from product_features import get_product_features

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
TEMPLATE = ROOT / "template"
OUTPUT = ROOT / "site"
BUILD_DATA = ROOT / ".site_build"
VERSION = "1.0"

SHARED_CHECKS = PROJECT_ROOT / "shared" / "checks"
PRO_CHECKS = PROJECT_ROOT / "pro" / "checks"

PRODUCTS = {
    "core": {
        "name": "QC Checker Core",
        "tier": "core",
        "output_path": Path("core"),
        "sources": [
            {"checks_dir": SHARED_CHECKS, "tier": "core", "product": "core"},
        ],
    },
    "pro": {
        "name": "QC Checker Pro",
        "tier": "pro",
        "output_path": Path("pro"),
        "sources": [
            {"checks_dir": SHARED_CHECKS, "tier": "core", "product": "core"},
            {"checks_dir": PRO_CHECKS, "tier": "pro", "product": "pro", "optional": True},
        ],
    },
}


def prepare_site(template_site: Path, output_dir: Path) -> None:
    """Copy manual/static site content once before generating product pages."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(template_site, output_dir)


def existing_sources(product: dict) -> list[dict]:
    sources = []
    for source in product["sources"]:
        path = Path(source["checks_dir"])
        if path.is_dir():
            sources.append(source)
            continue
        if source.get("optional"):
            print(f"Optional check source not found, skipping: {path}")
            continue
        raise FileNotFoundError(f"Required check source not found: {path}")
    return sources


def build_product(product_id: str, *, version: str = VERSION) -> int:
    product = PRODUCTS[product_id]
    sources = existing_sources(product)
    data_dir = BUILD_DATA / product_id
    data_json = data_dir / "checks.json"
    records = generate_metadata(sources, data_json)
    generate_product_site(
        data_path=data_json,
        output_dir=OUTPUT,
        product_id=product_id,
        product_name=product["name"],
        tier=product["tier"],
        product_path=product["output_path"],
        features=get_product_features(
            product_id
        ),
        version=version,
    )
    print(f"Built {len(records)} checks for {product['name']}.")
    return len(records)


def build_pack(pack_id: str, checks_dir: str | Path, *, name: str | None = None, version: str = VERSION) -> int:
    """Build one future QC pack under docs/qc_checker/packs/<pack_id>."""
    pack_id = pack_id.strip().lower().replace(" ", "_")
    pack_name = name or pack_id.replace("_", " ").title()
    data_dir = BUILD_DATA / "packs" / pack_id
    data_json = data_dir / "checks.json"
    records = generate_metadata(
        [{"checks_dir": Path(checks_dir), "tier": "pack", "product": pack_id}],
        data_json,
    )
    generate_product_site(
        data_path=data_json,
        output_dir=OUTPUT,
        product_id=pack_id,
        product_name=pack_name,
        tier="pack",
        product_path=Path("packs") / pack_id,
        features=[],
        version=version,
    )
    print(f"Built {len(records)} checks for {pack_name}.")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Scriptronaut QC documentation.")
    parser.add_argument("--product", choices=("core", "pro", "all"), default="all")
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--pack-id")
    parser.add_argument("--pack-name")
    parser.add_argument("--pack-checks")
    args = parser.parse_args()

    prepare_site(TEMPLATE, OUTPUT)

    if args.pack_id:
        if not args.pack_checks:
            parser.error("--pack-checks is required with --pack-id")
        build_pack(args.pack_id, args.pack_checks, name=args.pack_name, version=args.version)
        return 0

    products = ("core", "pro") if args.product == "all" else (args.product,)
    for product_id in products:
        build_product(product_id, version=args.version)
    print(f"Documentation site: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
