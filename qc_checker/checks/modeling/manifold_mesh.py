# Blender imports
import bpy
import bmesh


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Manifold Mesh"
DESCRIPTION = (
    "Checks if Object has Manifold Edges. "
)
WHY = (
    "Ensures a 3D model is 'watertight', meaning every edge connects "
    "to a maximum of two faces, and there are no holes, loose vertices, "
    "or impossible geometry. "
    "A manifold mesh is required for successful 3D printing, "
    "accurate Physics and Fluid simulations, Proper UV unwrapping, "
    "and reliable Boolean operation."
)


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Checks scene mesh objects for non-manifold geometry.
    """
    failed_objects = get_objects_with_non_manifold_geometry()

    issues = []

    for object_name, data in failed_objects.items():
        issue_parts = []

        if data["boundary_edges"]:
            issue_parts.append(
                "{} boundary/hole edge(s)".format(
                    len(data["boundary_edges"])
                )
            )

        if data["wire_edges"]:
            issue_parts.append(
                "{} loose edge(s)".format(
                    len(data["wire_edges"])
                )
            )

        if data["multi_face_edges"]:
            issue_parts.append(
                "{} edge(s) shared by more than 2 faces".format(
                    len(data["multi_face_edges"])
                )
            )

        issues.append(
            "Failed object: {} — {}".format(
                object_name,
                ", ".join(issue_parts),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_objects_with_non_manifold_geometry(
        objects=None,
        include_boundary=True,
        include_wire=True,
        include_multi_face=True,
    ):
    """
    Finds mesh objects containing non-manifold edges.

    Detects:
        - Boundary edges shared by one face, usually holes/open geometry.
        - Wire edges shared by no faces.
        - Edges shared by more than two faces.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Objects to inspect. Defaults to every object in the current scene.
        include_boundary (bool):
            Include edges connected to exactly one face.
        include_wire (bool):
            Include edges connected to no faces.
        include_multi_face (bool):
            Include edges connected to more than two faces.

    Returns:
        dict:
            Object names mapped to details about their non-manifold edges.

            Example:
            {
                "Cube": {
                    "boundary_edges": [0, 1, 2],
                    "wire_edges": [],
                    "multi_face_edges": [8],
                    "non_manifold_edges": [0, 1, 2, 8],
                    "edge_count": 4,
                }
            }
    """
    if objects is None:
        objects = bpy.context.scene.objects

    results = {}

    mesh_cache = {}

    for obj in objects:
        # Ignore directly linked library objects. They are read-only
        # in this file and cannot be safely fixed by this QC check.
        if obj.library is not None:
            continue


        if obj.type != "MESH":
            continue

        mesh = obj.data

        if mesh is None:
            continue

        # -----------------------------------------------------
        # Analyze each unique Mesh datablock only once
        # -----------------------------------------------------

        if mesh not in mesh_cache:

            bm = bmesh.new()

            try:
                bm.from_mesh(
                    mesh
                )

                bm.edges.ensure_lookup_table()

                boundary_edges = []
                wire_edges = []
                multi_face_edges = []

                for edge in bm.edges:

                    face_count = len(
                        edge.link_faces
                    )

                    if (
                        include_wire
                        and face_count == 0
                    ):
                        wire_edges.append(
                            edge.index
                        )

                    elif (
                        include_boundary
                        and face_count == 1
                    ):
                        boundary_edges.append(
                            edge.index
                        )

                    elif (
                        include_multi_face
                        and face_count > 2
                    ):
                        multi_face_edges.append(
                            edge.index
                        )

                non_manifold_edges = (
                    wire_edges
                    + boundary_edges
                    + multi_face_edges
                )

                if non_manifold_edges:

                    mesh_cache[
                        mesh
                    ] = {
                        "boundary_edges":
                            boundary_edges,

                        "wire_edges":
                            wire_edges,

                        "multi_face_edges":
                            multi_face_edges,

                        "non_manifold_edges":
                            non_manifold_edges,

                        "edge_count":
                            len(
                                non_manifold_edges
                            ),
                    }

                else:

                    mesh_cache[
                        mesh
                    ] = None

            finally:
                bm.free()

        # -----------------------------------------------------
        # Mesh passes
        # -----------------------------------------------------

        mesh_result = mesh_cache[
            mesh
        ]

        if mesh_result is None:
            continue

        # -----------------------------------------------------
        # Store result for this object
        # -----------------------------------------------------

        results[
            obj.name
        ] = {
            "boundary_edges":
                list(
                    mesh_result[
                        "boundary_edges"
                    ]
                ),

            "wire_edges":
                list(
                    mesh_result[
                        "wire_edges"
                    ]
                ),

            "multi_face_edges":
                list(
                    mesh_result[
                        "multi_face_edges"
                    ]
                ),

            "non_manifold_edges":
                list(
                    mesh_result[
                        "non_manifold_edges"
                    ]
                ),

            "edge_count":
                mesh_result[
                    "edge_count"
                ],

            "selection": {
                "mode":
                    "EDGE",

                "indices":
                    list(
                        mesh_result[
                            "non_manifold_edges"
                        ]
                    ),
            },
        }

    return results