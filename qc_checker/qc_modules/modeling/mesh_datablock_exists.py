# Standard python imports
import os

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_invalid_mesh_datablocks()

    issues = []

    for object_name, data in failed_objects.items():
        for issue in data["issues"]:
            issues.append(
                "{} - {}".format(
                    object_name,
                    issue,
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Note:
        This check reports four issue types, but only "invalid_geometry"
        is safely auto-fixable. "missing_datablock",
        "invalid_datablock_type" and "missing_library_file" always
        require manual artist intervention and will still be present
        in failed_objects/issues after this runs. Re-run main() after
        calling this to see the updated pass/fail state.

    Args:
        result_data (list[str]): List of object names.
    Returns:
        dict: Issues
    """
    # Call Function
    fix_result = fix_invalid_mesh_datablocks(result_data)

    return fix_result

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_invalid_mesh_datablocks(
        objects=None,
    ):
    """
    Finds Mesh objects with missing, invalid or broken datablocks.

    Checks:
        1. Object has no mesh datablock assigned.
        2. Object's datablock is not a valid Mesh type.
        3. Datablock is linked from a library file that can no longer
           be found on disk.
        4. Datablock contains invalid geometry, per Blender's own
           mesh validation.

    Note:
        Checks 1 and 2 are defensive checks against file-level
        corruption (e.g. a mangled .blend, a bad import/export
        round-trip, or a tool writing to the low-level data
        structures directly). They are not reproducible through a
        live Blender/Python session for testing: Object.type is
        derived from Object.data, so setting obj.data = None simply
        converts the object to an EMPTY rather than leaving a MESH
        object with no data, and the Object.data setter itself
        rejects assigning a non-Mesh datablock to a MESH-type object.
        Do not spend time trying to script a repro for these two -
        cover them via code review instead, or by testing against a
        deliberately corrupted .blend file if one is available.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Mesh objects to inspect.
            Defaults to all mesh objects in the current scene.

    Returns:
        dict:
        {
            "CharacterMesh": {
                "missing_datablock": bool,
                "invalid_datablock_type": bool,
                "missing_library_file": bool,
                "invalid_geometry": bool,
                "issues": [...]
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        missing_datablock = False
        invalid_datablock_type = False
        missing_library_file = False
        invalid_geometry = False

        issues = []

        if obj.data is None:
            missing_datablock = True
            issues.append(
                "Object has no mesh datablock assigned."
            )

        elif not isinstance(obj.data, bpy.types.Mesh):
            invalid_datablock_type = True
            issues.append(
                "Datablock '{}' is not a valid Mesh type.".format(
                    obj.data
                )
            )

        else:
            mesh_datablock = obj.data

            if mesh_datablock_missing_library(mesh_datablock):
                missing_library_file = True
                issues.append(
                    "Datablock '{}' is linked to a missing library file: {}".format(
                        mesh_datablock.name,
                        mesh_datablock.library.filepath,
                    )
                )

            if mesh_datablock_has_invalid_geometry(mesh_datablock):
                invalid_geometry = True
                issues.append(
                    "Datablock '{}' contains invalid geometry.".format(
                        mesh_datablock.name
                    )
                )

        if (
            missing_datablock
            or invalid_datablock_type
            or missing_library_file
            or invalid_geometry
        ):
            failed_objects[obj.name] = {
                "missing_datablock": missing_datablock,
                "invalid_datablock_type": invalid_datablock_type,
                "missing_library_file": missing_library_file,
                "invalid_geometry": invalid_geometry,
                "issues": issues,
            }

    return failed_objects


def mesh_datablock_missing_library(mesh_datablock):
    """
    Checks whether a mesh datablock is linked and its source library
    file can no longer be found on disk.

    Args:
        mesh_datablock (bpy.types.Mesh):
            Mesh datablock.

    Returns:
        bool:
            True when the datablock is linked but the source file is
            missing.
    """
    library = mesh_datablock.library

    if library is None:
        return False

    filepath = bpy.path.abspath(library.filepath)

    return not os.path.exists(filepath)


def mesh_datablock_has_invalid_geometry(mesh_datablock):
    """
    Checks whether a mesh datablock has invalid geometry, using
    Blender's own mesh validation.

    Validation is run on a temporary copy of the datablock rather than
    the original, since Mesh.validate() corrects problems in place as
    a side effect. The copy is discarded immediately after checking,
    keeping this a read-only check.

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

def fix_invalid_mesh_datablocks(result_data):
    """
    Attempts to fix invalid mesh datablocks.

    Only invalid geometry is fixed automatically, since Blender's own
    validation is safe to apply directly to the datablock. Missing
    datablocks, invalid datablock types and missing library files all
    require artist intervention and are reported as issues instead of
    being auto-fixed.

    IMPORTANT: This is a partial fix. This check bundles four issue
    types under one module, and this function only resolves one of
    them. Objects with missing_datablock, invalid_datablock_type or
    missing_library_file will still fail after this runs - that is
    expected, not a bug. Their issues remain in failed_objects/issues
    on the next main() run so they stay visible for manual follow-up.

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

        if object_data.get("missing_datablock"):
            issues.append(
                "'{}' has no mesh datablock - assign or remove manually.".format(
                    object_name
                )
            )

        if object_data.get("invalid_datablock_type"):
            issues.append(
                "'{}' datablock type is invalid - needs manual review.".format(
                    object_name
                )
            )

        if object_data.get("missing_library_file"):
            issues.append(
                "'{}' is linked to a missing library file - relink manually.".format(
                    object_name
                )
            )

        if object_data.get("invalid_geometry"):

            # Recheck before fixing, mirroring the vertex-group fix pattern.
            if obj.data is None or not isinstance(obj.data, bpy.types.Mesh):
                issues.append(
                    "Skipped '{}' geometry fix, datablock changed.".format(
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