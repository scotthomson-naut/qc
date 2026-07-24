# Standard python imports

# Blender imports
import bpy

# Company imports

# Constants
CASE_SENSITIVE = False

# Meta data
LABEL = "Name Has Valid Prefix"
DESCRIPTION = (
    "Checks if Object's Name dhas a valid Prefix"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    """
    failed_objects = get_objects_with_invalid_prefixes()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Uses invalid prefix '{}'".format(
                object_name,
                data["prefix"],
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
    fixed = fix_invalid_prefixes_from_objects(result_data)

    return fixed


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_invalid_prefixes(
        objects=None,
        prefixes=None
    ):
    """
    Finds objects whose names start with temporary/debug/test prefixes.

    Default prefixes:
        tmp
        temp
        debug
        test

    Examples that fail:
        tmp_Cube
        temp_mesh
        debugCharacter
        test_object
        TMP_Render
        TestCube

    Examples that pass:
        Character_Body
        Contest_Object
        AttemptMesh

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        prefixes (iterable[str] | None):
            Prefixes to check.
            Defaults to ("tmp", "temp", "debug", "test").

    Returns:
        dict:
        {
            "tmp_Cube": {
                "prefix": "tmp",
            },
            "DEBUG_Mesh": {
                "prefix": "debug",
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    if prefixes is None:
        prefixes = (
            "tmp_",
            "temp_",
            "debug_",
            "test_",
        )

    failed_objects = {}

    for obj in objects:

        object_name = obj.name

        if CASE_SENSITIVE:
            compare_name = object_name
            compare_prefixes = prefixes
        else:
            compare_name = object_name.lower()
            compare_prefixes = [
                prefix.lower()
                for prefix in prefixes
            ]

        for prefix in compare_prefixes:
            if not compare_name.startswith(prefix):
                continue

            failed_objects[object_name] = {
                "prefix": prefix,
            }

            break

    return failed_objects


# -------------------------
# Fix
# -------------------------

def fix_invalid_prefixes_from_objects(
        result_data=None,
        prefixes=None,
        strip_separators=True,
    ):
    """
    Removes invalid prefixes from object names.

    Default invalid prefixes:
        tmp
        temp
        debug
        test

    Examples:
        tmp_Cube      -> Cube
        temp-Chair    -> Chair
        debugRig      -> Rig
        TEST_object   -> object

    Args:
        result_data (dict):
            Result returned by main()

        prefixes (iterable[str] | None):
            Invalid prefixes to remove.

        strip_separators (bool):
            If True, removes separators immediately following
            the invalid prefix, such as:
                _
                -
                .
                spaces

    Returns:
        dict:{}
    """
    if prefixes is None:
        prefixes = (
            "tmp",
            "temp",
            "debug",
            "test",
        )


    # Check longer prefixes first.
    # This prevents "temp" from accidentally being treated
    # as "tmp" in custom prefix sets.
    prefixes = sorted(
        prefixes,
        key=len,
        reverse=True,
    )

    failed_objects = result_data.get("failed_objects", {})
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

        old_name = obj.name

        compare_name = (
            old_name
            if CASE_SENSITIVE
            else old_name.lower()
        )

        matched_prefix = None

        for prefix in prefixes:

            compare_prefix = (
                prefix
                if CASE_SENSITIVE
                else prefix.lower()
            )

            if compare_name.startswith(compare_prefix):
                matched_prefix = prefix
                break

        if matched_prefix is None:
            continue

        # Remove exactly the number of characters
        # contained in the matched prefix.
        new_name = old_name[len(matched_prefix):]

        if strip_separators:
            new_name = new_name.lstrip(
                " _-."
            )

        if not new_name:
            issues.append(
                "Could not rename {!r}: removing prefix "
                "would leave an empty name.".format(
                    old_name
                )
            )
            continue

        obj.name = new_name

        fixed_objects[old_name] = {
            "old_name": old_name,
            "new_name": obj.name,
            "removed_prefix": matched_prefix,
        }

    return {
        "fixed_objects": fixed_objects,
        "issues": issues,
    }
