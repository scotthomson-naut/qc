# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "warning"
LABEL = "No Hidden Geometry"
DESCRIPTION = (
    "Checks if Mesh objects have hidden vertices, edges, or faces "
    "(the Edit Mode 'H' hide state). This doesn't affect render "
    "output - it's a workflow hygiene check, since hidden elements "
    "can confuse the next person who enters Edit Mode without "
    "realizing part of the mesh is hidden."
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_objects_with_hidden_geometry()

    issues = [
        "Failed object: {} - {} hidden vertices, {} hidden edges, "
        "{} hidden faces".format(
            object_name,
            data["hidden_vertex_count"],
            data["hidden_edge_count"],
            data["hidden_face_count"],
        )
        for object_name, data in failed_objects.items()
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


def fix(result_data):
    """
    Fix for issue.

    Note:
        Unlike most visibility-related checks in this tool, this one
        is safe to auto-fix: unhiding mesh elements doesn't change
        the mesh's actual content or render output at all, only an
        Edit Mode display/selection convenience flag.

    Args:
        result_data (dict): Result returned by main().
    Returns:
        dict: Fix result.
    """
    # Call Function
    fix_result = fix_hidden_geometry(result_data)

    return fix_result

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Find
# -------------------------

def get_objects_with_hidden_geometry(objects=None):
    """
    Finds Mesh objects with hidden vertices, edges, or faces.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "hidden_vertex_count": 2,
                "hidden_edge_count": 1,
                "hidden_face_count": 0,
            },
            ...
        }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    failed_objects = {}

    for obj in objects:
        if obj.type != "MESH":
            continue

        if obj.data is None:
            continue

        counts = get_hidden_geometry_counts(obj.data)

        if (
            counts["hidden_vertex_count"]
            or counts["hidden_edge_count"]
            or counts["hidden_face_count"]
        ):
            failed_objects[obj.name] = counts

    return failed_objects


def get_hidden_geometry_counts(mesh):
    """
    Counts hidden vertices, edges and faces on a mesh datablock.

    Args:
        mesh (bpy.types.Mesh):
            Mesh datablock.

    Returns:
        dict:
        {
            "hidden_vertex_count": int,
            "hidden_edge_count": int,
            "hidden_face_count": int,
        }
    """
    hidden_vertices = [False] * len(mesh.vertices)
    mesh.vertices.foreach_get("hide", hidden_vertices)

    hidden_edges = [False] * len(mesh.edges)
    mesh.edges.foreach_get("hide", hidden_edges)

    hidden_polygons = [False] * len(mesh.polygons)
    mesh.polygons.foreach_get("hide", hidden_polygons)

    return {
        "hidden_vertex_count": sum(hidden_vertices),
        "hidden_edge_count": sum(hidden_edges),
        "hidden_face_count": sum(hidden_polygons),
    }


# -------------------------
# Fix
# -------------------------

def fix_hidden_geometry(result_data):
    """
    Unhides all vertices, edges, and faces on the flagged objects'
    mesh datablocks.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    fixed_objects = {}
    issues = []

    for object_name in failed_objects:
        obj = bpy.data.objects.get(object_name)

        if obj is None:
            issues.append(
                "Object no longer exists: {}".format(
                    object_name
                )
            )
            continue

        if obj.data is None or not isinstance(obj.data, bpy.types.Mesh):
            issues.append(
                "Skipped '{}', datablock changed since check ran.".format(
                    object_name
                )
            )
            continue

        if obj.data.library is not None:
            issues.append(
                "Skipped linked object: {}".format(object_name)
            )
            continue

        mesh = obj.data

        before_counts = get_hidden_geometry_counts(mesh)

        mesh.vertices.foreach_set(
            "hide",
            [False] * len(mesh.vertices),
        )
        mesh.edges.foreach_set(
            "hide",
            [False] * len(mesh.edges),
        )
        mesh.polygons.foreach_set(
            "hide",
            [False] * len(mesh.polygons),
        )

        fixed_objects[object_name] = {
            "previous_hidden_vertex_count":
                before_counts["hidden_vertex_count"],
            "previous_hidden_edge_count":
                before_counts["hidden_edge_count"],
            "previous_hidden_face_count":
                before_counts["hidden_face_count"],
        }

    return {
        "issues": issues,
        "fixed_objects": fixed_objects,
    }