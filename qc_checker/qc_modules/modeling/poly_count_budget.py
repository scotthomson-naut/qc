# Standard python imports

# Blender imports
import bpy
import bmesh

# Company imports

# Meta data
LABEL = "Poly Count Above Limit"
DESCRIPTION = (
    "Checks if Object is below a certain Poly count"
)

# Constants
SETTINGS = {
    "budget_scene": {
        "type": "int",
        "label": "Maximum Polys per Scene",
        "description": (
            "Maximum recommended Polys per scene"
        ),
        "default": 100000,
        "min": 1,
        "max": 1000000,
    },

    "budget_object": {
        "type": "int",
        "label": "Maximum Polys per Object",
        "description": (
            "Maximum recommended Polys per object"
        ),
        "default": 20000,
        "min": 1,
        "max": 50000,
    },
}


# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks polygon budgets.
    """
    settings = resolve_settings(
        preferences
    )

    result = get_objects_exceeding_poly_budget(
        settings
    )

    issues = []

    if result["scene_over_budget"]:
        issues.append(
            "Scene poly count: {} / {}".format(
                result["scene_poly_count"],
                result["scene_budget"],
            )
        )

    for name, data in result["failed_objects"].items():
        issues.append(
            "Failed object: {} ({} / {})".format(
                name,
                data["poly_count"],
                data["budget"],
            )
        )

    return {
        "issues": issues,
        "scene_poly_count": result["scene_poly_count"],
        "scene_budget": result["scene_budget"],
        "failed_objects": result["failed_objects"],
    }

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------


# -------------------------
# Find
# -------------------------

def get_objects_exceeding_poly_budget(
        objects=None,
        settings=None
    ):
    """
    Checks mesh objects against polygon budgets.

    Counts triangles after Blender evaluates modifiers.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

    Returns:
        dict:
        {
            "scene_poly_count": 125432,
            "scene_over_budget": False,
            "scene_budget": 500000,
            "failed_objects":
            {
                "Robot":
                {
                    "poly_count": 65432,
                    "budget": 50000,
                }
            }
        }
    """
    scene_poly_budget = settings["budget_scene"]
    object_poly_budget = settings["budget_object"]
    
    if objects is None:
        objects = bpy.context.scene.objects

    depsgraph = bpy.context.evaluated_depsgraph_get()

    failed_objects = {}
    total_triangles = 0

    for obj in objects:

        if obj.type != 'MESH':
            continue

        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()

        try:
            mesh.calc_loop_triangles()

            tri_count = len(mesh.loop_triangles)
            total_triangles += tri_count

            if tri_count > object_poly_budget:
                failed_objects[obj.name] = {
                    "poly_count": tri_count,
                    "budget": object_poly_budget,
                }

        finally:
            obj_eval.to_mesh_clear()

    return {
        "scene_poly_count": total_triangles,
        "scene_budget": scene_poly_budget,
        "scene_over_budget": total_triangles > scene_poly_budget,
        "failed_objects": failed_objects,
    }
