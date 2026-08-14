# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Object/Data Name Match"
DESCRIPTION = (
    "Checks that single-user datablock names match their object "
    "names, across every object type (Mesh, Camera, Curve, "
    "Armature, Light, etc). Like BoxRed -> Cube.001 "
    "Shared datablocks are allowed and ignored. "
)
WHY = (
    "An object holds position and rotation data, while its internal datablock "
    "holds the actual geometry or properties. When they mismatch, "
    "identifying assets becomes difficult."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks whether object names match their datablock names, across
    every object type.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_mismatched_data_names()
    )

    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Datablock is named '{}'".format(
                object_name,
                data["datablock_name"],
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fixes all objects reported by main().
    """
    return fix_objects_with_mismatched_data_names(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_mismatched_data_names(
        objects=None,
    ):
    """
    Finds single-user objects (of any type) whose object name does
    not match their datablock name.

    Note:
        Unlike the original version of this check, this is no longer
        restricted to obj.type == "MESH" - every object type with a
        datablock (Camera, Curve, Armature, Light, Lattice, Metaball,
        Speaker, GreasePencil, etc.) is checked the same way, since
        every datablock type shares the same .name and .users
        properties (inherited from Blender's base ID type), and the
        comparison logic and severity don't actually differ by
        object type. Empty objects (obj.data is always None) are
        naturally skipped, same as before.

        Shared datablocks are intentionally ignored because one
        datablock cannot match multiple differently named objects.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "object_name": "Cube",
                "datablock_name": "Mesh.002",
                "datablock_users": 1,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.data is None:
            continue

        # Shared datablocks are valid and cannot necessarily match
        # every object name.
        if obj.data.users > 1:
            continue

        if obj.name == obj.data.name:
            continue

        failed_objects[obj.name] = {
            "object_name": obj.name,
            "datablock_name": obj.data.name,
            "datablock_users": obj.data.users,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_with_mismatched_data_names(
        result_data=None,
    ):
    """
    Renames single-user datablocks to match their object names.

    Uses a two-pass rename so datablock-name swaps/cycles do not
    cause Blender to generate automatic numeric suffixes.

    Example:

        Object             Data
        window.001   ->     window.003
        window.002   ->     window.001
        window.003   ->     window.004
        window.004   ->     window.002

    Pass 1:
        All affected datablocks receive temporary unique names.

    Pass 2:
        Each datablock is renamed to its object's final name.

    Shared datablocks are skipped rather than made single-user.

    Returns:
        dict
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

    if not isinstance(
        failed_objects,
        dict,
    ):
        failed_objects = {}

    fixed_objects = {}
    issues = []

    rename_items = []

    # ---------------------------------------------------------
    # Gather objects that are still valid and safe to rename
    # ---------------------------------------------------------

    for object_name in failed_objects:

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        datablock = obj.data

        if datablock is None:
            continue

        if datablock.users > 1:
            issues.append(
                (
                    'Skipped "{}": datablock "{}" '
                    "is shared by {} objects."
                ).format(
                    obj.name,
                    datablock.name,
                    datablock.users,
                )
            )
            continue

        # Already fixed since the QC result was generated.
        if datablock.name == obj.name:
            continue

        rename_items.append({
            "object":
                obj,

            "datablock":
                datablock,

            "old_name":
                datablock.name,

            "target_name":
                obj.name,
        })

    if not rename_items:
        return {
            "fixed_objects": {},
            "issues": issues,
        }

    # ---------------------------------------------------------
    # Pass 1
    #
    # Move every affected datablock out of the way first.
    # This breaks rename cycles such as:
    #
    # A -> B
    # B -> C
    # C -> A
    # ---------------------------------------------------------

    for index, item in enumerate(
        rename_items
    ):

        datablock = item[
            "datablock"
        ]

        temporary_name = (
            "__SCRIPTRONAUT_QC_TEMP__{:06d}__"
        ).format(
            index
        )

        try:
            datablock.name = (
                temporary_name
            )

            item[
                "temporary_name"
            ] = datablock.name

        except Exception as error:

            item[
                "temporary_failed"
            ] = True

            issues.append(
                (
                    'Could not temporarily rename datablock '
                    'for object "{}": {}'
                ).format(
                    item[
                        "object"
                    ].name,
                    error,
                )
            )

    # ---------------------------------------------------------
    # Pass 2
    #
    # All original conflicting names are now free.
    # Assign the final names.
    # ---------------------------------------------------------

    for item in rename_items:

        if item.get(
            "temporary_failed",
            False,
        ):
            continue

        obj = item[
            "object"
        ]

        datablock = item[
            "datablock"
        ]

        old_name = item[
            "old_name"
        ]

        target_name = item[
            "target_name"
        ]

        try:
            datablock.name = (
                target_name
            )

            # -------------------------------------------------
            # Verify Blender actually accepted the exact name
            # -------------------------------------------------

            if datablock.name != target_name:

                issues.append(
                    (
                        'Could not set datablock for "{}" '
                        'to exact name "{}". Blender assigned '
                        '"{}" instead.'
                    ).format(
                        obj.name,
                        target_name,
                        datablock.name,
                    )
                )

                continue

            fixed_objects[
                obj.name
            ] = {
                "fixed":
                    True,

                "previous_datablock_name":
                    old_name,

                "datablock_name":
                    datablock.name,
            }

        except Exception as error:

            issues.append(
                (
                    'Could not rename datablock for '
                    'object "{}": {}'
                ).format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }
