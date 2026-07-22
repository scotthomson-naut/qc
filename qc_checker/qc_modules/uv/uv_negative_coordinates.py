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
    Checks for issue.
    
    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_negative_uvs()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} negative UV(s) on {}".format(
                object_name,
                data["negative_uv_count"],
                ", ".join(
                    data["negative_axes"]
                ),
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

def get_objects_with_negative_uvs(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing negative UV coordinates.

    A UV is considered negative when:
        U < 0
        or
        V < 0

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Small tolerance to avoid flagging floating-point values
            extremely close to zero.

    Returns:
        dict:
        {
            "Cube": {
                "uv_map": "UVMap",
                "negative_uv_count": 4,
                "negative_u_count": 2,
                "negative_v_count": 3,
                "negative_axes": ["U", "V"],
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data

        if mesh is None:
            continue

        # Skip meshes without UV maps.
        # This should be handled by the separate
        # "Mesh Has UV Map" QC check.
        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            continue

        negative_uv_count = 0
        negative_u_count = 0
        negative_v_count = 0

        for uv_loop in uv_layer.data:
            uv = uv_loop.uv

            negative_u = (
                uv.x < -tolerance
            )

            negative_v = (
                uv.y < -tolerance
            )

            if negative_u:
                negative_u_count += 1

            if negative_v:
                negative_v_count += 1

            if negative_u or negative_v:
                negative_uv_count += 1

        if negative_uv_count == 0:
            continue

        negative_axes = []

        if negative_u_count:
            negative_axes.append("U")

        if negative_v_count:
            negative_axes.append("V")

        failed_objects[obj.name] = {
            "uv_map": uv_layer.name,
            "negative_uv_count":
                negative_uv_count,
            "negative_u_count":
                negative_u_count,
            "negative_v_count":
                negative_v_count,
            "negative_axes":
                negative_axes,
        }

    return failed_objects
