# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Mesh Geometry Valid"
DESCRIPTION = (
    "Checks if Mesh datablocks contain invalid geometry, per "
    "Blender's own mesh validation"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_invalid_geometry()

    return {
        "issues": [
            "Failed object: {} - Datablock '{}' contains invalid geometry".format(
                object_name,
                data["datablock_name"],
            )
            for object_name, data in failed_objects.items()
        ],
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Args:
        result_data (list[str]): List of object names.
    Returns:
        dict: Issues
    """
    # Call Function
    fix_result = fix_invalid_geometry(result_data)

    return fix_result

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_invalid_geometry(objects=None):
    """
    Finds Mesh objects whose datablock contains invalid geometry, per
    Blender's own mesh validation.

    Note:
        Mesh.validate() corrects problems in place as a side effect of
        checking them. To keep this a read-only check, validation is
        run on a temporary copy of the datablock, which is discarded
        immediately after. The real datablock is only ever touched by
        fix_invalid_geometry(), below.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "datablock_name": "Cube",
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        if not isinstance(obj.data, bpy.types.Mesh):
            continue

        if mesh_datablock_has_invalid_geometry(obj.data):
            failed_objects[obj.name] = {
                "datablock_name": obj.data.name,
            }

    return failed_objects


def mesh_datablock_has_invalid_geometry(mesh_datablock):
    """
    Checks whether a mesh datablock has invalid geometry, without
    mutating it.

    Args:
        mesh_datablock (bpy.types.Mesh):
            Mesh datablock.

    Returns:
        bool:
            True when Blender's validation reports invalid geometry.
    """
    temp_mesh = mesh_datablock.copy()

    is_invalid = temp_mesh.validate(
        verbose=False,
        clean_customdata=True,
    )

    bpy.data.meshes.remove(temp_mesh)

    return is_invalid


# -------------------------
# Fix
# -------------------------

def fix_invalid_geometry(result_data):
    """
    Fixes invalid mesh geometry using Blender's own validation.

    Note:
        Unlike the read-only check above, this calls validate()
        directly on the real datablock, which is what actually
        performs the correction. This is a destructive fix: invalid
        data is removed, not repaired. See mesh_invalid_geometry.py
        conversation notes - validate() cannot reconstruct what a
        corrupted face was supposed to look like, it can only drop
        what it can't make sense of.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        if obj.data is None or not isinstance(obj.data, bpy.types.Mesh):
            issues.append(
                "Skipped '{}', datablock changed since check ran.".format(
                    object_name
                )
            )
            continue

        was_invalid = obj.data.validate(
            verbose=False,
            clean_customdata=True,
        )

        if was_invalid:
            fixed_objects[object_name] = {
                "fixed_geometry": True,
            }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }