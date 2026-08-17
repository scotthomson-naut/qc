# Python imports
import os

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Texture Files Exist"
DESCRIPTION = (
    "Checks if Image textures reference external files that do not exist "
    "on disk. Objects using materials containing missing textures are "
    "reported so they can be selected directly in the scene."
)
WHY = (
    "Prevents broken renders, avoid the dreaded bright pink, missing texture "
    "error, and ensure your project files remain portable when shared across "
    "different computers."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks for missing or broken external image paths.

    Also finds scene objects whose materials use the missing images.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_images": dict,
            "failed_objects": dict,
        }
    """
    failed_images = (
        get_images_with_missing_file_paths()
    )

    failed_objects = (
        get_objects_using_failed_images(
            failed_images
        )
    )

    issues = []

    # ---------------------------------------------------------
    # Object-specific issues
    # ---------------------------------------------------------

    for object_name, object_data in failed_objects.items():

        for image_data in object_data.get(
            "missing_images",
            [],
        ):
            issues.append(
                (
                    'Failed object: "{}" - Missing texture "{}" - {}'
                ).format(
                    object_name,
                    image_data["image_name"],
                    image_data["reason"],
                )
            )

    # ---------------------------------------------------------
    # Missing images not associated with scene objects
    # ---------------------------------------------------------

    referenced_image_names = {
        image_data["image_name"]
        for object_data in failed_objects.values()
        for image_data in object_data.get(
            "missing_images",
            [],
        )
    }

    for image_name, image_data in failed_images.items():

        if image_name in referenced_image_names:
            continue

        issues.append(
            "Missing image: {} - {}".format(
                image_name,
                image_data["reason"],
            )
        )

    return {
        "issues": issues,
        "failed_images": failed_images,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find Missing Images
# -------------------------------------------------------------------------

def get_images_with_missing_file_paths(
        images=None,
    ):
    """
    Finds Blender image datablocks whose external source files are
    missing, invalid, or have empty file paths.

    Checks:
        - FILE images
        - SEQUENCE images
        - MOVIE images
        - TILED / UDIM images

    Ignores:
        - Generated images
        - Viewer images
        - Render Result
        - Packed images

    Args:
        images (iterable[bpy.types.Image] | None):
            Images to inspect.
            Defaults to all image datablocks in the Blender file.

    Returns:
        dict
    """
    if images is None:
        images = bpy.data.images

    failed_images = {}

    for image in images:

        # Ignore images coming directly from linked Blender libraries.
        # Their paths belong to the source library, not this local file.
        if image.library is not None:
            continue

        source = image.source

        # -----------------------------------------------------
        # Internal images
        # -----------------------------------------------------

        if source in {
            "GENERATED",
            "VIEWER",
        }:
            continue

        if image.type == "RENDER_RESULT":
            continue

        # Packed images do not depend on an external file.
        if image.packed_file is not None:
            continue

        filepath = image.filepath

        # -----------------------------------------------------
        # Empty path
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # UDIM
        # -----------------------------------------------------

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
                    "reason": (
                        "One or more UDIM tiles are missing"
                    ),
                    "missing_tiles": missing_tiles,
                }

            continue

        # -----------------------------------------------------
        # Sequence
        # -----------------------------------------------------

        if source == "SEQUENCE":

            if not sequence_path_exists(
                absolute_path
            ):
                failed_images[image.name] = {
                    "filepath": filepath,
                    "absolute_path": absolute_path,
                    "source": source,
                    "reason": (
                        "Image sequence file does not exist"
                    ),
                }

            continue

        # -----------------------------------------------------
        # FILE / MOVIE
        # -----------------------------------------------------

        if not os.path.isfile(
            absolute_path
        ):
            failed_images[image.name] = {
                "filepath": filepath,
                "absolute_path": absolute_path,
                "source": source,
                "reason": "File does not exist",
            }

    return failed_images


# -------------------------------------------------------------------------
# Find Objects Using Missing Images
# -------------------------------------------------------------------------

def get_objects_using_failed_images(
        failed_images,
        objects=None,
    ):
    """
    Finds scene objects whose assigned materials use one or more of the
    missing images.

    Image Texture nodes are searched recursively through shader node groups.

    Args:
        failed_images (dict):
            Result from get_images_with_missing_file_paths().

        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to current scene objects.

    Returns:
        dict:
        {
            "Chair": {
                "object_type": "MESH",
                "missing_image_count": 2,
                "missing_images": [
                    {
                        "image_name": "Chair_BaseColor",
                        "material_name": "Chair_MAT",
                        "material_slot": 0,
                        "node_name": "Base Color",
                        "filepath": "//textures/chair.png",
                        "absolute_path": "...",
                        "source": "FILE",
                        "reason": "File does not exist",
                    }
                ],
            }
        }
    """
    if not isinstance(
        failed_images,
        dict,
    ) or not failed_images:
        return {}

    if objects is None:
        objects = bpy.context.scene.objects

    failed_image_names = set(
        failed_images.keys()
    )

    failed_objects = {}

    for obj in objects:

        # Directly linked objects are read-only and outside local QC scope.
        if obj.library is not None:
            continue

        object_missing_images = []

        material_slots = getattr(
            obj,
            "material_slots",
            [],
        )

        for slot_index, slot in enumerate(
            material_slots
        ):

            material = getattr(
                slot,
                "material",
                None,
            )

            if material is None:
                continue

            if material.library is not None:
                continue

            if not material.use_nodes:
                continue

            node_tree = material.node_tree

            if node_tree is None:
                continue

            image_nodes = (
                get_image_texture_nodes_recursive(
                    node_tree
                )
            )

            for node in image_nodes:

                image = getattr(
                    node,
                    "image",
                    None,
                )

                if image is None:
                    continue

                if image.name not in failed_image_names:
                    continue

                failure_data = failed_images[
                    image.name
                ]

                object_missing_images.append({
                    "image_name":
                        image.name,

                    "material_name":
                        material.name,

                    "material_slot":
                        slot_index,

                    "node_name":
                        node.name,

                    "filepath":
                        failure_data.get(
                            "filepath",
                            "",
                        ),

                    "absolute_path":
                        failure_data.get(
                            "absolute_path",
                            "",
                        ),

                    "source":
                        failure_data.get(
                            "source",
                            "",
                        ),

                    "reason":
                        failure_data.get(
                            "reason",
                            "",
                        ),

                    "missing_tiles":
                        failure_data.get(
                            "missing_tiles",
                            [],
                        ),
                })

        if not object_missing_images:
            continue

        # Remove duplicate entries when the same image is encountered
        # more than once through shared/grouped nodes.
        object_missing_images = (
            deduplicate_missing_image_entries(
                object_missing_images
            )
        )

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "missing_image_count": len(
                object_missing_images
            ),
            "missing_images":
                object_missing_images,
        }

    return failed_objects


# -------------------------------------------------------------------------
# Node Helpers
# -------------------------------------------------------------------------

def get_image_texture_nodes_recursive(
        node_tree,
        visited_node_trees=None,
    ):
    """
    Finds Image Texture nodes in a shader node tree.

    Recurses into Shader Node Groups.

    Args:
        node_tree (bpy.types.NodeTree):
            Node tree to inspect.

        visited_node_trees (set | None):
            Used internally to avoid recursive node-group loops.

    Returns:
        list[bpy.types.Node]
    """
    if node_tree is None:
        return []

    if visited_node_trees is None:
        visited_node_trees = set()

    try:
        tree_pointer = (
            node_tree.as_pointer()
        )
    except Exception:
        tree_pointer = id(
            node_tree
        )

    if tree_pointer in visited_node_trees:
        return []

    visited_node_trees.add(
        tree_pointer
    )

    image_nodes = []

    for node in node_tree.nodes:

        # -----------------------------------------------------
        # Image Texture
        # -----------------------------------------------------

        if node.type == "TEX_IMAGE":
            image_nodes.append(
                node
            )

            continue

        # -----------------------------------------------------
        # Node Group
        # -----------------------------------------------------

        if node.type == "GROUP":

            group_tree = getattr(
                node,
                "node_tree",
                None,
            )

            if group_tree is None:
                continue

            image_nodes.extend(
                get_image_texture_nodes_recursive(
                    group_tree,
                    visited_node_trees,
                )
            )

    return image_nodes


def deduplicate_missing_image_entries(
        entries,
    ):
    """
    Removes duplicate missing-image records.

    A unique record is defined by:
        image
        material
        material slot
        node
    """
    result = []
    seen = set()

    for entry in entries:

        key = (
            entry.get(
                "image_name"
            ),
            entry.get(
                "material_name"
            ),
            entry.get(
                "material_slot"
            ),
            entry.get(
                "node_name"
            ),
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            entry
        )

    return result


# -------------------------------------------------------------------------
# File Helpers
# -------------------------------------------------------------------------

def get_missing_udim_tiles(
        image,
        absolute_path,
    ):
    """
    Returns missing UDIM tile paths for a tiled image.
    """
    missing_tiles = []

    for tile in image.tiles:

        tile_path = get_udim_tile_path(
            absolute_path,
            tile.number,
        )

        if not os.path.isfile(
            tile_path
        ):
            missing_tiles.append(
                tile_path
            )

    return missing_tiles


def get_udim_tile_path(
        filepath,
        tile_number,
    ):
    """
    Resolves a UDIM tile filepath.

    Supports:
        <UDIM>
        %04d
        trailing four-digit UDIM numbers
    """
    tile_text = str(
        tile_number
    )

    if "<UDIM>" in filepath:
        return filepath.replace(
            "<UDIM>",
            tile_text,
        )

    if "%04d" in filepath:
        return filepath.replace(
            "%04d",
            tile_text,
        )

    root, extension = os.path.splitext(
        filepath
    )

    if (
        len(root) >= 4
        and root[-4:].isdigit()
    ):
        return (
            root[:-4]
            + tile_text
            + extension
        )

    return filepath


def sequence_path_exists(
        filepath,
    ):
    """
    Checks whether an image-sequence path exists.
    """
    return os.path.isfile(
        filepath
    )
