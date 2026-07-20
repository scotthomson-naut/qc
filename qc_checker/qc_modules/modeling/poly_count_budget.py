# Standard python imports

# Blender imports
import bpy
import bmesh

# Company imports


# Constants
SCENE_POLY_BUDGET = 500
OBJECT_POLY_BUDGET = 50

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks polygon budgets.
    """
    result = get_objects_exceeding_poly_budget(
        scene_poly_budget=SCENE_POLY_BUDGET,
        object_poly_budget=OBJECT_POLY_BUDGET,
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
        scene_poly_budget=500000,
        object_poly_budget=50000,
    ):
    """
    Checks mesh objects against polygon budgets.

    Counts triangles after Blender evaluates modifiers.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all scene objects.

        scene_poly_budget (int):
            Maximum allowed triangles in the scene.

        object_poly_budget (int):
            Maximum allowed triangles per object.

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
