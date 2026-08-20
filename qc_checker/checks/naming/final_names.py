# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Final Names"
DESCRIPTION = (
    "Checks that Object and Datablock names do not use temporary, test, "
    "or debug prefixes such as tmp_, temp_, debug_, or test_. "
    "Final production assets should use descriptive production-ready names."
)
WHY = (
    "Helps with finding and identifying objects better."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

CASE_SENSITIVE = False

DEFAULT_PREFIXES = (
    "tmp",
    "temp",
    "debug",
    "test",
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks object names and datablock names for temporary/debug prefixes.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_invalid_prefixes()
    )

    issues = []

    for object_name, data in failed_objects.items():

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_data = data.get(
            "object_name"
        )

        if object_name_data:
            issues.append(
                (
                    "Failed object: {} - Object name {!r} "
                    "uses invalid prefix {!r}"
                ).format(
                    object_name,
                    object_name_data["name"],
                    object_name_data["prefix"],
                )
            )

        # -----------------------------------------------------
        # Datablock name
        # -----------------------------------------------------

        datablock_name_data = data.get(
            "datablock_name"
        )

        if datablock_name_data:
            issues.append(
                (
                    "Failed object: {} - Datablock name {!r} "
                    "uses invalid prefix {!r}"
                ).format(
                    object_name,
                    datablock_name_data["name"],
                    datablock_name_data["prefix"],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.
    """
    return fix_invalid_prefixes(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_invalid_prefixes(
        objects=None,
        prefixes=None,
    ):
    """
    Finds objects whose object name or datablock name starts with
    a temporary/debug/test prefix.

    Default prefixes:
        tmp
        temp
        debug
        test

    Examples that fail:
        tmp_Cube
        temp_mesh
        debug_Character
        test_object
        TMP_Render
        TestCube

    Datablock examples:
        Object: Chair
        Mesh:   tmp_ChairMesh

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

        prefixes (iterable[str] | None):
            Prefixes to check.

    Returns:
        dict:
        {
            "Chair": {
                "object_name": {
                    "name": "tmp_Chair",
                    "prefix": "tmp",
                },
                "datablock_name": {
                    "name": "temp_ChairMesh",
                    "prefix": "temp",
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    failed_objects = {}

    for obj in objects:

        # Directly linked library objects are read-only and are
        # outside the scope of local naming QC.
        if obj.library is not None:
            continue

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_result = (
            get_invalid_prefix_data(
                obj.name,
                prefixes=prefixes,
            )
        )

        # -----------------------------------------------------
        # Datablock name
        # -----------------------------------------------------

        datablock_name_result = None

        datablock = getattr(
            obj,
            "data",
            None,
        )

        if (
            datablock is not None
            and hasattr(
                datablock,
                "name",
            )
        ):
            datablock_name_result = (
                get_invalid_prefix_data(
                    datablock.name,
                    prefixes=prefixes,
                )
            )

        if (
            object_name_result is None
            and datablock_name_result is None
        ):
            continue

        result = {}

        if object_name_result is not None:
            result["object_name"] = (
                object_name_result
            )

        if datablock_name_result is not None:
            result["datablock_name"] = (
                datablock_name_result
            )

        failed_objects[
            obj.name
        ] = result

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_invalid_prefix_data(
        name,
        prefixes=None,
    ):
    """
    Checks a single name for an invalid prefix.

    Returns:
        dict | None:
        {
            "name": "tmp_Chair",
            "prefix": "tmp",
        }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    # Longer prefixes first.
    prefixes = sorted(
        prefixes,
        key=len,
        reverse=True,
    )

    compare_name = (
        name
        if CASE_SENSITIVE
        else name.lower()
    )

    for prefix in prefixes:

        compare_prefix = (
            prefix
            if CASE_SENSITIVE
            else prefix.lower()
        )

        if compare_name.startswith(
            compare_prefix
        ):
            return {
                "name": name,
                "prefix": prefix,
            }

    return None


def remove_invalid_prefix(
        name,
        prefixes=None,
        strip_separators=True,
    ):
    """
    Removes an invalid prefix from a name.

    Examples:
        tmp_Cube    -> Cube
        temp-Chair  -> Chair
        debugRig    -> Rig
        TEST_object -> object

    Returns:
        tuple:
            (
                new_name,
                matched_prefix,
            )

        Returns (None, None) when no prefix is found.
    """
    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    prefixes = sorted(
        prefixes,
        key=len,
        reverse=True,
    )

    compare_name = (
        name
        if CASE_SENSITIVE
        else name.lower()
    )

    for prefix in prefixes:

        compare_prefix = (
            prefix
            if CASE_SENSITIVE
            else prefix.lower()
        )

        if not compare_name.startswith(
            compare_prefix
        ):
            continue

        new_name = name[
            len(prefix):
        ]

        if strip_separators:
            new_name = new_name.lstrip(
                " _-."
            )

        if not new_name:
            return None, prefix

        return (
            new_name,
            prefix,
        )

    return (
        None,
        None,
    )


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_invalid_prefixes(
        result_data=None,
        prefixes=None,
        strip_separators=True,
    ):
    """
    Removes invalid prefixes from object names and datablock names.

    Datablock names are only changed when the datablock is not shared.

    Args:
        result_data (dict):
            Result returned by main().

        prefixes (iterable[str] | None):
            Invalid prefixes to remove.

        strip_separators (bool):
            Remove separators immediately following the prefix.

    Returns:
        dict:
        {
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    if prefixes is None:
        prefixes = DEFAULT_PREFIXES

    if not isinstance(
        result_data,
        dict,
    ):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for original_object_name, failure_data in (
        failed_objects.items()
    ):

        obj = bpy.data.objects.get(
            original_object_name
        )

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    original_object_name
                )
            )
            continue

        if obj.library is not None:
            continue

        fixed_data = {}

        # -----------------------------------------------------
        # Fix Object Name
        # -----------------------------------------------------

        if (
            isinstance(
                failure_data,
                dict,
            )
            and failure_data.get(
                "object_name"
            )
        ):
            old_object_name = obj.name

            (
                new_object_name,
                removed_prefix,
            ) = remove_invalid_prefix(
                old_object_name,
                prefixes=prefixes,
                strip_separators=strip_separators,
            )

            if new_object_name is None:
                issues.append(
                    (
                        "Could not rename object {!r}: removing "
                        "the prefix would leave an empty name."
                    ).format(
                        old_object_name
                    )
                )

            else:
                obj.name = (
                    new_object_name
                )

                fixed_data[
                    "object_name"
                ] = {
                    "old_name":
                        old_object_name,

                    "new_name":
                        obj.name,

                    "removed_prefix":
                        removed_prefix,
                }

        # -----------------------------------------------------
        # Fix Datablock Name
        # -----------------------------------------------------

        if (
            isinstance(
                failure_data,
                dict,
            )
            and failure_data.get(
                "datablock_name"
            )
        ):
            datablock = getattr(
                obj,
                "data",
                None,
            )

            if datablock is None:
                issues.append(
                    (
                        "Could not rename datablock for {!r}: "
                        "object has no datablock."
                    ).format(
                        obj.name
                    )
                )

            elif datablock.users > 1:
                issues.append(
                    (
                        "Skipped datablock {!r} on object {!r}: "
                        "datablock is shared by {} objects/users."
                    ).format(
                        datablock.name,
                        obj.name,
                        datablock.users,
                    )
                )

            else:
                old_datablock_name = (
                    datablock.name
                )

                (
                    new_datablock_name,
                    removed_prefix,
                ) = remove_invalid_prefix(
                    old_datablock_name,
                    prefixes=prefixes,
                    strip_separators=strip_separators,
                )

                if new_datablock_name is None:
                    issues.append(
                        (
                            "Could not rename datablock {!r}: "
                            "removing the prefix would leave "
                            "an empty name."
                        ).format(
                            old_datablock_name
                        )
                    )

                else:
                    datablock.name = (
                        new_datablock_name
                    )

                    fixed_data[
                        "datablock_name"
                    ] = {
                        "old_name":
                            old_datablock_name,

                        "new_name":
                            datablock.name,

                        "removed_prefix":
                            removed_prefix,
                    }

        if fixed_data:
            fixed_objects[
                original_object_name
            ] = fixed_data

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
