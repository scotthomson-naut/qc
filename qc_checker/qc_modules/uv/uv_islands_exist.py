# Standard python imports


# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "UV Island Exist"
DESCRIPTION = (
    "Checks if Object has UV Islands"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue.
    
    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_without_uv_islands()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {}".format(
                object_name,
                data["reason"],
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

def get_objects_without_uv_islands(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects that do not appear to have generated UV islands.

    A mesh fails when:
        - It has polygons but no UV map.
        - It has no active UV map.
        - It has UV data, but all UV coordinates are effectively
          collapsed to the same point.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Tolerance used when comparing UV coordinates.

    Returns:
        dict:
        {
            "Character_Body": {
                "uv_map": "UVMap",
                "polygon_count": 1200,
                "reason": "UV coordinates are collapsed",
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

        # Ignore meshes with no faces.
        # That should be handled by the separate
        # "Meshes Have Faces" QC check.
        if not mesh.polygons:
            continue

        # ---------------------------------------------------------
        # No UV map
        # ---------------------------------------------------------

        if not mesh.uv_layers:

            failed_objects[obj.name] = {
                "uv_map": None,
                "polygon_count": len(mesh.polygons),
                "reason": "Mesh has no UV map",
            }

            continue

        # ---------------------------------------------------------
        # No active UV map
        # ---------------------------------------------------------

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:

            failed_objects[obj.name] = {
                "uv_map": None,
                "polygon_count": len(mesh.polygons),
                "reason": "Mesh has no active UV map",
            }

            continue

        uv_data = uv_layer.data

        if not uv_data:

            failed_objects[obj.name] = {
                "uv_map": uv_layer.name,
                "polygon_count": len(mesh.polygons),
                "reason": "UV map contains no UV data",
            }

            continue

        # ---------------------------------------------------------
        # Check whether UV coordinates have meaningful variation
        # ---------------------------------------------------------

        first_uv = uv_data[0].uv.copy()

        has_uv_variation = False

        for uv_loop in uv_data[1:]:

            uv = uv_loop.uv

            if (
                abs(uv.x - first_uv.x) > tolerance
                or
                abs(uv.y - first_uv.y) > tolerance
            ):
                has_uv_variation = True
                break

        if has_uv_variation:
            continue

        # Every UV corner is effectively at the same coordinate.
        failed_objects[obj.name] = {
            "uv_map": uv_layer.name,
            "polygon_count": len(mesh.polygons),
            "reason": "UV coordinates are collapsed; no UV islands detected",
        }

    return failed_objects
