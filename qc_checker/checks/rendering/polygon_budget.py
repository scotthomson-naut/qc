# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Polygon Budget"
DESCRIPTION = (
    "Checks whether the scene and individual mesh objects "
    "are below configurable polygon limits."
)
WHY = (
    "Help keep a constant flow of assets in scenes."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "budget_scene": {
        "type": "int",
        "label": "Maximum Polys per Scene",
        "description": (
            "Maximum recommended triangle count for the scene."
        ),
        "default": 100000,
        "min": 1,
        "max": 1000000,
    },

    "budget_object": {
        "type": "int",
        "label": "Maximum Polys per Object",
        "description": (
            "Maximum recommended triangle count per object."
        ),
        "default": 20000,
        "min": 1,
        "max": 50000,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks scene and object polygon budgets.

    Args:
        preferences (dict | None):
            User-configured check settings.

    Returns:
        dict:
            Normalized QC result.
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    result = get_objects_exceeding_poly_budget(
        settings=settings,
    )

    issues = []

    if result["scene_over_budget"]:
        issues.append(
            "Scene poly count: {} / {}".format(
                result["scene_poly_count"],
                result["scene_budget"],
            )
        )

    for object_name, data in result["failed_objects"].items():
        issues.append(
            "Failed object: {} ({} / {})".format(
                object_name,
                data["poly_count"],
                data["budget"],
            )
        )

    return {
        "issues": issues,
        "scene_poly_count": result["scene_poly_count"],
        "scene_budget": result["scene_budget"],
        "scene_over_budget": result["scene_over_budget"],
        "failed_objects": result["failed_objects"],
    }

# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_exceeding_poly_budget(
        objects=None,
        settings=None,
    ):
    """
    Checks evaluated mesh objects against polygon budgets.

    Polygon count is measured as triangles after modifiers are evaluated.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to current scene objects.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "scene_poly_count": int,
            "scene_over_budget": bool,
            "scene_budget": int,
            "failed_objects": dict,
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    scene_poly_budget = int(
        settings["budget_scene"]
    )

    object_poly_budget = int(
        settings["budget_object"]
    )

    if objects is None:
        objects = bpy.context.scene.objects

    depsgraph = (
        bpy.context.evaluated_depsgraph_get()
    )

    failed_objects = {}
    total_triangles = 0

    for obj in objects:

        if obj.library is not None:
            continue

        if obj.type != "MESH":
            continue

        obj_eval = obj.evaluated_get(
            depsgraph
        )

        mesh = obj_eval.to_mesh()

        if mesh is None:
            continue

        try:
            mesh.calc_loop_triangles()

            triangle_count = len(
                mesh.loop_triangles
            )

            total_triangles += (
                triangle_count
            )

            if triangle_count > object_poly_budget:
                failed_objects[obj.name] = {
                    "poly_count": triangle_count,
                    "budget": object_poly_budget,
                }

        finally:
            obj_eval.to_mesh_clear()

    return {
        "scene_poly_count": total_triangles,
        "scene_budget": scene_poly_budget,
        "scene_over_budget": (
            total_triangles
            > scene_poly_budget
        ),
        "failed_objects": failed_objects,
    }
