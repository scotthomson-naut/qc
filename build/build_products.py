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
from datetime import datetime
from pathlib import Path
import py_compile
import re
import shutil
import sys
import zipfile


SCRIPT_PATH = Path(__file__).resolve()
BUILD_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = BUILD_DIR.parent

SHARED_DIR = PROJECT_ROOT / "shared"
CORE_DIR = PROJECT_ROOT / "core"
PRO_DIR = PROJECT_ROOT / "pro"

DEV_DIR = BUILD_DIR / "dev"
PACKAGE_STAGE_DIR = BUILD_DIR / ".package_build"
DIST_DIR = BUILD_DIR / "dist"
VERSION_FILE = PROJECT_ROOT / "VERSION"

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


def read_product_version() -> str:
    """Reads and validates the single project version from VERSION."""
    if not VERSION_FILE.is_file():
        raise RuntimeError(
            "Project VERSION file was not found: {}".format(VERSION_FILE)
        )

    version = VERSION_FILE.read_text(encoding="utf-8").strip()

    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise RuntimeError(
            "VERSION must use X.Y.Z semantic version format, for example 0.1.0. "
            "Found: {!r}".format(version)
        )

    return version


def validate_version_string(version: str) -> str:
    """Validates and returns an X.Y.Z semantic version string."""
    version = version.strip()
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise RuntimeError(
            "Version must use X.Y.Z semantic version format, for example 0.1.0. "
            "Found: {!r}".format(version)
        )
    return version


def set_product_version(version: str) -> str:
    """Validates and writes the project VERSION file when it changed."""
    version = validate_version_string(version)
    current = read_product_version()
    if version != current:
        VERSION_FILE.write_text(version + "\n", encoding="utf-8")
        print("Project VERSION updated: {} -> {}".format(current, version))
    else:
        print("Project VERSION unchanged: {}".format(version))
    return version


def patch_product_version(
        product_root: Path,
        version: str,
    ) -> None:
    """Sets the generated Blender manifest version from the root VERSION file."""
    manifest_path = product_root / "blender_manifest.toml"
    text = manifest_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'^version\s*=\s*["\'][^"\']*["\']\s*$',
        re.MULTILINE,
    )
    text, replacement_count = pattern.subn(
        'version = "{}"'.format(version),
        text,
        count=1,
    )
    if replacement_count != 1:
        raise RuntimeError(
            "Could not set version in generated blender_manifest.toml."
        )
    manifest_path.write_text(text, encoding="utf-8")



def patch_runtime_version(
        product_root: Path,
        version: str,
    ) -> None:
    """Sets the generated runtime version used by feedback and UI metadata."""
    constants_path = product_root / "scriptronaut_qc" / "constants.py"
    text = constants_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'^VERSION\s*=\s*["\'][^"\']*["\']\s*$',
        re.MULTILINE,
    )
    text, replacement_count = pattern.subn(
        'VERSION = "{}"'.format(version),
        text,
        count=1,
    )
    if replacement_count != 1:
        raise RuntimeError(
            "Could not set VERSION in generated scriptronaut_qc/constants.py."
        )
    constants_path.write_text(text, encoding="utf-8")

