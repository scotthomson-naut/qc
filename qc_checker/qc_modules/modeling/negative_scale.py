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
    failed_objects = get_objects_with_negative_scale()
    issues = []

    for object_name, data in failed_objects.items():
        scale = data["scale"]

        issues.append(
            "Failed object: {} - Negative scale on {} "
            "(Scale: {:.4f}, {:.4f}, {:.4f})".format(
                object_name,
                ", ".join(data["negative_axes"]),
                scale[0],
                scale[1],
                scale[2],
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
    fixed = fix_objects_with_negative_scale(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_negative_scale(objects=None):
    """
    Finds mesh objects with one or more negative scale values.

    Examples:
        Scale (-1, 1, 1)   -> FAIL
        Scale (1, -2, 1)   -> FAIL
        Scale (-1, -1, -1) -> FAIL
        Scale (1, 1, 1)    -> PASS

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "scale": (-1.0, 1.0, 1.0),
                "negative_axes": ["X"],
            },
            "Sphere": {
                "scale": (1.0, -1.0, -2.0),
                "negative_axes": ["Y", "Z"],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    axis_names = ("X", "Y", "Z")

    for obj in objects:

        if obj.type != "MESH":
            continue

        scale = tuple(obj.scale)

        negative_axes = [
            axis_name
            for axis_name, value in zip(axis_names, scale)
            if value < 0.0
        ]

        if not negative_axes:
            continue

        failed_objects[obj.name] = {
            "scale": scale,
            "negative_axes": negative_axes,
        }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_with_negative_scale(result_data=None):
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
                    "previous_scale": (-1.0, 2.0, 1.0),
                    "scale": (1.0, 2.0, 1.0),
                    "negative_axes": ["X"],
                }
            },
            "issues": [...]
        }
    """
    failed_objects = result_data.get("failed_objects", {})
    fixed_objects = {}
    issues = []
    axis_names = ("X", "Y", "Z")

    for object_name, object_data in failed_objects.items():
        obj = bpy.data.objects.get(object_name)

        if obj.type != "MESH":
            continue
        previous_scale = tuple(obj.scale)

        negative_axes = [
            axis_name
            for axis_name, value in zip(
                axis_names,
                previous_scale,
            )
            if value < -TOLERANCE
        ]

        if not negative_axes:
            continue

        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(
                    obj.name
                )
            )
            continue

        try:

            # Make mesh data unique before modifying geometry.
            if obj.data.users > 1:
                obj.data = obj.data.copy()

            # -----------------------------------------------------
            # Build a sign-only scale matrix
            # -----------------------------------------------------
            #
            # Example:
            # (-2, 3, -4)
            #
            # We only bake:
            # (-1, 1, -1)
            #
            # The remaining object scale becomes:
            # (2, 3, 4)
            #

            sign_x = -1.0 if obj.scale.x < 0.0 else 1.0
            sign_y = -1.0 if obj.scale.y < 0.0 else 1.0
            sign_z = -1.0 if obj.scale.z < 0.0 else 1.0

            sign_matrix = Matrix.Diagonal((
                sign_x,
                sign_y,
                sign_z,
                1.0,
            ))

            # Bake the mirror into mesh geometry.
            obj.data.transform(
                sign_matrix
            )

            # Make object scale positive.
            obj.scale = (
                abs(obj.scale.x),
                abs(obj.scale.y),
                abs(obj.scale.z),
            )

            # -----------------------------------------------------
            # Fix face winding / normals when handedness flips
            # -----------------------------------------------------
            #
            # An odd number of negative axes reverses the mesh
            # orientation.
            #

            negative_axis_count = len(
                negative_axes
            )

            if negative_axis_count % 2 == 1:

                for polygon in obj.data.polygons:
                    polygon.flip()

            obj.data.update()

            fixed_objects[obj.name] = {
                "previous_scale":
                    previous_scale,

                "scale":
                    tuple(obj.scale),

                "negative_axes":
                    negative_axes,
            }

        except Exception as error:

            issues.append(
                "Could not bake negative scale on {}: {}".format(
                    obj.name,
                    error,
                )
            )

    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
