# Python imports
import os

# Blender imports
import bpy
import bpy.utils.previews


# -------------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------------

_preview_collection = None


# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------

def register_icons():
    """
    Automatically loads all supported image files from:

        scriptronaut_qc/ui/icons/

    The filename without extension becomes the icon name.

    Example:

        select_invert.png

    becomes:

        get_icon_id("select_invert")
    """
    global _preview_collection

    if _preview_collection is not None:
        return

    _preview_collection = (
        bpy.utils.previews.new()
    )

    icon_directory = os.path.join(
        os.path.dirname(__file__),
        "ui",
        "icons",
    )

    if not os.path.isdir(
        icon_directory
    ):
        print(
            "Scriptronaut QC icon folder not found: {}".format(
                icon_directory
            )
        )
        return

    supported_extensions = {
        ".png"
    }

    loaded_count = 0

    for filename in sorted(
        os.listdir(
            icon_directory
        )
    ):
        filepath = os.path.join(
            icon_directory,
            filename,
        )

        if not os.path.isfile(
            filepath
        ):
            continue

        icon_name, extension = os.path.splitext(
            filename
        )

        extension = extension.lower()

        if extension not in supported_extensions:
            continue

        # Avoid duplicate icon names from files such as:
        if icon_name in _preview_collection:
            print(
                (
                    "Scriptronaut QC duplicate icon name "
                    "ignored: {}"
                ).format(
                    icon_name
                )
            )
            continue

        try:
            _preview_collection.load(
                icon_name,
                filepath,
                "IMAGE",
            )

            loaded_count += 1

        except Exception as error:
            print(
                (
                    "Could not load Scriptronaut QC icon "
                    "'{}': {}"
                ).format(
                    filepath,
                    error,
                )
            )

    print(
        "Scriptronaut QC loaded {} custom icon{}.".format(
            loaded_count,
            ""
            if loaded_count == 1
            else "s",
        )
    )


def unregister_icons():
    """
    Removes the custom icon preview collection.
    """
    global _preview_collection

    if _preview_collection is None:
        return

    bpy.utils.previews.remove(
        _preview_collection
    )

    _preview_collection = None


# -------------------------------------------------------------------------
# Access
# -------------------------------------------------------------------------

def get_icon_id(
        icon_name,
        fallback=0,
    ):
    """
    Returns the integer icon_value for a custom icon.

    Args:
        icon_name (str):
            Filename without extension.

            Example:
                select_invert

        fallback (int):
            Returned when the icon cannot be found.

    Returns:
        int
    """
    if _preview_collection is None:
        return fallback

    preview = _preview_collection.get(
        icon_name
    )

    if preview is None:
        return fallback

    return preview.icon_id


def has_icon(
        icon_name,
    ):
    """
    Returns True when a custom icon has been loaded.
    """
    if _preview_collection is None:
        return False

    return (
        _preview_collection.get(
            icon_name
        )
        is not None
    )


def get_icon_names():
    """
    Returns all currently loaded custom icon names.
    """
    if _preview_collection is None:
        return []

    return sorted(
        _preview_collection.keys()
    )
