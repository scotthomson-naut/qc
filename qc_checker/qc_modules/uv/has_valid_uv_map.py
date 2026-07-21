# Standard python imports
import re

# Blender imports
import bpy

# Company imports


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_meshes_without_valid_uv_maps()

    issues = [
        "Failed object: {} - Mesh has no UV map".format(
            object_name
        )
        for object_name in failed_objects
    ]

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

def get_meshes_without_valid_uv_maps(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds meshes that either have no UV map or appear to have no
    meaningful UV coordinate data.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

        tolerance (float):
            Tolerance used when comparing UV coordinates.

    Returns:
        dict:
            Failed mesh objects and the reason for failure.
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:

        if obj.type != "MESH":
            continue

        mesh = obj.data

        # No UV layers.
        if not mesh.uv_layers:

            failed_objects[obj.name] = {
                "mesh_name": mesh.name,
                "uv_map_count": 0,
                "reason": "Mesh has no UV map",
            }

            continue

        # A mesh with no polygons does not have meaningful UVs.
        if not mesh.polygons:

            failed_objects[obj.name] = {
                "mesh_name": mesh.name,
                "uv_map_count": len(mesh.uv_layers),
                "reason": "Mesh has no polygons to UV map",
            }

            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:

            failed_objects[obj.name] = {
                "mesh_name": mesh.name,
                "uv_map_count": len(mesh.uv_layers),
                "reason": "Mesh has no active UV map",
            }

    return failed_objects
