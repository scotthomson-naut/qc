# Standard python imports

# Blender imports
import bpy

# Company imports

# Constants
TOLERANCE=1e-6

# Meta data
LABEL = "Location Applied"
DESCRIPTION = (
    "Checks if Object's Location is Applied"
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
    Moves normal Location values into Delta Location.

    This preserves:
        - Geometry world position
        - Origin/pivot world position
        - Rotation
        - Scale

    This is not equivalent to Object > Apply > Location.
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                'Object "{}" no longer exists.'.format(
                    object_name
                )
            )
            continue

        if obj.type != "MESH":
            continue

        if obj.library is not None:
            issues.append(
                "Skipped linked object: {}".format(
                    obj.name
                )
            )
            continue

        # Use blender's function
        bpy.ops.object.transforms_to_deltas(mode='LOC')


    bpy.context.view_layer.update()

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