def patch_build_metadata(
        product_root: Path,
        channel: str,
        include_beta_tools: bool,
    ) -> None:
    """Sets generated build channel and optional Beta UI visibility."""
    constants_path = product_root / "scriptronaut_qc" / "constants.py"
    text = constants_path.read_text(encoding="utf-8")

    replacements = (
        (
            r'^BUILD_CHANNEL\s*=\s*["\'][^"\']*["\']\s*$',
            'BUILD_CHANNEL = "{}"'.format(channel),
            "BUILD_CHANNEL",
        ),
        (
            r'^INCLUDE_BETA_TOOLS\s*=\s*(?:True|False)\s*$',
            'INCLUDE_BETA_TOOLS = {}'.format(
                "True" if include_beta_tools else "False"
            ),
            "INCLUDE_BETA_TOOLS",
        ),
    )

    for pattern, replacement, label in replacements:
        text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(
                "Could not set {} in generated constants.py.".format(label)
            )

    constants_path.write_text(text, encoding="utf-8")


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
        output_root: Path | None = None,
        *,
        channel: str,
        include_beta_tools: bool,
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

    if output_root is None:
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

    product_version = read_product_version()
    patch_product_version(
        output_root,
        product_version,
    )

    patch_runtime_version(
        output_root,
        product_version,
    )

    patch_build_metadata(
        output_root,
        channel,
        include_beta_tools,
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

    print(
        "  Version: {}".format(
            product_version
        )
    )

    return output_root



def manifest_value(
        manifest_path: Path,
        key: str,
) -> str:
    """Reads one required quoted string value from a Blender manifest."""
    text = manifest_path.read_text(
        encoding="utf-8",
    )
    match = re.search(
        r'^\s*{}\s*=\s*["\']([^"\']+)["\']'.format(
            re.escape(key)
        ),
        text,
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError(
            "Manifest is missing a valid {} value: {}".format(
                key,
                manifest_path,
            )
        )
    return match.group(1).strip()


def validate_blender_manifest(
        manifest_path: Path,
) -> None:
    """Validates manifest fields needed by QC Checker beta packages."""
    text = manifest_path.read_text(encoding="utf-8")

    required = (
        "schema_version",
        "id",
        "version",
        "name",
        "tagline",
        "maintainer",
        "type",
        "blender_version_min",
        "license",
    )
    for key in required:
        if not re.search(r"^\s*{}\s*=".format(re.escape(key)), text, re.MULTILINE):
            raise RuntimeError(
                "Manifest is missing required field '{}': {}".format(
                    key, manifest_path
                )
            )

    permission_block = re.search(
        r"(?ms)^\[permissions\]\s*(.*?)(?=^\[|\Z)",
        text,
    )
    if permission_block:
        for line in permission_block.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z_]+)\s*=\s*(.+)$", line)
            if not match:
                raise RuntimeError(
                    "Invalid permission entry in {}: {}".format(
                        manifest_path, line
                    )
                )
            permission, value = match.groups()
            if permission not in {
                "files", "network", "clipboard", "camera", "microphone"
            }:
                raise RuntimeError(
                    "Unsupported Blender permission '{}': {}".format(
                        permission, manifest_path
                    )
                )
            if not re.fullmatch(r'"[^"]+"|\'[^\']+\'', value.strip()):
                raise RuntimeError(
                    "Permission '{}' must contain a short explanation string, "
                    "not a boolean: {}".format(permission, manifest_path)
                )


def package_product(
        tier_key: str,
        product_root: Path,
) -> Path:
    """Creates a Blender-installable Extension ZIP from an assembled product."""
    manifest_path = product_root / "blender_manifest.toml"
    validate_blender_manifest(
        manifest_path
    )
    extension_id = manifest_value(
        manifest_path,
        "id",
    )
    version = manifest_value(
        manifest_path,
        "version",
    )

    DIST_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        DIST_DIR
        / "{}-{}-beta.zip".format(
            extension_id,
            version,
        )
    )

    if output_path.exists():
        output_path.unlink()

    source_files = [
        path
        for path in sorted(product_root.rglob("*"))
        if path.is_file()
        and not should_ignore(path)
    ]

    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source_path in source_files:
            # Blender Extensions require __init__.py and
            # blender_manifest.toml directly at the ZIP root.
            archive.write(
                source_path,
                source_path.relative_to(product_root).as_posix(),
            )

    with zipfile.ZipFile(
        output_path,
        "r",
    ) as archive:
        bad_file = archive.testzip()
        names = set(
            archive.namelist()
        )

    if bad_file:
        raise RuntimeError(
            "ZIP integrity failed at: {}".format(
                bad_file
            )
        )

    required_root_files = {
        "__init__.py",
        "blender_manifest.toml",
    }

    if not required_root_files.issubset(
        names
    ):
        raise RuntimeError(
            "Installable ZIP root layout validation failed."
        )

    # A wrapper folder would make Blender see paths such as
    # qc_checker_core/__init__.py instead of root-level extension files.
    if any(
        name.count("/") == 0
        and name not in required_root_files
        for name in names
    ):
        pass

    # Create an editable changelog beside the successful ZIP build.
    # Never overwrite notes already written for this version.
    changelog_path = output_path.with_suffix(".log")
    if not changelog_path.exists():
        timestamp = datetime.now().strftime("%Y-%m-%d @ %H:%M:%S")
        template = (
            "# Changelog\n\n"
            f"## {version}-beta - {timestamp}\n\n"
            "### Fixed\n"
            "* In **CATEGORY** check **NAME**:\n"
            "  * Setting X.\n"
            "  * Setting Y.\n\n"
            "* In **CATEGORY** check **NAME**:\n"
            "  * Setting X.\n"
            "  * Setting Y.\n\n"
            "### Added\n"
            "* In **CATEGORY** check **NAME**:\n"
            "  * Setting X.\n"
            "  * Setting Y.\n\n"
            "### Removed\n"
            "* In **CATEGORY** check **NAME**:\n"
            "  * Setting X.\n"
            "  * Setting Y.\n"
        )
        changelog_path.write_text(template, encoding="utf-8")
        print(f"  Changelog created: {changelog_path}")
    else:
        print(f"  Changelog preserved (already exists): {changelog_path}")

    print(
        "  Installable ZIP: {}".format(
            output_path
        )
    )
    print(
        "  Extension ID: {}".format(
            extension_id
        )
    )
    print(
        "  Version: {}".format(
            version
        )
    )

    return output_path


