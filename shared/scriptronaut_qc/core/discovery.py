"""Scriptronaut QC check discovery."""

import glob
import os

from ..constants import COMMON_CATEGORY
from ..utils.json_io import load_check_list
from .packs import get_registered_check_packs


def _legacy_pack(
        folder_path,
    ):
    """
    Builds a temporary fallback pack for older/local configurations.
    """
    if (
        not folder_path
        or not os.path.isdir(
            folder_path
        )
    ):
        return []

    return [{
        "pack_id":
            "legacy",

        "name":
            "Legacy QC Folder",

        "version":
            "0.0.0",

        "priority":
            1000,

        "checks_path":
            os.path.abspath(
                folder_path
            ),

        "metadata":
            {},
    }]


def _get_discovery_packs(
        folder_path=None,
        registered=True,
    ):
    """
    Returns packs used for discovery.

    Registered packs are authoritative. The legacy folder is used only when
    no packs have been registered, preserving compatibility during reloads
    and development.
    """
    if registered:
        packs = get_registered_check_packs()

        if packs:
            return packs

    return _legacy_pack(
        folder_path
    )


def _folder_categories(
        checks_path,
    ):
    """
    Returns category folders containing Python checks.
    """
    if not os.path.isdir(
        checks_path
    ):
        return []

    categories = []

    for folder in glob.glob(
        os.path.join(
            checks_path,
            "*",
        )
    ):
        if not os.path.isdir(
            folder
        ):
            continue

        category = os.path.basename(
            folder
        )

        if category in {
            "__pycache__",
            COMMON_CATEGORY,
        }:
            continue

        if not glob.glob(
            os.path.join(
                folder,
                "*.py",
            )
        ):
            continue

        categories.append(
            category
        )

    return sorted(
        categories
    )


def _pack_categories(
        pack,
        use_json=False,
    ):
    """
    Gets categories contributed by one registered pack.

    In JSON mode a pack uses its own check_settings.json when present.
    Packs without a JSON file continue using their physical category folders.
    This lets read-only commercial packs coexist with a Core JSON config.
    """
    checks_path = pack[
        "checks_path"
    ]

    if use_json:
        check_list = load_check_list(
            checks_path
        )

        if check_list:
            return sorted(
                category
                for category, checks in check_list.items()
                if (
                    isinstance(
                        category,
                        str,
                    )
                    and isinstance(
                        checks,
                        list,
                    )
                )
            )

    return _folder_categories(
        checks_path
    )


def get_categories(
        folder_path=None,
        use_json=False,
    ):
    """
    Returns categories contributed by all registered check packs.

    Categories with the same name are merged. For example Core and an
    Animation Pack may both contribute checks to "animation".
    """
    categories = set()

    for pack in _get_discovery_packs(
        folder_path,
    ):
        categories.update(
            _pack_categories(
                pack,
                use_json=use_json,
            )
        )

    return sorted(
        categories
    )


def _discover_pack_scripts(
        pack,
    ):
    """
    Discovers scripts belonging to one pack.
    """
    registry = {}
    duplicate_names = {}

    checks_path = pack[
        "checks_path"
    ]

    if not os.path.isdir(
        checks_path
    ):
        return (
            registry,
            duplicate_names,
        )

    pattern = os.path.join(
        checks_path,
        "**",
        "*.py",
    )

    for script_path in sorted(
        glob.glob(
            pattern,
            recursive=True,
        )
    ):
        filename = os.path.basename(
            script_path
        )

        if filename == "__init__.py":
            continue

        script_name = os.path.splitext(
            filename
        )[0]

        relative_folder = os.path.relpath(
            os.path.dirname(
                script_path
            ),
            checks_path,
        )

        source_category = relative_folder.replace(
            "\\",
            "/",
        )

        script_data = {
            "name":
                script_name,

            "script_path":
                os.path.abspath(
                    script_path
                ),

            "source_category":
                source_category,

            "pack_id":
                pack["pack_id"],

            "pack_name":
                pack["name"],

            "pack_version":
                pack["version"],

            "pack_root":
                checks_path,
        }

        if script_name in registry:
            duplicate_names.setdefault(
                script_name,
                [
                    registry[
                        script_name
                    ][
                        "script_path"
                    ]
                ],
            )

            duplicate_names[
                script_name
            ].append(
                script_data[
                    "script_path"
                ]
            )

            continue

        registry[
            script_name
        ] = script_data

    return (
        registry,
        duplicate_names,
    )


