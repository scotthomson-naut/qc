# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Name has no Trailing Spaces"
DESCRIPTION = (
    "Checks if Object's Name has Trailing Spaces"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue
    """
    failed_objects = get_objects_with_trailing_spaces()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {!r} - Contains {} trailing space(s)".format(
                object_name,
                data["trailing_space_count"],
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
    fixed = fix_objects_with_trailing_spaces(result_data)

    return {
        "issues": [],
        "fixed_objects": fixed,
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_trailing_spaces(objects=None):
    """
    Finds objects whose names contain one or more trailing spaces.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Character_Body ": {
                "trimmed_name": "Character_Body",
                "trailing_space_count": 1,
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        object_name = obj.name

        trimmed_name = object_name.rstrip(" ")

        if object_name == trimmed_name:
            continue

        trailing_space_count = (
            len(object_name) - len(trimmed_name)
        )

        failed_objects[object_name] = {
            "trimmed_name": trimmed_name,
            "trailing_space_count": trailing_space_count,
        }

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_objects_with_trailing_spaces(result_data):
    """
    Removes trailing spaces from failed object names.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for old_name, data in failed_objects.items():
        obj = bpy.data.objects.get(old_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {!r}".format(old_name)
            )
            continue

        new_name = obj.name.rstrip(" ")

        if not new_name:
            issues.append(
                "Cannot rename {!r}: name would be empty.".format(
                    old_name
                )
            )
            continue

        obj.name = new_name

        fixed_objects[old_name] = {
            "new_name": obj.name,
        }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }