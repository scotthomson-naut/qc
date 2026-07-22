# Standard python imports
from mathutils import Matrix

# Blender imports
import bpy

# Company imports


# Constants
TOLERANCE=1e-6

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_unapplied_location()

    issues = []

    for object_name, data in failed_objects.items():
        location = data["location"]
        issues.append(
            "Failed object: {} - Location is not applied: "
            "({:.4f}, {:.4f}, {:.4f})".format(
                object_name,
                location[0],
                location[1],
                location[2],
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
    fixed = fix_objects_with_unapplied_location(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_unapplied_location(objects=None):
    """
    Finds mesh objects whose location is not zero.

    An object passes when:
        Location = (0, 0, 0)

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.


    Returns:
        dict:
        {
            "Cube": {
                "location": (1.0, 0.0, 2.5),
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        if obj.type != "MESH":
            continue

        location = tuple(obj.location)

        has_unapplied_location = any(
            abs(value) > TOLERANCE
            for value in location
        )

        if not has_unapplied_location:
            continue

        failed_objects[obj.name] = {
            "location": location,
        }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_with_unapplied_location(result_data=None):
    """
    Applies location to mesh objects.

    The object's current location is baked into its mesh data,
    then the object location is reset to (0, 0, 0).

    Rotation and scale are preserved.

    Args:
        result_data (dict):
            Result returned by main()

    Returns:
        dict:
        {
            "fixed_objects": {
                "Cube": {
                    "previous_location": (2.0, 0.0, 5.0),
                    "location": (0.0, 0.0, 0.0),
                }
            },
            "issues": [...]
        }
    """
    failed_objects = result_data.get("failed_objects", {})
    fixed_objects = {}
    issues = []

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj.type != "MESH":
            continue

        # ---------------------------------------------------------
        # Check whether location needs applying
        # ---------------------------------------------------------

        if not any(
            abs(value) > TOLERANCE
            for value in obj.location
        ):
            continue

        # ---------------------------------------------------------
        # Skip linked objects
        # ---------------------------------------------------------

        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(
                    obj.name
                )
            )
            continue

        try:

            # -----------------------------------------------------
            # Make shared mesh data unique
            # -----------------------------------------------------

            if obj.data.users > 1:
                obj.data = obj.data.copy()

            previous_location = tuple(obj.location)

            # Save exact world-space transform before changing
            # the object's location.
            old_world_matrix = obj.matrix_world.copy()

            # -----------------------------------------------------
            # Zero object location
            # -----------------------------------------------------

            obj.location = (
                0.0,
                0.0,
                0.0,
            )

            bpy.context.view_layer.update()

            # World matrix after zeroing location.
            new_world_matrix = obj.matrix_world.copy()

            # -----------------------------------------------------
            # Calculate geometry correction
            # -----------------------------------------------------

            # Find the local-space transform that makes:
            #
            # new_world_matrix @ corrected_geometry
            #
            # equal:
            #
            # old_world_matrix @ original_geometry
            #
            geometry_transform = (
                new_world_matrix.inverted_safe()
                @ old_world_matrix
            )

            # Bake that difference into the mesh.
            obj.data.transform(
                geometry_transform
            )

            obj.data.update()

            fixed_objects[obj.name] = {
                "previous_location":
                    previous_location,

                "location":
                    tuple(obj.location),
            }

        except Exception as error:

            issues.append(
                "Could not apply location to {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
