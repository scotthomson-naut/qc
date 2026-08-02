"""Object and mesh-component selection helpers."""

import bpy
import bmesh


def select_object(
    context,
    obj,
):
    """
    Select and activate one Blender object.
    """
    if obj is None:
        return False

    # Leave Edit Mode before changing active objects.
    active_object = context.view_layer.objects.active

    if (
        active_object is not None
        and active_object.mode != "OBJECT"
    ):
        try:
            bpy.ops.object.mode_set(
                mode="OBJECT"
            )
        except RuntimeError:
            return False

    for selected_object in context.selected_objects:
        selected_object.select_set(
            False
        )

    try:
        obj.hide_set(
            False
        )
    except RuntimeError:
        pass

    obj.hide_viewport = False
    obj.hide_select = False

    obj.select_set(
        True
    )

    context.view_layer.objects.active = (
        obj
    )

    return True


def select_mesh_components(
    context,
    obj,
    selection_data,
):
    """
    Select mesh components described by QC result metadata.

    Supported formats:

        {
            "mode": "FACE",
            "indices": [0, 4, 8],
        }

        {
            "mode": "MIXED",
            "vertex_indices": [...],
            "edge_indices": [...],
            "face_indices": [...],
        }

    Args:
        context:
            Blender context.

        obj:
            Mesh object.

        selection_data:
            Serialized QC component selection dictionary.

    Returns:
        tuple[bool, str]:
            Success state and message.
    """
    if obj is None:
        return False, "Object does not exist."

    if obj.type != "MESH":
        return False, "Object is not a mesh."

    if not isinstance(
        selection_data,
        dict,
    ):
        return False, "No component selection data exists."

    if not select_object(
        context,
        obj,
    ):
        return False, "Could not activate the object."

    selection_mode = str(
        selection_data.get(
            "mode",
            "",
        )
    ).upper()

    try:
        bpy.ops.object.mode_set(
            mode="EDIT"
        )

    except RuntimeError as error:
        return (
            False,
            "Could not enter Edit Mode: {}".format(
                error
            ),
        )

    bm = bmesh.from_edit_mesh(
        obj.data
    )

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Clear the current component selection.
    for vertex in bm.verts:
        vertex.select_set(
            False
        )

    for edge in bm.edges:
        edge.select_set(
            False
        )

    for face in bm.faces:
        face.select_set(
            False
        )

    selected_count = 0

    # ---------------------------------------------------------
    # Vertex selection
    # ---------------------------------------------------------

    if selection_mode == "VERT":
        bpy.ops.mesh.select_mode(
            type="VERT"
        )

        indices = selection_data.get(
            "indices",
            [],
        )

        selected_count += select_bmesh_elements(
            bm.verts,
            indices,
        )

    # ---------------------------------------------------------
    # Edge selection
    # ---------------------------------------------------------

    elif selection_mode == "EDGE":
        bpy.ops.mesh.select_mode(
            type="EDGE"
        )

        indices = selection_data.get(
            "indices",
            [],
        )

        selected_count += select_bmesh_elements(
            bm.edges,
            indices,
        )

    # ---------------------------------------------------------
    # Face selection
    # ---------------------------------------------------------

    elif selection_mode == "FACE":
        bpy.ops.mesh.select_mode(
            type="FACE"
        )

        indices = selection_data.get(
            "indices",
            [],
        )

        selected_count += select_bmesh_elements(
            bm.faces,
            indices,
        )

    # ---------------------------------------------------------
    # Mixed component selection
    # ---------------------------------------------------------

    elif selection_mode == "MIXED":
        vertex_indices = selection_data.get(
            "vertex_indices",
            [],
        )

        edge_indices = selection_data.get(
            "edge_indices",
            [],
        )

        face_indices = selection_data.get(
            "face_indices",
            [],
        )

        # Choose the most useful visible selection mode.
        if face_indices:
            bpy.ops.mesh.select_mode(
                type="FACE"
            )

        elif edge_indices:
            bpy.ops.mesh.select_mode(
                type="EDGE"
            )

        else:
            bpy.ops.mesh.select_mode(
                type="VERT"
            )

        selected_count += select_bmesh_elements(
            bm.verts,
            vertex_indices,
        )

        selected_count += select_bmesh_elements(
            bm.edges,
            edge_indices,
        )

        selected_count += select_bmesh_elements(
            bm.faces,
            face_indices,
        )

    else:
        return (
            False,
            'Unsupported component mode: "{}".'.format(
                selection_mode
            ),
        )

    bmesh.update_edit_mesh(
        obj.data,
        loop_triangles=False,
        destructive=False,
    )

    if selected_count == 0:
        return (
            False,
            "No valid mesh component indices were found.",
        )

    return (
        True,
        "Selected {} mesh component{}.".format(
            selected_count,
            ""
            if selected_count == 1
            else "s",
        ),
    )


def select_bmesh_elements(
    elements,
    indices,
):
    """
    Select valid BMesh elements by index.

    Returns:
        int:
            Number of selected elements.
    """
    if not isinstance(
        indices,
        (list, tuple, set),
    ):
        return 0

    selected_count = 0

    for raw_index in indices:
        try:
            index = int(
                raw_index
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            index < 0
            or index >= len(elements)
        ):
            continue

        element = elements[
            index
        ]

        if not element.is_valid:
            continue

        element.select_set(
            True
        )

        selected_count += 1

    return selected_count
