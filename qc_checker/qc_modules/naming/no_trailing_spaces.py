# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "No Trailing Spaces"
DESCRIPTION = (
    "Checks if Object or Datablock names contain trailing spaces."
)
WHY = (
    "Trailing spaces can cause invisible string mismatches in scripts, "
    "exports, file paths, and production tools."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks object names and datablock names for trailing spaces.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_trailing_spaces()
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
                    "Failed object: {!r} - Object name contains "
                    "{} trailing space(s)"
                ).format(
                    object_name,
                    object_name_data[
                        "trailing_space_count"
                    ],
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
                    "Failed object: {!r} - Datablock name {!r} "
                    "contains {} trailing space(s)"
                ).format(
                    object_name,
                    datablock_name_data[
                        "name"
                    ],
                    datablock_name_data[
                        "trailing_space_count"
                    ],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix trailing spaces in object and datablock names.
    """
    return fix_objects_with_trailing_spaces(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_trailing_spaces(
        objects=None,
    ):
    """
    Finds objects whose object name or datablock name contains
    one or more trailing spaces.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Character_Body ": {
                "object_name": {
                    "name": "Character_Body ",
                    "trimmed_name": "Character_Body",
                    "trailing_space_count": 1,
                },

                "datablock_name": {
                    "name": "CharacterMesh  ",
                    "trimmed_name": "CharacterMesh",
                    "trailing_space_count": 2,
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

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
            get_trailing_space_data(
                obj.name
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
                get_trailing_space_data(
                    datablock.name
                )
            )

        # -----------------------------------------------------
        # Passed both
        # -----------------------------------------------------

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

def get_trailing_space_data(
        name,
    ):
    """
    Checks one name for trailing spaces.

    Returns:
        dict | None:
            None when there are no trailing spaces.

            Otherwise:
            {
                "name": "Chair  ",
                "trimmed_name": "Chair",
                "trailing_space_count": 2,
            }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    trimmed_name = name.rstrip(
        " "
    )

    if name == trimmed_name:
        return None

    trailing_space_count = (
        len(name)
        - len(trimmed_name)
    )

    return {
        "name": name,
        "trimmed_name": trimmed_name,
        "trailing_space_count":
            trailing_space_count,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_with_trailing_spaces(
        result_data,
    ):
    """
    Removes trailing spaces from failed object and datablock names.

    Datablock names are only changed when the datablock is not shared.

    Returns:
        dict:
        {
            "issues": list[str],
            "fixed_objects": dict,
        }
    """
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

    for old_object_name, failure_data in (
        failed_objects.items()
    ):

        obj = bpy.data.objects.get(
            old_object_name
        )

        if obj is None:
            issues.append(
                "Object no longer exists: {!r}".format(
                    old_object_name
                )
            )
            continue

        if obj.library is not None:
            continue

        fixed_data = {}

        # -----------------------------------------------------
        # Fix object name
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
            current_name = obj.name

            new_name = current_name.rstrip(
                " "
            )

            if not new_name:
                issues.append(
                    (
                        "Cannot rename object {!r}: "
                        "name would be empty."
                    ).format(
                        current_name
                    )
                )

            else:
                obj.name = new_name

                fixed_data[
                    "object_name"
                ] = {
                    "old_name":
                        current_name,

                    "new_name":
                        obj.name,
                }

        # -----------------------------------------------------
        # Fix datablock name
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
                        "datablock is shared by {} users."
                    ).format(
                        datablock.name,
                        obj.name,
                        datablock.users,
                    )
                )

            else:
                current_datablock_name = (
                    datablock.name
                )

                new_datablock_name = (
                    current_datablock_name.rstrip(
                        " "
                    )
                )

                if not new_datablock_name:
                    issues.append(
                        (
                            "Cannot rename datablock {!r}: "
                            "name would be empty."
                        ).format(
                            current_datablock_name
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
                            current_datablock_name,

                        "new_name":
                            datablock.name,
                    }

        if fixed_data:
            fixed_objects[
                old_object_name
            ] = fixed_data

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }
