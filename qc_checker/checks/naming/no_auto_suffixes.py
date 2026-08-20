# Python imports
import re

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "No Auto Suffixes"
DESCRIPTION = (
    "Checks if Object or Datablock names use Blender's automatic numeric "
    "suffixes such as .001, .002, etc."
)
WHY = (
    "These names usually indicate copied or duplicated data that has "
    "not been given a deliberate production name."
)


# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------

AUTO_INCREMENT_PATTERN = re.compile(r"^(.*)\.(\d{3})$")


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Detects Blender auto-incremented object and datablock names.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = get_objects_with_auto_increment_names()

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
                    "Failed object: {} - Object name {!r} uses "
                    "Blender auto suffix .{:03d}"
                ).format(
                    object_name,
                    object_name_data["name"],
                    object_name_data["suffix"],
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
                    "Failed object: {} - Datablock name {!r} uses "
                    "Blender auto suffix .{:03d}"
                ).format(
                    object_name,
                    datablock_name_data["name"],
                    datablock_name_data["suffix"],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_auto_increment_names(
        objects=None,
        exclude_types=None,
    ):
    """
    Finds objects whose object name or datablock name ends with
    Blender's automatic numeric suffix.

    Examples:
        Object:
            Cube.001
            Chair.004
            Character.015

        Datablock:
            Object:      Chair
            Mesh:        Cube.001

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all Blender objects.

        exclude_types (set[str] | None):
            Object types to ignore.

            Example:
                {
                    "CAMERA",
                    "LIGHT",
                }

    Returns:
        dict:
        {
            "Chair.001": {
                "object_name": {
                    "name": "Chair.001",
                    "base_name": "Chair",
                    "suffix": 1,
                },

                "datablock_name": {
                    "name": "ChairMesh.002",
                    "base_name": "ChairMesh",
                    "suffix": 2,
                },
            }
        }
    """
    if objects is None:
        objects = bpy.data.objects

    if exclude_types is None:
        exclude_types = set()

    failed_objects = {}

    for obj in objects:

        # Directly linked library objects are read-only and are
        # outside the scope of local naming QC.
        if obj.library is not None:
            continue

        if obj.type in exclude_types:
            continue

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_result = (
            get_auto_increment_data(
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
                get_auto_increment_data(
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

def get_auto_increment_data(
        name,
    ):
    """
    Checks one name for Blender's .### auto-increment suffix.

    Args:
        name (str):
            Name to inspect.

    Returns:
        dict | None:
            None when the name does not contain an auto suffix.

            Otherwise:
            {
                "name": "Cube.001",
                "base_name": "Cube",
                "suffix": 1,
            }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    match = AUTO_INCREMENT_PATTERN.match(
        name
    )

    if not match:
        return None

    return {
        "name": name,
        "base_name": match.group(1),
        "suffix": int(
            match.group(2)
        ),
    }
