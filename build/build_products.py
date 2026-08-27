"""Build self-contained Scriptronaut QC Checker development products.

Source layout
-------------

qc_checker/
    shared/
        checks/
        scriptronaut_qc/

    core/
        __init__.py
        blender_manifest.toml

    pro/
        checks/
        scriptronaut_qc_pro/
        __init__.py
        blender_manifest.toml

    build/
        build_products.py
        dev/
            qc_checker_core/
            qc_checker_pro/

The generated development products are intentionally self-contained so they
match the shape of the Blender package we will eventually distribute.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import py_compile
import re
import shutil
import sys


SCRIPT_PATH = Path(__file__).resolve()
BUILD_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = BUILD_DIR.parent

SHARED_DIR = PROJECT_ROOT / "shared"
CORE_DIR = PROJECT_ROOT / "core"
PRO_DIR = PROJECT_ROOT / "pro"

DEV_DIR = BUILD_DIR / "dev"

PRODUCTS = {
    "core": {
        "source": CORE_DIR,
        "output": DEV_DIR / "qc_checker_core",
        "tier": "Core",
    },
    "pro": {
        "source": PRO_DIR,
        "output": DEV_DIR / "qc_checker_pro",
        "tier": "Pro",
    },
}

IGNORED_NAMES = {
    "__pycache__",
    ".git",
    ".gitignore",
    ".gitattributes",
}

IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def should_ignore(
        path: Path,
) -> bool:
    """
    Returns True for files/folders that should never enter a product build.
    """
    if path.name in IGNORED_NAMES:
        return True

    if path.suffix.lower() in IGNORED_SUFFIXES:
        return True

    return False


def copy_tree(
        source: Path,
        destination: Path,
        *,
        exclude_names: set[str] | None = None,
        fail_on_existing_files: bool = False,
) -> None:
    """
    Copies one source tree into destination.

    Args:
        source:
            Directory to copy.

        destination:
            Destination directory.

        exclude_names:
            Basenames to skip anywhere in this copy.

        fail_on_existing_files:
            When True, an incoming file may not replace a file already
            assembled into the product. This protects Core checks from being
            accidentally overwritten by Pro checks with the same relative
            path/name.
    """
    if not source.exists():
        return

    if not source.is_dir():
        raise RuntimeError(
            "Expected directory: {}".format(
                source
            )
        )

    exclude_names = set(
        exclude_names
        or ()
    )

    for source_path in sorted(
        source.rglob("*")
    ):
        relative_path = source_path.relative_to(
            source
        )

        if any(
            part in IGNORED_NAMES
            for part in relative_path.parts
        ):
            continue

        if source_path.name in exclude_names:
            continue

        if should_ignore(
            source_path
        ):
            continue

        destination_path = (
            destination
            / relative_path
        )

        if source_path.is_dir():
            destination_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            continue

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            fail_on_existing_files
            and destination_path.exists()
        ):
            raise RuntimeError(
                (
                    "Build collision: '{}' would overwrite '{}'. "
                    "Pro checks/features must add to Core rather than "
                    "silently replacing shared files."
                ).format(
                    source_path,
                    destination_path,
                )
            )

        shutil.copy2(
            source_path,
            destination_path,
        )


def copy_file(
        source: Path,
        destination: Path,
    ) -> None:
    """
    Copies one required product file.
    """
    if not source.is_file():
        raise RuntimeError(
            "Required build file is missing: {}".format(
                source
            )
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )


def patch_product_tier(
        product_root: Path,
        tier: str,
    ) -> None:
    """
    Sets TIER in the generated product only.

    The source framework remains shared. Core and Pro receive their tier
    identity when assembled.
    """
    constants_path = (
        product_root
        / "scriptronaut_qc"
        / "constants.py"
    )

    if not constants_path.is_file():
        raise RuntimeError(
            "Generated constants.py was not found: {}".format(
                constants_path
            )
        )

    text = constants_path.read_text(
        encoding="utf-8"
    )

    pattern = re.compile(
        r'^TIER\s*=\s*["\'][^"\']*["\']\s*$',
        re.MULTILINE,
    )

    replacement = (
        'TIER = "{}"'.format(
            tier
        )
    )

    text, replacement_count = pattern.subn(
        replacement,
        text,
        count=1,
    )

    if replacement_count != 1:
        raise RuntimeError(
            "Could not set TIER in generated constants.py."
        )

    constants_path.write_text(
        text,
        encoding="utf-8",
    )


def validate_source_layout() -> None:
    """
    Validates the source folders required by both products.
    """
    required = [
        SHARED_DIR / "checks",
        SHARED_DIR / "scriptronaut_qc",
        CORE_DIR / "__init__.py",
        CORE_DIR / "blender_manifest.toml",
        PRO_DIR / "__init__.py",
        PRO_DIR / "blender_manifest.toml",
    ]

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing required source paths:\n{}".format(
                "\n".join(
                    "  - {}".format(
                        path
                    )
                    for path in missing
                )
            )
        )

    # check_settings.json is Pro-only.
    shared_settings = (
        SHARED_DIR
        / "checks"
        / "check_settings.json"
    )

    if shared_settings.exists():
        raise RuntimeError(
            (
                "check_settings.json must not exist in shared/checks. "
                "It is a Pro-only product file."
            )
        )


def syntax_check_product(
        product_root: Path,
    ) -> int:
    """
    Syntax-checks every Python file in one assembled product.

    Returns:
        int:
            Number of checked Python files.
    """
    checked_count = 0

    for path in sorted(
        product_root.rglob("*.py")
    ):
        py_compile.compile(
            str(
                path
            ),
            doraise=True,
        )

        checked_count += 1

    # py_compile creates __pycache__. Remove generated caches so the
    # development product remains clean.
    for cache_dir in sorted(
        product_root.rglob("__pycache__"),
        reverse=True,
    ):
        shutil.rmtree(
            cache_dir,
            ignore_errors=True,
        )

    return checked_count


def validate_product(
        tier_key: str,
        product_root: Path,
    ) -> None:
    """
    Performs product-specific assembly validation.
    """
    required = [
        product_root / "__init__.py",
        product_root / "blender_manifest.toml",
        product_root / "checks",
        product_root / "scriptronaut_qc",
    ]

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Generated product is incomplete:\n{}".format(
                "\n".join(
                    "  - {}".format(
                        path
                    )
                    for path in missing
                )
            )
        )

    check_settings = (
        product_root
        / "checks"
        / "check_settings.json"
    )

    if tier_key == "core":

        if check_settings.exists():
            raise RuntimeError(
                (
                    "Core build unexpectedly contains "
                    "checks/check_settings.json."
                )
            )

        pro_package = (
            product_root
            / "scriptronaut_qc_pro"
        )

        if pro_package.exists():
            raise RuntimeError(
                (
                    "Core build unexpectedly contains "
                    "scriptronaut_qc_pro."
                )
            )

        if (
            product_root
            / "scriptronaut_qc"
            / "operators"
            / "category_editor.py"
        ).exists():
            raise RuntimeError(
                (
                    "Core build unexpectedly contains the "
                    "Pro check-settings editor."
                )
            )

    elif tier_key == "pro":

        source_pro_settings = (
            PRO_DIR
            / "checks"
            / "check_settings.json"
        )

        if (
            source_pro_settings.exists()
            and not check_settings.exists()
        ):
            raise RuntimeError(
                (
                    "Pro source contains check_settings.json, but it "
                    "was not copied into the Pro build."
                )
            )


def build_product(
        tier_key: str,
    ) -> Path:
    """
    Assembles one development product.
    """
    if tier_key not in PRODUCTS:
        raise ValueError(
            "Unknown tier: {}".format(
                tier_key
            )
        )

    product = PRODUCTS[
        tier_key
    ]

    output_root = product[
        "output"
    ]

    product_source = product[
        "source"
    ]

    print("")
    print(
        "Building Scriptronaut QC Checker {}...".format(
            product[
                "tier"
            ]
        )
    )

    if output_root.exists():
        shutil.rmtree(
            output_root
        )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Shared framework
    # ---------------------------------------------------------

    copy_tree(
        SHARED_DIR / "scriptronaut_qc",
        output_root / "scriptronaut_qc",
    )

    # ---------------------------------------------------------
    # Shared/Core checks
    #
    # check_settings.json is explicitly excluded as a second safety net,
    # even though it should no longer exist in shared source.
    # ---------------------------------------------------------

    copy_tree(
        SHARED_DIR / "checks",
        output_root / "checks",
        exclude_names={
            "check_settings.json",
        },
    )

    # ---------------------------------------------------------
    # Product entry point + manifest
    # ---------------------------------------------------------

    copy_file(
        product_source / "__init__.py",
        output_root / "__init__.py",
    )

    copy_file(
        product_source / "blender_manifest.toml",
        output_root / "blender_manifest.toml",
    )

    # ---------------------------------------------------------
    # Pro additions
    # ---------------------------------------------------------

    if tier_key == "pro":

        # Extra Pro checks/categories are merged into the same checks tree.
        # Existing Core check files may not be overwritten.
        copy_tree(
            PRO_DIR / "checks",
            output_root / "checks",
            fail_on_existing_files=True,
        )

        # Future Pro-only framework/features live here.
        pro_features = (
            PRO_DIR
            / "scriptronaut_qc_pro"
        )

        if pro_features.exists():
            copy_tree(
                pro_features,
                output_root / "scriptronaut_qc_pro",
            )

    # ---------------------------------------------------------
    # Generated product identity
    # ---------------------------------------------------------

    patch_product_tier(
        output_root,
        product[
            "tier"
        ],
    )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    validate_product(
        tier_key,
        output_root,
    )

    checked_count = syntax_check_product(
        output_root
    )

    print(
        "  Output: {}".format(
            output_root
        )
    )

    print(
        "  Python files checked: {}".format(
            checked_count
        )
    )

    print(
        "  Tier: {}".format(
            product[
                "tier"
            ]
        )
    )

    return output_root


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments.

    Examples:
        python build_products.py --dev core
        python build_products.py --dev pro
        python build_products.py --dev all
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build Scriptronaut QC Checker development products."
        )
    )

    parser.add_argument(
        "--dev",
        choices=(
            "core",
            "pro",
            "all",
        ),
        required=True,
        help=(
            "Development product to assemble."
        ),
    )

    return parser.parse_args()


def main() -> int:
    """
    Command-line entry point.
    """
    args = parse_args()

    try:
        validate_source_layout()

        tiers = (
            ("core", "pro")
            if args.dev == "all"
            else (
                args.dev,
            )
        )

        outputs = []

        for tier_key in tiers:
            outputs.append(
                build_product(
                    tier_key
                )
            )

        print("")
        print(
            "Build completed successfully."
        )

        for output in outputs:
            print(
                "  {}".format(
                    output
                )
            )

        return 0

    except Exception as error:
        print("")
        print(
            "BUILD ERROR:"
        )
        print(
            str(
                error
            )
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
