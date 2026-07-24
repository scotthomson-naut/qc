# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
LABEL = "UV Outside Tile Area"
DESCRIPTION = (
    "Checks if Object has UVs Outside of the Tile Area"
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
    failed_objects = get_objects_with_uvs_outside_01()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - {} UV(s) outside 0-1 range".format(
                object_name,
                data["outside_uv_count"],
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

def get_objects_with_uvs_outside_01(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing UV coordinates outside the 0-1 tile.

    Valid UV range:
        0 <= U <= 1
        0 <= V <= 1

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

        tolerance (float):
            Floating-point tolerance around the 0-1 boundaries.

    Returns:
        dict:
        {
            "Cube": {
                "uv_map": "UVMap",
                "outside_uv_count": 4,
                "below_zero_count": 2,
                "above_one_count": 3,
                "polygon_indices": [2, 5],
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

        # Missing UV maps should be handled by a separate QC check.
        if not mesh.uv_layers:
            continue

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            continue

        uv_data = uv_layer.data

        outside_uv_count = 0
        below_zero_count = 0
        above_one_count = 0

        polygon_indices = set()

        # ---------------------------------------------------------
        # Check polygons and their UV loops
        # ---------------------------------------------------------

        for polygon in mesh.polygons:
            polygon_failed = False
            for loop_index in polygon.loop_indices:
                uv = uv_data[loop_index].uv

                below_zero = (
                    uv.x < -tolerance
                    or uv.y < -tolerance
                )

                above_one = (
                    uv.x > 1.0 + tolerance
                    or uv.y > 1.0 + tolerance
                )

                if below_zero:
                    below_zero_count += 1

                if above_one:
                    above_one_count += 1

                if below_zero or above_one:
                    outside_uv_count += 1
                    polygon_failed = True

            if polygon_failed:
                polygon_indices.add(
                    polygon.index
                )

        # ---------------------------------------------------------
        # Store failure
        # ---------------------------------------------------------

        if outside_uv_count:
            failed_objects[obj.name] = {
                "uv_map": uv_layer.name,
                "outside_uv_count":
                    outside_uv_count,
                "below_zero_count":
                    below_zero_count,
                "above_one_count":
                    above_one_count,
                "polygon_indices":
                    sorted(polygon_indices),
            }

    return failed_objects
