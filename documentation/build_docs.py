"""Build Scriptronaut QC Checker documentation products."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from extract_check_metadata import generate_metadata
from generate_html_pages import (
    generate_product_site,
)
from product_features import get_product_features
from generate_product_pages import (
    generate_product_page,
    generate_qc_checker_product_index,
)


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

TEMPLATE = ROOT / "template"
OUTPUT = ROOT / "site"
BUILD_DATA = ROOT / ".site_build"

VERSION = "1.0"

SHARED_CHECKS = PROJECT_ROOT / "shared" / "checks"
PRO_CHECKS = PROJECT_ROOT / "pro" / "checks"
PACKS_ROOT = PROJECT_ROOT / "packs"


PRODUCTS = {
    "core": {
        "name": "QC Checker Core",
        "tier": "core",
        "output_path": Path("core"),
        "sources": [
            {
                "checks_dir": SHARED_CHECKS,
                "tier": "core",
                "product": "core",
            },
        ],
    },

    "pro": {
        "name": "QC Checker Pro",
        "tier": "pro",
        "output_path": Path("pro"),
        "sources": [
            {
                "checks_dir": SHARED_CHECKS,
                "tier": "core",
                "product": "core",
            },

            {
                "checks_dir": PRO_CHECKS,
                "tier": "pro",
                "product": "pro",
                "optional": True,
            },
        ],
    },
}


def normalize_identifier(
        value: str,
) -> str:
    """
    Convert a folder/product name into a stable documentation identifier.
    """
    return re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        str(
            value
        ).strip(),
    ).strip(
        "_"
    ).lower()


def display_name_from_identifier(
        value: str,
) -> str:
    """
    Convert identifiers such as rigging_pack into Rigging Pack.
    """
    return " ".join(
        word.capitalize()
        for word in re.split(
            r"[_\-]+",
            str(
                value
            ).strip(),
        )
        if word
    )


def prepare_site(
        template_site: Path,
        output_dir: Path,
) -> None:
    """
    Copy manual/static site content once before generating documentation.
    """
    if output_dir.exists():
        shutil.rmtree(
            output_dir
        )

    shutil.copytree(
        template_site,
        output_dir,
    )


def existing_sources(
        product: dict,
) -> list[dict]:
    """
    Return source roots that currently exist.
    """
    sources = []

    for source in product[
        "sources"
    ]:
        path = Path(
            source[
                "checks_dir"
            ]
        )

        if path.is_dir():
            sources.append(
                source
            )
            continue

        if source.get(
            "optional"
        ):
            print(
                "Optional check source not found, skipping: {}".format(
                    path
                )
            )
            continue

        raise FileNotFoundError(
            "Required check source not found: {}".format(
                path
            )
        )

    return sources


def pack_has_checks(
        checks_dir: Path,
) -> bool:
    """
    Return True when a checks root contains at least one actual check module.
    """
    if not checks_dir.is_dir():
        return False

    for category_dir in checks_dir.iterdir():
        if (
            not category_dir.is_dir()
            or category_dir.name.startswith(
                "."
            )
            or category_dir.name == "__pycache__"
        ):
            continue

        for script_path in category_dir.glob(
            "*.py"
        ):
            if script_path.name != "__init__.py":
                return True

    return False


def discover_packs() -> dict[str, dict]:
    """
    Discover documentation-capable packs directly from PROJECT_ROOT/packs.

    Expected pack shape:

        packs/
            rigging/
                checks/
                    rigging/
                        check_a.py
                        check_b.py

    The folder name becomes the pack ID. A folder called ``rigging`` is
    displayed as ``Rigging Pack``.
    """
    discovered = {}

    if not PACKS_ROOT.is_dir():
        return discovered

    for pack_dir in sorted(
        PACKS_ROOT.iterdir(),
        key=lambda path: path.name.lower(),
    ):
        if (
            not pack_dir.is_dir()
            or pack_dir.name.startswith(
                "."
            )
            or pack_dir.name == "__pycache__"
        ):
            continue

        checks_dir = (
            pack_dir
            / "checks"
        )

        if not pack_has_checks(
            checks_dir
        ):
            continue

        pack_id = normalize_identifier(
            pack_dir.name
        )

        base_name = display_name_from_identifier(
            pack_dir.name
        )

        pack_name = (
            base_name
            if base_name.lower().endswith(
                "pack"
            )
            else "{} Pack".format(
                base_name
            )
        )

        discovered[
            pack_id
        ] = {
            "id":
                pack_id,

            "name":
                pack_name,

            "tier":
                "pack",

            "pack_dir":
                pack_dir,

            "checks_dir":
                checks_dir,

            "output_path":
                Path(
                    "packs"
                )
                / pack_id,
        }

    return discovered


def build_product(
        product_id: str,
        *,
        version: str = VERSION,
) -> dict:
    """
    Build one Core or Pro documentation product.
    """
    product = PRODUCTS[
        product_id
    ]

    sources = existing_sources(
        product
    )

    data_dir = (
        BUILD_DATA
        / product_id
    )

    data_json = (
        data_dir
        / "checks.json"
    )

    records = generate_metadata(
        sources,
        data_json,
    )

    generate_product_site(
        data_path=data_json,
        output_dir=OUTPUT,
        product_id=product_id,
        product_name=product[
            "name"
        ],
        tier=product[
            "tier"
        ],
        product_path=product[
            "output_path"
        ],
        features=get_product_features(
            product_id
        ),
        version=version,
    )

    print(
        "Built {} checks for {}.".format(
            len(
                records
            ),
            product[
                "name"
            ],
        )
    )

    return {
        "id":
            product_id,

        "name":
            product[
                "name"
            ],

        "tier":
            product[
                "tier"
            ],

        "href":
            "{}/index.html".format(
                product[
                    "output_path"
                ].as_posix()
            ),

        "check_count":
            len(
                records
            ),

        "feature_count":
            len(
                get_product_features(
                    product_id
                )
            ),
    }


def build_pack(
        pack: dict,
        *,
        version: str = VERSION,
    ) -> dict:
    """
    Build one discovered pack under docs/qc_checker/packs/<pack_id>.
    """
    pack_id = pack[
        "id"
    ]

    data_dir = (
        BUILD_DATA
        / "packs"
        / pack_id
    )

    data_json = (
        data_dir
        / "checks.json"
    )

    records = generate_metadata(
        [
            {
                "checks_dir":
                    pack[
                        "checks_dir"
                    ],

                "tier":
                    "pack",

                "product":
                    pack_id,
            }
        ],
        data_json,
    )

    generate_product_site(
        data_path=data_json,
        output_dir=OUTPUT,
        product_id=pack_id,
        product_name=pack[
            "name"
        ],
        tier="pack",
        product_path=pack[
            "output_path"
        ],
        features=[],
        version=version,
    )

    print(
        "Built {} checks for {}.".format(
            len(
                records
            ),
            pack[
                "name"
            ],
        )
    )

    return {
        "id":
            pack_id,

        "name":
            pack[
                "name"
            ],

        "tier":
            "pack",

        "href":
            "{}/index.html".format(
                pack[
                    "output_path"
                ].as_posix()
            ),

        "check_count":
            len(
                records
            ),

        "feature_count":
            0,
    }


def build_product_pages(
        products: list[dict],
        *,
        version: str = VERSION,
) -> None:
    """Generate product/marketing pages for built QC products and packs."""
    if not products:
        return

    generate_qc_checker_product_index(
        output_dir=OUTPUT,
        products=products,
        version=version,
    )

    for product in products:
        generate_product_page(
            output_dir=OUTPUT,
            product_id=product["id"],
            product_name=product["name"],
            tier=product["tier"],
            check_count=product.get("check_count", 0),
            feature_count=product.get("feature_count", 0),
            version=version,
        )

        print(
            "Built product page for {}.".format(
                product["name"]
            )
        )


def resolve_pack_selection(
        selection: str,
        discovered_packs: dict[str, dict],
) -> list[dict]:
    """
    Resolve --packs none|all|id1,id2.
    """
    selection = str(
        selection
        or "none"
    ).strip()

    if not selection or selection.lower() == "none":
        return []

    if selection.lower() == "all":
        return [
            discovered_packs[
                pack_id
            ]
            for pack_id in sorted(
                discovered_packs
            )
        ]

    requested_ids = [
        normalize_identifier(
            item
        )
        for item in selection.split(
            ","
        )
        if item.strip()
    ]

    missing = [
        pack_id
        for pack_id in requested_ids
        if pack_id not in discovered_packs
    ]

    if missing:
        raise ValueError(
            "Unknown pack(s): {}. Available packs: {}".format(
                ", ".join(
                    missing
                ),
                ", ".join(
                    sorted(
                        discovered_packs
                    )
                )
                or "none",
            )
        )

    return [
        discovered_packs[
            pack_id
        ]
        for pack_id in requested_ids
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build Scriptronaut QC documentation."
        )
    )

    parser.add_argument(
        "--product",
        choices=(
            "none",
            "core",
            "pro",
            "all",
        ),
        default="all",
        help=(
            "Core/Pro documentation products to build."
        ),
    )

    parser.add_argument(
        "--packs",
        default="none",
        help=(
            "Pack documentation to build: none, all, or a comma-separated "
            "list of discovered pack IDs such as rigging,animation."
        ),
    )

    parser.add_argument(
        "--list-packs",
        action="store_true",
        help=(
            "List packs discovered under the packs folder and exit."
        ),
    )

    parser.add_argument(
        "--product-pages",
        choices=(
            "none",
            "selected",
        ),
        default="selected",
        help=(
            "Generate product/marketing pages for the same Core, Pro, and "
            "Pack products selected for documentation."
        ),
    )

    parser.add_argument(
        "--version",
        default=VERSION,
    )

    args = parser.parse_args()

    discovered_packs = discover_packs()

    if args.list_packs:
        if not discovered_packs:
            print(
                "No documentation packs found."
            )
            return 0

        print(
            "Discovered documentation packs:"
        )

        for pack_id, pack in (
            discovered_packs.items()
        ):
            print(
                "  {} -> {}".format(
                    pack_id,
                    pack[
                        "checks_dir"
                    ],
                )
            )

        return 0

    selected_packs = resolve_pack_selection(
        args.packs,
        discovered_packs,
    )

    if (
        args.product == "none"
        and not selected_packs
    ):
        parser.error(
            "Nothing selected. Choose a Core/Pro product and/or one or more packs."
        )

    prepare_site(
        TEMPLATE,
        OUTPUT,
    )

    built_products = []

    if args.product != "none":
        product_ids = (
            (
                "core",
                "pro",
            )
            if args.product == "all"
            else (
                args.product,
            )
        )

        for product_id in product_ids:
            built_products.append(
                build_product(
                    product_id,
                    version=args.version,
                )
            )

    for pack in selected_packs:
        built_products.append(
            build_pack(
                pack,
                version=args.version,
            )
        )

    if args.product_pages == "selected":
        build_product_pages(
            built_products,
            version=args.version,
        )

    print(
        "Documentation site: {}".format(
            OUTPUT
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
