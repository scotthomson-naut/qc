# Python imports
import re

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Valid Names"
DESCRIPTION = (
    "Checks that Object and Datablock names contain only supported "
    "characters."
)
WHY = (
    "Special characters can corrupt file paths, break code "
    "parsing, and violate external software naming rules."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

VALID_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.\- ]")


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks object names and datablock names for invalid characters.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_invalid_characters()
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
                    "Failed object: {} - Object name {!r} contains "
                    "special character(s): {}"
                ).format(
                    object_name,
                    object_name_data["name"],
                    " ".join(
                        object_name_data[
                            "invalid_characters"
                        ]
                    ),
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
                    "Failed object: {} - Datablock name {!r} contains "
                    "special character(s): {}"
                ).format(
                    object_name,
                    datablock_name_data["name"],
                    " ".join(
                        datablock_name_data[
                            "invalid_characters"
                        ]
                    ),
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_invalid_characters(
        objects=None,
    ):
    """
    Finds objects whose object name or datablock name contains
    unsupported characters.

    Allowed characters:
        A-Z
        a-z
        0-9
        underscore _
        hyphen -
        period .
        space

    Examples that fail:
        Object:
            Fried_Ham_$%
            Me@TheBusStop
            Chair#01

        Datablock:
            Object: Chair
            Mesh:   Chair$Mesh

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

    Returns:
        dict:
        {
            "Chair": {
                "object_name": {
                    "name": "Chair@01",
                    "invalid_characters": ["@"],
                },

                "datablock_name": {
                    "name": "Chair$Mesh",
                    "invalid_characters": ["$"],
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
            get_invalid_character_data(
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
                get_invalid_character_data(
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
            result[
                "object_name"
            ] = object_name_result

        if datablock_name_result is not None:
            result[
                "datablock_name"
            ] = datablock_name_result

        failed_objects[
            obj.name
        ] = result

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_invalid_character_data(
        name,
    ):
    """
    Checks one name for unsupported characters.

    Args:
        name (str):
            Name to inspect.

    Returns:
        dict | None:
            None when the name contains only valid characters.

            Otherwise:
            {
                "name": "Chair@$",
                "invalid_characters": [
                    "@",
                    "$",
                ],
            }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    invalid_characters = list(
        dict.fromkeys(
            VALID_NAME_PATTERN.findall(
                name
            )
        )
    )

    if not invalid_characters:
        return None

    return {
        "name": name,
        "invalid_characters":
            invalid_characters,
    }
