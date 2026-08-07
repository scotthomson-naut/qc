# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Object/Data Name Match"
DESCRIPTION = (
    "Checks that single-user mesh datablock names match their object names. "
    "Like BoxRed -> Cube.001 "
    "Shared mesh datablocks are allowed and ignored. "
    "An object holds position and rotation data, while its internal datablock "
    "holds the actual geometry or properties. When they mismatch, "
    "identifying assets becomes difficult."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks whether mesh object names match their mesh datablock names.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_mismatched_mesh_names()
    )

    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Mesh datablock is named '{}'".format(
                object_name,
                data["mesh_name"],
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
    return fix_objects_with_mismatched_mesh_names(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_mismatched_mesh_names(
        objects=None,
    ):
    """
    Finds single-user mesh objects whose object name does not match
    their mesh datablock name.

    Shared mesh datablocks are intentionally ignored because one
    datablock cannot match multiple differently named objects.
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        # Shared mesh datablocks are valid and cannot necessarily
        # match every object name.
        if obj.data.users > 1:
            continue

        if obj.name == obj.data.name:
            continue

        failed_objects[obj.name] = {
            "object_name": obj.name,
            "mesh_name": obj.data.name,
            "mesh_users": obj.data.users,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_objects_with_mismatched_mesh_names(
        result_data=None,
    ):
    """
    Renames single-user mesh datablocks to match their object names.

    Shared datablocks are skipped rather than made single-user.
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(failed_objects, dict):
        failed_objects = {}

    fixed_objects = {}
    issues = []

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

        if obj.type != "MESH" or obj.data is None:
            continue

        if obj.data.users > 1:
            issues.append(
                'Skipped "{}": mesh datablock "{}" is shared by {} objects.'.format(
                    obj.name,
                    obj.data.name,
                    obj.data.users,
                )
            )
            continue

        try:
            old_mesh_name = obj.data.name
            obj.data.name = obj.name

            fixed_objects[obj.name] = {
                "fixed": True,
                "previous_mesh_name": old_mesh_name,
                "mesh_name": obj.data.name,
            }

        except Exception as error:
            issues.append(
                "Could not fix {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