def cleanup_package_stage() -> None:
    """Removes temporary package staging without touching persistent dev builds."""
    if PACKAGE_STAGE_DIR.exists():
        shutil.rmtree(PACKAGE_STAGE_DIR)
        print(
            "  Removed temporary package staging: {}".format(
                PACKAGE_STAGE_DIR
            )
        )

def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments.

    Examples:
        python build_products.py --dev core
        python build_products.py --dev pro
        python build_products.py --dev all
        python build_products.py --package core
        python build_products.py --package pro
        python build_products.py --package all
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build Scriptronaut QC Checker development products."
        )
    )

    selection = parser.add_mutually_exclusive_group(
        required=True,
    )

    selection.add_argument(
        "--dev",
        choices=(
            "core",
            "pro",
            "all",
        ),
        help=(
            "Development product to assemble."
        ),
    )

    selection.add_argument(
        "--package",
        choices=(
            "core",
            "pro",
            "all",
        ),
        help=(
            "Assemble and create Blender-installable Extension ZIP file(s)."
        ),
    )

    parser.add_argument(
        "--version",
        help=(
            "Optional X.Y.Z project version. When supplied, VERSION is updated "
            "before the build."
        ),
    )

    parser.add_argument(
        "--beta-tools",
        choices=("yes", "no"),
        default="yes",
        help="Include the Beta panel tools in the generated product.",
    )

    return parser.parse_args()


def main() -> int:
    """
    Command-line entry point.
    """
    args = parse_args()

    try:
        if args.version is not None:
            set_product_version(args.version)

        validate_source_layout()

        selection = (
            args.package
            if args.package is not None
            else args.dev
        )

        tiers = (
            ("core", "pro")
            if selection == "all"
            else (
                selection,
            )
        )

        outputs = []
        packages = []

        if args.package is not None:
            cleanup_package_stage()

        for tier_key in tiers:
            if args.package is not None:
                product_root = build_product(
                    tier_key,
                    PACKAGE_STAGE_DIR / "qc_checker_{}".format(tier_key),
                    channel="beta",
                    include_beta_tools=(args.beta_tools == "yes"),
                )
            else:
                product_root = build_product(
                    tier_key,
                    channel="dev",
                    include_beta_tools=(args.beta_tools == "yes"),
                )

            outputs.append(
                product_root
            )

            if args.package is not None:
                packages.append(
                    package_product(
                        tier_key,
                        product_root,
                    )
                )

        print("")
        print(
            "Build completed successfully."
        )

        for output in outputs:
            print(
                "  Product: {}".format(
                    output
                )
            )

        for package in packages:
            print(
                "  Installable ZIP: {}".format(
                    package
                )
            )

        if args.package is not None:
            cleanup_package_stage()

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
