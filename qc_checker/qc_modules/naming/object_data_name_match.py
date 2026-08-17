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

        # Directly linked library objects are read-only and are
        # outside the scope of local naming QC.
        if obj.library is not None:
            continue
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
    Renames single-user datablocks to exactly match their object names.

    Uses Blender's ID.rename(..., mode="ALWAYS") collision handling.
    When the requested datablock name already exists, Blender renames
    the conflicting datablock and guarantees the current datablock gets
    the requested name.

    Shared datablocks remain untouched.
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

    # ---------------------------------------------------------
    # Resolve current objects first
    # ---------------------------------------------------------

    objects_to_fix = []

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

        if obj.library is not None:
            continue

        datablock = obj.data

        if datablock is None:
            continue

        if datablock.users > 1:
            issues.append(
                (
                    'Skipped "{}": datablock "{}" '
                    "is shared by {} users."
                ).format(
                    obj.name,
                    datablock.name,
                    datablock.users,
                )
            )
            continue

        if datablock.name == obj.name:
            continue

        objects_to_fix.append(
            obj
        )

    # ---------------------------------------------------------
    # Rename
    # ---------------------------------------------------------

    for obj in objects_to_fix:

        datablock = obj.data

        # Another rename earlier in the sequence may already
        # have caused this datablock to receive its correct name.
        if datablock.name == obj.name:
            continue

        old_datablock_name = (
            datablock.name
        )

        try:

            # Blender handles the collision for us.
            #
            # ALWAYS means:
            #     This datablock MUST receive obj.name.
            #     If another datablock owns that name,
            #     Blender renames the other datablock.
            rename_result = datablock.rename(
                obj.name,
                mode="ALWAYS",
            )

        except Exception as error:

            issues.append(
                (
                    'Could not rename datablock for "{}": {}'
                ).format(
                    obj.name,
                    error,
                )
            )

            continue

        # -----------------------------------------------------
        # Verify exact result
        # -----------------------------------------------------

        if datablock.name != obj.name:

            issues.append(
                (
                    'Could not assign exact datablock name "{}" '
                    'to object "{}". Blender assigned "{}".'
                ).format(
                    obj.name,
                    obj.name,
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
                old_datablock_name,

            "datablock_name":
                datablock.name,

            "rename_result":
                str(
                    rename_result
                ),
        }

    bpy.context.view_layer.update()

    return {
        "fixed_objects":
            fixed_objects,

        "issues":
            issues,
    }
