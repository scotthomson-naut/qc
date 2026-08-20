# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "info"
LABEL = "UV Within Bounds"
DESCRIPTION = (
    "Checks all UV maps for UV coordinates outside the 0-1 tile. "
)
WHY = (
    "Out-of-bounds UVs can cause unintended texture repetition, "
    "baking issues, seams, and inconsistent texel density."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks all UV maps for UV coordinates outside the 0-1 range.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
        }
    """
    failed_objects = (
        get_objects_with_uvs_outside_01()
    )

    issues = []

    for object_name, object_data in (
        failed_objects.items()
    ):
        failed_uv_maps = object_data.get(
            "failed_uv_maps",
            {},
        )

        for uv_map_name, uv_map_data in (
            failed_uv_maps.items()
        ):
            issues.append(
                (
                    "Failed object: {} - UV map '{}' has "
                    "{} UV(s) outside 0-1 range"
                ).format(
                    object_name,
                    uv_map_name,
                    uv_map_data[
                        "outside_uv_count"
                    ],
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_uvs_outside_01(
        objects=None,
        tolerance=1e-6,
    ):
    """
    Finds mesh objects containing UV coordinates outside the 0-1 tile
    across all UV maps.

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
                "failed_uv_maps": {
                    "UVMap": {
                        "outside_uv_count": 4,
                        "below_zero_count": 2,
                        "above_one_count": 3,
                        "polygon_indices": [2, 5],
                    }
                },
                "failed_uv_map_count": 1,
                "outside_uv_count": 4,
                "polygon_indices": [2, 5],
                "selection": {
                    "mode": "FACE",
                    "indices": [2, 5],
                },
            }
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    # Keep mesh data synchronized with what is visible in Edit Mode.
    if (
        bpy.context.object
        and bpy.context.object.mode == "EDIT"
    ):
        bpy.ops.object.mode_set(
            mode="OBJECT"
        )

    for obj in objects:

        # Directly linked library objects are read-only and outside
        # the scope of local UV QC.
        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        mesh = obj.data

        if mesh is None:
            continue

        # Missing UV maps are handled by another check.
        if not mesh.uv_layers:
            continue

        failed_uv_maps = {}

        all_failed_polygon_indices = set()

        total_outside_uv_count = 0
        total_below_zero_count = 0
        total_above_one_count = 0

        # -----------------------------------------------------
        # Check every UV map
        # -----------------------------------------------------

        for uv_layer in mesh.uv_layers:

            uv_data = uv_layer.data

            outside_uv_count = 0
            below_zero_count = 0
            above_one_count = 0

            polygon_indices = set()

            # -------------------------------------------------
            # Check polygon UV loops
            # -------------------------------------------------

            for polygon in mesh.polygons:

                polygon_failed = False

                for loop_index in polygon.loop_indices:

                    uv = uv_data[
                        loop_index
                    ].uv

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

                    if (
                        below_zero
                        or above_one
                    ):
                        outside_uv_count += 1
                        polygon_failed = True

                if polygon_failed:
                    polygon_indices.add(
                        polygon.index
                    )

                    all_failed_polygon_indices.add(
                        polygon.index
                    )

            # -------------------------------------------------
            # Store UV-map failure
            # -------------------------------------------------

            if not outside_uv_count:
                continue

            failed_uv_maps[
                uv_layer.name
            ] = {
                "outside_uv_count":
                    outside_uv_count,

                "below_zero_count":
                    below_zero_count,

                "above_one_count":
                    above_one_count,

                "polygon_indices":
                    sorted(
                        polygon_indices
                    ),
            }

            total_outside_uv_count += (
                outside_uv_count
            )

            total_below_zero_count += (
                below_zero_count
            )

            total_above_one_count += (
                above_one_count
            )

        # -----------------------------------------------------
        # Object passes all UV maps
        # -----------------------------------------------------

        if not failed_uv_maps:
            continue

        combined_polygon_indices = sorted(
            all_failed_polygon_indices
        )

        failed_objects[
            obj.name
        ] = {
            "failed_uv_maps":
                failed_uv_maps,

            "failed_uv_map_count":
                len(failed_uv_maps),

            # Total UV-loop failures across all UV maps.
            "outside_uv_count":
                total_outside_uv_count,

            "below_zero_count":
                total_below_zero_count,

            "above_one_count":
                total_above_one_count,

            # Unique geometry faces affected in any UV map.
            "polygon_indices":
                combined_polygon_indices,

            # Works with your Select Failed Components button.
            "selection": {
                "mode": "FACE",
                "indices":
                    combined_polygon_indices,
            },
        }

    return failed_objects
