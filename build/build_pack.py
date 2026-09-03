"""Validate and build installable Scriptronaut QC check-pack extensions."""

from __future__ import annotations

import argparse
from pathlib import Path
import py_compile
import re
import shutil
import sys
import zipfile


SCRIPT_PATH = Path(__file__).resolve()
BUILD_DIR = SCRIPT_PATH.parent
PROJECT_ROOT = BUILD_DIR.parent
PACKS_DIR = PROJECT_ROOT / "packs"
DIST_DIR = BUILD_DIR / "dist"

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


def manifest_value(
        manifest_path: Path,
        key: str,
    ) -> str:
    """Read one required quoted string from blender_manifest.toml."""
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


def should_ignore(
        relative_path: Path,
    ) -> bool:
    """Return True for development files that must not enter the ZIP."""
    return (
        any(part in IGNORED_NAMES for part in relative_path.parts)
        or relative_path.suffix.lower() in IGNORED_SUFFIXES
    )


def validate_pack(
        pack_root: Path,
    ) -> tuple[str, str, list[Path]]:
    """Validate a pack and return its manifest identity and source files."""
    required = [
        pack_root / "__init__.py",
        pack_root / "blender_manifest.toml",
        pack_root / "checks",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Pack is incomplete:\n{}".format(
                "\n".join("  - {}".format(path) for path in missing)
            )
        )

    manifest_path = pack_root / "blender_manifest.toml"
    extension_id = manifest_value(manifest_path, "id")
    version = manifest_value(manifest_path, "version")

    source_files = [
        path
        for path in sorted(pack_root.rglob("*"))
        if path.is_file()
        and not should_ignore(path.relative_to(pack_root))
    ]
    check_files = [
        path
        for path in source_files
        if "checks" in path.relative_to(pack_root).parts
        and path.suffix.lower() == ".py"
        and path.name != "__init__.py"
    ]
    if not check_files:
        raise RuntimeError(
            "Pack contains no Python check modules: {}".format(pack_root)
        )

    for source_path in source_files:
        if source_path.suffix.lower() == ".py":
            py_compile.compile(
                str(source_path),
                doraise=True,
            )

    for cache_dir in sorted(pack_root.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache_dir, ignore_errors=True)

    return extension_id, version, source_files


def build_pack(
        pack_name: str,
    ) -> Path:
    """Create one Blender-installable extension ZIP."""
    pack_root = (PACKS_DIR / pack_name).resolve()
    try:
        pack_root.relative_to(PACKS_DIR.resolve())
    except ValueError as error:
        raise RuntimeError("Pack must be inside {}".format(PACKS_DIR)) from error

    if not pack_root.is_dir():
        raise RuntimeError("Pack folder was not found: {}".format(pack_root))

    extension_id, version, source_files = validate_pack(pack_root)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DIST_DIR / "{}-{}.zip".format(extension_id, version)

    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source_path in source_files:
            # Files are relative to pack_root so the manifest and entry point
            # are placed directly at the ZIP root, as Blender requires.
            archive.write(
                source_path,
                source_path.relative_to(pack_root).as_posix(),
            )

    with zipfile.ZipFile(output_path, "r") as archive:
        bad_file = archive.testzip()
        names = set(archive.namelist())

    if bad_file:
        raise RuntimeError("ZIP integrity failed at: {}".format(bad_file))

    if not {"__init__.py", "blender_manifest.toml"}.issubset(names):
        raise RuntimeError("ZIP root layout validation failed.")

    print("Built pack: {}".format(output_path))
    print("Extension ID: {}".format(extension_id))
    print("Version: {}".format(version))
    print("Files: {}".format(len(source_files)))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build installable Scriptronaut QC pack ZIP files."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--pack", help="Folder name under packs, such as rigging.")
    selection.add_argument("--all", action="store_true", help="Build every pack folder.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pack_names = (
            [path.name for path in sorted(PACKS_DIR.iterdir()) if path.is_dir()]
            if args.all
            else [args.pack]
        )
        if not pack_names:
            raise RuntimeError("No pack folders were found in {}".format(PACKS_DIR))
        for pack_name in pack_names:
            build_pack(pack_name)
        return 0
    except Exception as error:
        print("\nPACK BUILD ERROR:\n{}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
