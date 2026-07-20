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
    Checks for missing or broken external image paths.
    """
    failed_images = get_images_with_missing_file_paths()

    return {
        "issues": [
            "Missing image: {} - {}".format(
                image_name,
                data["reason"],
            )
            for image_name, data in failed_images.items()
        ],
        "failed_images": failed_images,
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_images_with_missing_file_paths(images=None):
    """
    Finds Blender image datablocks whose external source files are
    missing, invalid, or have empty file paths.

    Checks:
        - FILE images
        - SEQUENCE images
        - MOVIE images
        - TILED/UDIM images

    Ignores:
        - Generated images
        - Viewer images
        - Render Result
        - Packed images, unless check_packed is enabled separately

    Args:
        images (iterable[bpy.types.Image] | None):
            Images to inspect.
            Defaults to all image datablocks in the Blender file.

    Returns:
        dict:
        {
            "ImageName": {
                "filepath": "//textures/diffuse.png",
                "absolute_path": "C:/project/textures/diffuse.png",
                "source": "FILE",
                "reason": "File does not exist",
            },
            ...
        }
    """
    if images is None:
        images = bpy.data.images

    failed_images = {}

    for image in images:
        source = image.source

        # Generated and internal images do not require external files.
        if source in {"GENERATED", "VIEWER"}:
            continue

        # Render Result is an internal Blender image.
        if image.type == "RENDER_RESULT":
            continue

        # Packed images do not depend on the external file being present.
        if image.packed_file is not None:
            continue

        filepath = image.filepath

        if not filepath:
            failed_images[image.name] = {
                "filepath": "",
                "absolute_path": "",
                "source": source,
                "reason": "Empty file path",
            }
            continue

        absolute_path = bpy.path.abspath(
            filepath,
            library=image.library,
        )

        if source == "TILED":
            missing_tiles = get_missing_udim_tiles(
                image=image,
                absolute_path=absolute_path,
            )

            if missing_tiles:
                failed_images[image.name] = {
                    "filepath": filepath,
                    "absolute_path": absolute_path,
                    "source": source,
                    "reason": "One or more UDIM tiles are missing",
                    "missing_tiles": missing_tiles,
                }

            continue

        if source == "SEQUENCE":
            if not sequence_path_exists(absolute_path):
                failed_images[image.name] = {
                    "filepath": filepath,
                    "absolute_path": absolute_path,
                    "source": source,
                    "reason": "Image sequence file does not exist",
                }

            continue

        if not os.path.isfile(absolute_path):
            failed_images[image.name] = {
                "filepath": filepath,
                "absolute_path": absolute_path,
                "source": source,
                "reason": "File does not exist",
            }

    return failed_images


def get_missing_udim_tiles(image, absolute_path):
    """
    Returns missing UDIM tile paths for a tiled image.

    Args:
        image (bpy.types.Image):
            Tiled Blender image datablock.

        absolute_path (str):
            Resolved image filepath containing a UDIM token or tile number.

    Returns:
        list[str]: Missing UDIM tile paths.
    """
    missing_tiles = []

    for tile in image.tiles:
        tile_path = get_udim_tile_path(
            absolute_path,
            tile.number,
        )

        if not os.path.isfile(tile_path):
            missing_tiles.append(tile_path)

    return missing_tiles


def get_udim_tile_path(filepath, tile_number):
    """
    Resolves a UDIM tile filepath.

    Supports paths containing:
        <UDIM>
        %04d

    Args:
        filepath (str): Base tiled image filepath.
        tile_number (int): UDIM tile number.

    Returns:
        str: Resolved tile filepath.
    """
    tile_text = str(tile_number)

    if "<UDIM>" in filepath:
        return filepath.replace("<UDIM>", tile_text)

    if "%04d" in filepath:
        return filepath.replace("%04d", tile_text)

    root, extension = os.path.splitext(filepath)

    # Replace a trailing four-digit UDIM number when present.
    if len(root) >= 4 and root[-4:].isdigit():
        return root[:-4] + tile_text + extension

    return filepath


def sequence_path_exists(filepath):
    """
    Checks whether an image-sequence path exists.

    Blender image datablocks often store the path to one concrete
    sequence frame, so this first checks that exact path.

    Args:
        filepath (str): Resolved sequence filepath.

    Returns:
        bool: True when the referenced sequence file exists.
    """
    return os.path.isfile(filepath)
