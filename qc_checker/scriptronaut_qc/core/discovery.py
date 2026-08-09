"""Scriptronaut QC Checks internal module."""

import glob
import os
import traceback
from typing import Any

from ..constants import CHECK_SETTINGS_FILE, COMMON_CATEGORY
from ..utils.json_io import load_check_list


def get_categories(folder_path, use_json=False):
    """
    Returns available QC categories.

    When JSON mode is enabled, categories come from CHECK_SETTINGS_FILE.
    Otherwise categories come from folders under qc_modules.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        list[str]: Sorted category names.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    if use_json:
        check_list = load_check_list(folder_path)
        if not check_list:
            return []

        return sorted(
            category
            for category, checks in check_list.items()
            if isinstance(category, str)
            and isinstance(checks, list)
        )

    return sorted([
        os.path.basename(folder)
        for folder in glob.glob(os.path.join(folder_path, "*"))
        if (
            os.path.isdir(folder)
            and os.path.basename(folder) not in {
                "__pycache__",
                COMMON_CATEGORY,
            }
            and glob.glob(os.path.join(folder, "*.py"))
        )
    ])


def get_scripts(folder_path, category, use_json=False):
    """
    Returns the QC scripts assigned to a category.

    JSON mode:
        - Discovers all scripts recursively.
        - Requires globally unique script names.
        - Uses CHECK_SETTINGS_FILE to assign scripts to categories.
        - Ignores missing script entries and prints warnings.

    Folder mode:
        - Loads all scripts from common.
        - Loads all scripts from the selected category.

    Args:
        folder_path (str): Root QC modules directory.
        category (str): Selected category.

    Returns:
        list[dict]: Script metadata records.
    """
    if (
        not folder_path
        or not category
        or category in {"NONE", "----------------"}
    ):
        return []

    registry, duplicate_names = discover_check_scripts(folder_path)

    if duplicate_names:
        print("QC checks contain duplicate script names:")

        for script_name, paths in duplicate_names.items():
            print("  Duplicate check: {}".format(script_name))
            for path in paths:
                print("    {}".format(path))

        # Do not continue because JSON references would be ambiguous.
        return []

    if use_json:
        check_list = load_check_list(folder_path)
        configured_names = check_list.get(category, [])

        if not isinstance(configured_names, list):
            print(
                'QC category "{}" must contain a JSON list.'.format(
                    category
                )
            )
            return []

        script_records = []
        added_names = set()

        for script_name in configured_names:
            if not isinstance(script_name, str):
                print(
                    "Invalid QC script entry in category '{}': {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            if script_name in added_names:
                print(
                    "Duplicate JSON entry ignored: {} -> {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            script_data = registry.get(script_name)
            if script_data is None:
                print(
                    "QC script listed in JSON but not found: "
                    "{} -> {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            added_names.add(script_name)
            script_records.append(dict(script_data))

        return script_records

    # ---------------------------------------------------------
    # Folder-based fallback
    # ---------------------------------------------------------
    script_records = []

    source_categories = [
        COMMON_CATEGORY,
        category,
    ]

    for script_data in registry.values():
        if script_data["source_category"] in source_categories:
            script_records.append(dict(script_data))

    return sorted(
        script_records,
        key=lambda item: (
            item["source_category"] != COMMON_CATEGORY,
            item["name"],
        ),
    )


def validate_check_configuration(folder_path, use_json=False):
    """
    Validates discovered QC scripts and the optional JSON configuration.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        dict:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
        }
    """
    errors = []
    warnings = []

    registry, duplicate_names = discover_check_scripts(folder_path)

    for script_name, paths in duplicate_names.items():
        errors.append(
            "Duplicate QC script name '{}': {}".format(
                script_name,
                ", ".join(paths),
            )
        )

    if use_json:
        check_list = load_check_list(folder_path)

        if not check_list:
            errors.append(
                "JSON mode is enabled, but CHECK_SETTINGS_FILE is missing "
                "or invalid."
            )
        else:
            for category, script_names in check_list.items():
                if not isinstance(script_names, list):
                    errors.append(
                        "Category '{}' must contain a list.".format(
                            category
                        )
                    )
                    continue

                seen_names = set()

                for script_name in script_names:
                    if not isinstance(script_name, str):
                        errors.append(
                            "Category '{}' contains a non-string entry: "
                            "{}".format(category, script_name)
                        )
                        continue

                    if script_name in seen_names:
                        warnings.append(
                            "Category '{}' lists '{}' more than once.".format(
                                category,
                                script_name,
                            )
                        )
                        continue

                    seen_names.add(script_name)

                    if script_name not in registry:
                        errors.append(
                            "Category '{}' references missing check "
                            "'{}'.".format(
                                category,
                                script_name,
                            )
                        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def discover_check_scripts(folder_path):
    """
    Finds every QC check script under the QC modules directory.

    Script names must be unique across all folders.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        tuple:
            registry (dict): Script names mapped to script metadata.
            duplicate_names (dict): Duplicate names mapped to paths.

        Example registry:
        {
            "freeze_transforms": {
                "name": "freeze_transforms",
                "script_path": ".../common/freeze_transforms.py",
                "source_category": "common",
            }
        }
    """
    registry = {}
    duplicate_names = {}

    if not folder_path or not os.path.isdir(folder_path):
        return registry, duplicate_names

    pattern = os.path.join(folder_path, "**", "*.py")

    for script_path in sorted(glob.glob(pattern, recursive=True)):
        filename = os.path.basename(script_path)

        if filename == "__init__.py":
            continue

        script_name = os.path.splitext(filename)[0]

        relative_folder = os.path.relpath(
            os.path.dirname(script_path),
            folder_path,
        )

        source_category = relative_folder.replace("\\", "/")

        script_data = {
            "name": script_name,
            "script_path": os.path.abspath(script_path),
            "source_category": source_category,
        }

        if script_name in registry:
            duplicate_names.setdefault(
                script_name,
                [registry[script_name]["script_path"]],
            )
            duplicate_names[script_name].append(
                script_data["script_path"]
            )
            continue

        registry[script_name] = script_data

    return registry, duplicate_names
