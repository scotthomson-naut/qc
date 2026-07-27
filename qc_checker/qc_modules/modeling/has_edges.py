# Standard python imports

# Blender imports
import bpy

# Company imports


# Meta data
SEVERITY = "critical"
LABEL = "Has Edges"
DESCRIPTION = (
    "Checks if Object has Edges"
)

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Checks for issue
    """
    failed_objects = get_meshes_without_edges()
    issues = []

    for object_name, data in failed_objects.items():
        issues.append(
            "Failed object: {} - Mesh has no Edges "
            "({} vertices, {} faces)".format(
                object_name,
                data["vertex_count"],
                data["face_count"],
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

def get_meshes_without_edges(objects=None):
    """
    Finds mesh objects that contain no Edges.

    A mesh fails when it exists but has zero edges. This includes:
        - Empty mesh objects
        - Meshes containing only polygons
        - Meshes containing only vertices

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect.
            Defaults to all objects in the current scene.

    Returns:
        dict:
        {
            "Mesh_Object": {
                "vertex_count": 4,
                "edge_count": 0,
                "face_count": 4,
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

        edge_count = len(mesh.edges)

        if edge_count > 0:
            continue

        failed_objects[obj.name] = {
            "vertex_count": len(mesh.vertices) ,
            "edge_count": edge_count,
            "face_count": len(mesh.polygons),
        }

    return failed_objects
