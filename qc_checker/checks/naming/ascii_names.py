# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "ASCII Names"
DESCRIPTION = (
    "Checks that Object and Datablock names contain only ASCII characters. "
    "Names such as 'Café', '椅子', or emoji."
)
WHY = (
    "Causes export, scripting, game-engine, and pipeline compatibility "
    "problems."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks object names and datablock names for non-ASCII characters.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_unicode_characters()
    )

    issues = []

    for object_name, data in failed_objects.items():

        # -----------------------------------------------------
        # Object name
        # -----------------------------------------------------

        object_name_data = data.get(
            "object_name",
        )

        if object_name_data:
            character_info = ", ".join(
                "{} ({})".format(
                    item["character"],
                    item["codepoint"],
                )
                for item in object_name_data[
                    "unicode_details"
                ]
            )

            issues.append(
                (
                    "Failed object: {!r} - Object name contains "
                    "Unicode character(s): {}"
                ).format(
                    object_name,
                    character_info,
                )
            )

        # -----------------------------------------------------
        # Datablock name
        # -----------------------------------------------------

        datablock_data = data.get(
            "datablock_name",
        )

        if datablock_data:
            character_info = ", ".join(
                "{} ({})".format(
                    item["character"],
                    item["codepoint"],
                )
                for item in datablock_data[
                    "unicode_details"
                ]
            )

            issues.append(
                (
                    "Failed object: {!r} - Datablock {!r} contains "
                    "Unicode character(s): {}"
                ).format(
                    object_name,
                    datablock_data[
                        "name"
                    ],
                    character_info,
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_unicode_characters(
        objects=None,
    ):
    """
    Finds objects whose object name or datablock name contains
    non-ASCII characters.

    ASCII characters 0-127 are considered valid.

    Examples that fail:
        Object:
            "Café"
            "Crâne"
            "椅子"
            "Character_😀"
            "Prop–Chair"

        Datablock:
            Object name: "Chair"
            Mesh name:   "ChaîrMesh"

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Chair": {
                "object_name": {
                    "name": "Chaîr",
                    "unicode_characters": ["î"],
                    "unicode_details": [
                        {
                            "character": "î",
                            "codepoint": "U+00EE",
                        }
                    ],
                },

                "datablock_name": {
                    "name": "Mësh",
                    "unicode_characters": ["ë"],
                    "unicode_details": [
                        {
                            "character": "ë",
                            "codepoint": "U+00EB",
                        }
                    ],
                },
            }
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
        object_result = get_unicode_name_data(
            obj.name
        )

        datablock_result = None
        data = getattr(
            obj,
            "data",
            None,
        )

        if (
            data is not None
            and hasattr(
                data,
                "name",
            )
        ):
            datablock_result = (
                get_unicode_name_data(
                    data.name
                )
            )

        # Neither object nor datablock failed.
        if (
            object_result is None
            and datablock_result is None
        ):
            continue

        result = {}

        if object_result is not None:
            result[
                "object_name"
            ] = object_result

        if datablock_result is not None:
            result[
                "datablock_name"
            ] = datablock_result

        failed_objects[
            obj.name
        ] = result

    return failed_objects


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_unicode_name_data(name):
    """
    Returns Unicode-character information for a name.

    Args:
        name (str):
            Name to inspect.

    Returns:
        dict | None:
            None when the name is valid ASCII.

            Otherwise:
            {
                "name": str,
                "unicode_characters": list[str],
                "unicode_details": list[dict],
            }
    """
    if not isinstance(
        name,
        str,
    ):
        return None

    unicode_characters = []
    unicode_details = []

    for character in name:
        # ASCII range is 0-127.
        if ord(character) <= 127:
            continue

        if character in unicode_characters:
            continue

        unicode_characters.append(
            character
        )

        unicode_details.append({
            "character": character,
            "codepoint": "U+{:04X}".format(
                ord(character)
            ),
        })

    if not unicode_characters:
        return None

    return {
        "name": name,
        "unicode_characters":
            unicode_characters,
        "unicode_details":
            unicode_details,
    }