def discover_check_scripts(
        folder_path=None,
        registered=True,
    ):
    """
    Finds every QC script across registered packs.

    Check filenames remain globally unique for API v1. This keeps existing
    result/preferences behavior backward compatible while packs are being
    introduced.

    Args:
        folder_path (str | None):
            Legacy fallback folder.

        registered (bool):
            When False, scan only folder_path. Used by the existing Core
            category editor so external packs remain read-only there.

    Returns:
        tuple:
            registry, duplicate_names
    """
    registry = {}
    duplicate_names = {}

    packs = _get_discovery_packs(
        folder_path,
        registered=registered,
    )

    for pack in packs:
        (
            pack_registry,
            pack_duplicates,
        ) = _discover_pack_scripts(
            pack
        )

        for script_name, paths in (
            pack_duplicates.items()
        ):
            duplicate_names.setdefault(
                script_name,
                [],
            ).extend(
                paths
            )

        for script_name, script_data in (
            pack_registry.items()
        ):
            if script_name in registry:
                duplicate_names.setdefault(
                    script_name,
                    [
                        registry[
                            script_name
                        ][
                            "script_path"
                        ]
                    ],
                )

                duplicate_names[
                    script_name
                ].append(
                    script_data[
                        "script_path"
                    ]
                )

                continue

            registry[
                script_name
            ] = script_data

    # De-duplicate duplicate-path reporting.
    duplicate_names = {
        name: list(
            dict.fromkeys(
                paths
            )
        )
        for name, paths in duplicate_names.items()
    }

    return (
        registry,
        duplicate_names,
    )


def _configured_names_for_pack(
        pack,
        category,
        use_json,
    ):
    """
    Returns names assigned to category for one pack.

    None means folder assignment should be used.
    """
    if not use_json:
        return None

    check_list = load_check_list(
        pack[
            "checks_path"
        ]
    )

    if not check_list:
        return None

    configured = check_list.get(
        category,
        [],
    )

    if not isinstance(
        configured,
        list,
    ):
        return []

    return configured


def get_scripts(
        folder_path,
        category,
        use_json=False,
    ):
    """
    Returns scripts contributed to a category by registered packs.

    Each pack may use its own check_settings.json. A pack without JSON
    configuration uses its folder layout even when Core JSON mode is enabled.
    """
    if (
        not category
        or category in {
            "NONE",
            "----------------",
        }
    ):
        return []

    registry, duplicate_names = (
        discover_check_scripts(
            folder_path
        )
    )

    if duplicate_names:
        print(
            "QC checks contain duplicate script names:"
        )

        for script_name, paths in (
            duplicate_names.items()
        ):
            print(
                "  Duplicate check: {}".format(
                    script_name
                )
            )

            for path in paths:
                print(
                    "    {}".format(
                        path
                    )
                )

        return []

    packs_by_id = {
        pack["pack_id"]:
            pack
        for pack in _get_discovery_packs(
            folder_path
        )
    }

    script_records = []

    for script_data in registry.values():
        source_category = script_data[
            "source_category"
        ]

        # Common checks from any pack are available in every category.
        if source_category == COMMON_CATEGORY:
            script_records.append(
                dict(
                    script_data
                )
            )

            continue

        pack = packs_by_id.get(
            script_data[
                "pack_id"
            ]
        )

        if pack is None:
            continue

        configured_names = (
            _configured_names_for_pack(
                pack,
                category,
                use_json,
            )
        )

        if configured_names is None:
            if source_category != category:
                continue

        else:
            if script_data[
                "name"
            ] not in configured_names:
                continue

        script_records.append(
            dict(
                script_data
            )
        )

    return sorted(
        script_records,
        key=lambda item: (
            item[
                "source_category"
            ]
            != COMMON_CATEGORY,
            item[
                "pack_id"
            ],
            item[
                "name"
            ],
        ),
    )


def validate_check_configuration(
        folder_path,
        use_json=False,
    ):
    """
    Validates all registered check packs.
    """
    errors = []
    warnings = []

    registry, duplicate_names = (
        discover_check_scripts(
            folder_path
        )
    )

    for script_name, paths in (
        duplicate_names.items()
    ):
        errors.append(
            "Duplicate QC script name '{}': {}".format(
                script_name,
                ", ".join(
                    paths
                ),
            )
        )

    if use_json:
        for pack in _get_discovery_packs(
            folder_path
        ):
            check_list = load_check_list(
                pack[
                    "checks_path"
                ]
            )

            # Packs are allowed to omit JSON and use folders.
            if not check_list:
                continue

            pack_registry, _ = (
                _discover_pack_scripts(
                    pack
                )
            )

            for category, script_names in (
                check_list.items()
            ):
                if not isinstance(
                    script_names,
                    list,
                ):
                    errors.append(
                        (
                            "Pack '{}' category '{}' must contain a list."
                        ).format(
                            pack[
                                "pack_id"
                            ],
                            category,
                        )
                    )

                    continue

                seen_names = set()

                for script_name in script_names:
                    if not isinstance(
                        script_name,
                        str,
                    ):
                        errors.append(
                            (
                                "Pack '{}' category '{}' contains a "
                                "non-string entry: {}"
                            ).format(
                                pack[
                                    "pack_id"
                                ],
                                category,
                                script_name,
                            )
                        )

                        continue

                    if script_name in seen_names:
                        warnings.append(
                            (
                                "Pack '{}' category '{}' lists '{}' "
                                "more than once."
                            ).format(
                                pack[
                                    "pack_id"
                                ],
                                category,
                                script_name,
                            )
                        )

                        continue

                    seen_names.add(
                        script_name
                    )

                    if script_name not in pack_registry:
                        errors.append(
                            (
                                "Pack '{}' category '{}' references "
                                "missing check '{}'."
                            ).format(
                                pack[
                                    "pack_id"
                                ],
                                category,
                                script_name,
                            )
                        )

    return {
        "valid":
            not errors,

        "errors":
            errors,

        "warnings":
            warnings,
    }
