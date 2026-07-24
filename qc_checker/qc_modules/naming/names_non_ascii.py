# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "Name is ASCII"
DESCRIPTION = (
    "Checks if Object's Name is ASCII"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_objects_with_unicode_characters()
    issues = []

    for object_name, data in failed_objects.items():
        character_info = ", ".join(
            "{} ({})".format(
                item["character"],
                item["codepoint"],
            )
            for item in data["unicode_details"]
        )

        issues.append(
            "Failed object: {!r} - Contains Unicode "
            "character(s): {}".format(
                object_name,
                character_info,
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_unicode_characters(objects=None):
    """
    Finds objects whose names contain non-ASCII / Unicode characters.

    ASCII characters 0-127 are considered valid.

    Examples that fail:
        "Café"
        "Crâne"
        "椅子"
        "Character_😀"
        "Prop–Chair"   # en dash instead of normal hyphen

    Examples that pass:
        "Cafe"
        "Character_Body"
        "Prop-Chair"
        "Cube.001"

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Café": {
                "unicode_characters": ["é"],
                "unicode_details": [
                    {
                        "character": "é",
                        "codepoint": "U+00E9",
                    }
                ],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        unicode_characters = []
        unicode_details = []

        for character in obj.name:
            # ASCII range is 0-127.
            if ord(character) <= 127:
                continue

            if character not in unicode_characters:
                unicode_characters.append(character)

                unicode_details.append({
                    "character": character,
                    "codepoint": "U+{:04X}".format(
                        ord(character)
                    ),
                })

        if not unicode_characters:
            continue

        failed_objects[obj.name] = {
            "unicode_characters": unicode_characters,
            "unicode_details": unicode_details,
        }

    return failed_objects
