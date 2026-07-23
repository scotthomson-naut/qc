# Standard python imports


# Blender imports
import bpy

# Company imports


# Meta data
LABEL = "All Polygons have UV coordinates"
DESCRIPTION = (
    "Checks Every polygon has UV coordinates"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks that every animated channel has a key at the start
    and end of the timeline.
    """
    failed_objects = get_meshes_with_unmapped_polygons()
    issues = []

    for object_name, data in failed_objects.items():
        reason = data.get("reason")
        if reason:
            issues.append(
                "Failed object: {} - {}".format(
                    object_name,
                    reason,
                )
            )
        else:
            issues.append(
                "Failed object: {} - {} of {} polygons "
                "do not have valid UV coordinates".format(
                    object_name,
                    data["unmapped_count"],
                    data["polygon_count"],
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

def get_meshes_with_unmapped_polygons(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing polygons without meaningful UV coordinates.

    A polygon is considered invalid when:
        - The mesh has no UV map.
        - There is no active UV map.
        - The polygon has no UV loop data.
        - All UV coordinates for the polygon are effectively identical.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Tolerance used when comparing UV coordinates.

    Returns:
        dict:
        {
            "MeshObject": {
                "uv_map": "UVMap",
                "polygon_count": 100,
                "unmapped_count": 2,
                "unmapped_polygons": [14, 27],
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

        if not mesh.polygons:
            continue

        # ---------------------------------------------------------
        # No UV maps
        # ---------------------------------------------------------

        if not mesh.uv_layers:

            failed_objects[obj.name] = {
                "uv_map": None,
                "polygon_count": len(mesh.polygons),
                "unmapped_count": len(mesh.polygons),
                "unmapped_polygons": [
                    polygon.index
                    for polygon in mesh.polygons
                ],
                "reason": "Mesh has no UV map",
            }

            continue

        # ---------------------------------------------------------
        # Active UV map
        # ---------------------------------------------------------

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:

            failed_objects[obj.name] = {
                "uv_map": None,
                "polygon_count": len(mesh.polygons),
                "unmapped_count": len(mesh.polygons),
                "unmapped_polygons": [
                    polygon.index
                    for polygon in mesh.polygons
                ],
                "reason": "Mesh has no active UV map",
            }

            continue

        uv_data = uv_layer.data

        unmapped_polygons = []

        # ---------------------------------------------------------
        # Inspect every polygon
        # ---------------------------------------------------------

        for polygon in mesh.polygons:

            polygon_uvs = []

            for loop_index in polygon.loop_indices:

                if loop_index >= len(uv_data):
                    continue

                uv = uv_data[loop_index].uv

                polygon_uvs.append(
                    (uv.x, uv.y)
                )

            # No UV data found for polygon.
            if not polygon_uvs:
                unmapped_polygons.append(
                    polygon.index
                )
                continue

            # Check whether all corners have effectively
            # the same UV coordinate.
            first_u, first_v = polygon_uvs[0]

            has_uv_area = False

            for u, v in polygon_uvs[1:]:

                if (
                    abs(u - first_u) > tolerance
                    or abs(v - first_v) > tolerance
                ):
                    has_uv_area = True
                    break

            if not has_uv_area:
                unmapped_polygons.append(
                    polygon.index
                )

        # ---------------------------------------------------------
        # Store failures
        # ---------------------------------------------------------

        if unmapped_polygons:

            failed_objects[obj.name] = {
                "uv_map": uv_layer.name,
                "polygon_count": len(mesh.polygons),
                "unmapped_count": len(
                    unmapped_polygons
                ),
                "unmapped_polygons":
                    unmapped_polygons,
            }

    return failed_objects
