# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Material Output Connected"
DESCRIPTION = (
    "Checks materials for shader nodes that are not connected, directly "
    "or indirectly, to an active Material Output node."
)
WHY = (
    "Unconnected shader nodes helps you clean up unused data, "
    "prevent clutter in your node trees, and save render time. Unlinked "
    "nodes do not affect how your object looks, but they can confuse you "
    "later or cause mistakes when you export your 3D mode."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "ignore_muted_nodes": {
        "type": "bool",
        "label": "Ignore Muted Nodes",
        "description": (
            "Do not report muted nodes that are disconnected from the "
            "Material Output."
        ),
        "default": False,
    },

    "ignore_frames": {
        "type": "bool",
        "label": "Ignore Frame Nodes",
        "description": (
            "Do not report Frame nodes. A Frame is considered used when "
            "at least one node inside it contributes to the output."
        ),
        "default": True,
    },

    "ignore_reroutes": {
        "type": "bool",
        "label": "Ignore Reroute Nodes",
        "description": (
            "Do not report disconnected Reroute nodes."
        ),
        "default": False,
    },

    "ignore_materials_without_nodes": {
        "type": "bool",
        "label": "Ignore Materials Without Nodes",
        "description": (
            "Ignore materials that do not have Use Nodes enabled."
        ),
        "default": True,
    },

    "active_outputs_only": {
        "type": "bool",
        "label": "Active Outputs Only",
        "description": (
            "Only consider active Material Output nodes. When disabled, "
            "connections to any Material Output are considered valid."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds objects whose materials contain shader nodes that do not
    contribute to a Material Output node.

    Args:
        preferences (dict | None):
            User-configured check settings.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "failed_materials": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_materials = get_materials_with_unconnected_nodes(
        settings=settings,
    )

    failed_objects = get_objects_using_failed_materials(
        failed_materials=failed_materials,
    )

    issues = []

    for material_name, material_data in sorted(
        failed_materials.items()
    ):
        disconnected_nodes = material_data.get(
            "unconnected_nodes",
            [],
        )

        node_labels = []

        for node_data in disconnected_nodes:
            node_name = node_data.get(
                "node_name",
                "",
            )

            node_label = node_data.get(
                "node_label",
                "",
            )

            if node_label and node_label != node_name:
                node_labels.append(
                    '{} "{}"'.format(
                        node_name,
                        node_label,
                    )
                )
            else:
                node_labels.append(
                    node_name
                )

        if material_data.get(
            "missing_output",
            False,
        ):
            issues.append(
                (
                    'Material "{}" has no Material Output node. '
                    "{} shader node{} cannot contribute to the material."
                ).format(
                    material_name,
                    len(disconnected_nodes),
                    ""
                    if len(disconnected_nodes) == 1
                    else "s",
                )
            )

        elif material_data.get(
            "disconnected_output",
            False,
        ):
            issues.append(
                (
                    'Material "{}" has no connected Material Output. '
                    "{} shader node{} do not contribute to the material: {}."
                ).format(
                    material_name,
                    len(disconnected_nodes),
                    ""
                    if len(disconnected_nodes) == 1
                    else "s",
                    ", ".join(node_labels),
                )
            )

        else:
            issues.append(
                (
                    'Material "{}" has {} shader node{} not connected '
                    "to the Material Output: {}."
                ).format(
                    material_name,
                    len(disconnected_nodes),
                    ""
                    if len(disconnected_nodes) == 1
                    else "s",
                    ", ".join(node_labels),
                )
            )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "failed_materials": failed_materials,
        "settings": settings,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_materials_with_unconnected_nodes(
        materials=None,
        settings=None,
    ):
    """
    Finds materials containing nodes that are not upstream of a Material
    Output node.

    Args:
        materials (iterable[bpy.types.Material] | None):
            Materials to inspect. Defaults to materials assigned to objects
            in the current scene.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    if materials is None:
        materials = get_scene_materials()

    failed_materials = {}

    for material in materials:

        if material is None:
            continue

        if material.library is not None:
            continue

        material_result = get_material_unconnected_nodes(
            material=material,
            settings=settings,
        )

        if material_result is None:
            continue

        failed_materials[material.name] = material_result

    return failed_materials


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_material_unconnected_nodes(
        material,
        settings=None,
    ):
    """
    Checks one material for nodes that do not contribute to a Material
    Output node.

    Args:
        material (bpy.types.Material):
            Material to inspect.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict | None
    """
    if material is None:
        return None

    if settings is None:
        settings = resolve_settings(SETTINGS)

    use_nodes = bool(
        getattr(
            material,
            "use_nodes",
            False,
        )
    )

    if not use_nodes:
        if settings["ignore_materials_without_nodes"]:
            return None

        return {
            "material_name": material.name,
            "use_nodes": False,
            "missing_output": True,
            "disconnected_output": True,
            "output_nodes": [],
            "connected_node_count": 0,
            "unconnected_node_count": 0,
            "unconnected_nodes": [],
        }

    node_tree = getattr(
        material,
        "node_tree",
        None,
    )

    if node_tree is None:
        return None

    nodes = list(
        node_tree.nodes
    )

    output_nodes = get_material_output_nodes(
        node_tree=node_tree,
        active_only=settings[
            "active_outputs_only"
        ],
    )

    connected_nodes = set()
    connected_output_nodes = []

    for output_node in output_nodes:
        output_connections = get_input_links(
            output_node
        )

        if not output_connections:
            continue

        connected_output_nodes.append(
            output_node
        )

        collect_upstream_nodes(
            node=output_node,
            connected_nodes=connected_nodes,
        )

    reportable_nodes = []

    for node in nodes:
        # Material Output nodes are endpoints, not unused shader nodes.
        if node.type == "OUTPUT_MATERIAL":
            continue

        if should_ignore_node(
            node=node,
            connected_nodes=connected_nodes,
            settings=settings,
        ):
            continue

        if node in connected_nodes:
            continue

        reportable_nodes.append(
            serialize_node(
                node
            )
        )

    missing_output = (
        len(output_nodes) == 0
    )

    disconnected_output = (
        bool(output_nodes)
        and not connected_output_nodes
    )

    if (
        not reportable_nodes
        and not missing_output
        and not disconnected_output
    ):
        return None

    return {
        "material_name": material.name,
        "use_nodes": use_nodes,
        "missing_output": missing_output,
        "disconnected_output": disconnected_output,
        "output_node_count": len(
            output_nodes
        ),
        "connected_output_count": len(
            connected_output_nodes
        ),
        "output_nodes": [
            serialize_node(output_node)
            for output_node in output_nodes
        ],
        "connected_node_count": len(
            connected_nodes
        ),
        "unconnected_node_count": len(
            reportable_nodes
        ),
        "unconnected_nodes": reportable_nodes,
    }


# -------------------------------------------------------------------------
# Graph traversal
# -------------------------------------------------------------------------

def collect_upstream_nodes(
        node,
        connected_nodes,
    ):
    """
    Recursively collects every node that contributes to the supplied node.

    Traversal follows links backward:

        Material Output input
            <- Surface Shader
            <- Textures
            <- Mapping
            <- Coordinates

    Args:
        node (bpy.types.Node):
            Node from which to begin walking upstream.

        connected_nodes (set):
            Set populated with connected nodes.
    """
    if node is None:
        return

    if node in connected_nodes:
        return

    connected_nodes.add(
        node
    )

    for input_socket in getattr(
        node,
        "inputs",
        [],
    ):
        if not bool(
            getattr(
                input_socket,
                "is_linked",
                False,
            )
        ):
            continue

        for link in getattr(
            input_socket,
            "links",
            [],
        ):
            from_node = getattr(
                link,
                "from_node",
                None,
            )

            if from_node is None:
                continue

            collect_upstream_nodes(
                node=from_node,
                connected_nodes=connected_nodes,
            )


def get_input_links(node):
    """
    Returns all links connected to a node's input sockets.

    Returns:
        list[bpy.types.NodeLink]
    """
    links = []

    if node is None:
        return links

    for input_socket in getattr(
        node,
        "inputs",
        [],
    ):
        for link in getattr(
            input_socket,
            "links",
            [],
        ):
            links.append(
                link
            )

    return links


# -------------------------------------------------------------------------
# Output helpers
# -------------------------------------------------------------------------

def get_material_output_nodes(
        node_tree,
        active_only=True,
    ):
    """
    Gets Material Output nodes from a shader node tree.

    If active_only is enabled but no output node is marked active, all
    Material Output nodes are returned as a fallback. This avoids false
    failures in files where Blender has no explicit active flag.

    Args:
        node_tree (bpy.types.NodeTree):
            Material shader node tree.

        active_only (bool):
            Whether to prefer active outputs.

    Returns:
        list[bpy.types.Node]
    """
    if node_tree is None:
        return []

    output_nodes = [
        node
        for node in node_tree.nodes
        if node.type == "OUTPUT_MATERIAL"
    ]

    if not active_only:
        return output_nodes

    active_outputs = [
        node
        for node in output_nodes
        if bool(
            getattr(
                node,
                "is_active_output",
                False,
            )
        )
    ]

    if active_outputs:
        return active_outputs

    return output_nodes


# -------------------------------------------------------------------------
# Node filtering
# -------------------------------------------------------------------------

def should_ignore_node(
        node,
        connected_nodes,
        settings,
    ):
    """
    Determines whether a disconnected node should be excluded from the
    report.

    Frame nodes receive special handling. A frame is considered connected
    when one or more child nodes contribute to the material output.

    Returns:
        bool
    """
    if node is None:
        return True

    if (
        settings["ignore_muted_nodes"]
        and bool(
            getattr(
                node,
                "mute",
                False,
            )
        )
    ):
        return True

    if (
        settings["ignore_reroutes"]
        and node.type == "REROUTE"
    ):
        return True

    if node.type == "FRAME":
        if settings["ignore_frames"]:
            return True

        for child_node in getattr(
            node.id_data,
            "nodes",
            [],
        ):
            if child_node.parent == node:
                if child_node in connected_nodes:
                    return True

    return False


def serialize_node(node):
    """
    Converts a shader node into QC result data.

    Returns:
        dict
    """
    return {
        "node_name": node.name,
        "node_label": node.label,
        "node_type": node.type,
        "bl_idname": node.bl_idname,
        "muted": bool(
            getattr(
                node,
                "mute",
                False,
            )
        ),
        "location": [
            float(node.location.x),
            float(node.location.y),
        ],
        "parent_frame": (
            node.parent.name
            if node.parent is not None
            else None
        ),
    }


# -------------------------------------------------------------------------
# Material and object helpers
# -------------------------------------------------------------------------

def get_scene_materials(scene=None):
    """
    Returns all unique materials assigned to objects in the scene.

    Returns:
        list[bpy.types.Material]
    """
    if scene is None:
        scene = bpy.context.scene

    materials = []
    seen_materials = set()

    for obj in scene.objects:

        if obj.library is not None:
            continue

        for material_slot in getattr(
            obj,
            "material_slots",
            [],
        ):
            material = getattr(
                material_slot,
                "material",
                None,
            )

            if material is None:
                continue

            if material.library is not None:
                continue

            try:
                material_pointer = material.as_pointer()
            except Exception:
                material_pointer = id(material)

            if material_pointer in seen_materials:
                continue

            seen_materials.add(
                material_pointer
            )

            materials.append(
                material
            )

    return materials


def get_objects_using_failed_materials(
        failed_materials,
        scene=None,
    ):
    """
    Builds an object-based result dictionary for viewport selection and
    object-mode QC display.

    Args:
        failed_materials (dict):
            Results from get_materials_with_unconnected_nodes().

        scene (bpy.types.Scene | None):
            Scene to inspect.

    Returns:
        dict
    """
    if scene is None:
        scene = bpy.context.scene

    if not isinstance(
        failed_materials,
        dict,
    ):
        return {}

    failed_material_names = set(
        failed_materials.keys()
    )

    failed_objects = {}

    for obj in scene.objects:

        if obj.library is not None:
            continue

        object_materials = []

        for slot_index, material_slot in enumerate(
            getattr(
                obj,
                "material_slots",
                [],
            )
        ):
            material = getattr(
                material_slot,
                "material",
                None,
            )

            if material is None:
                continue

            if material.library is not None:
                continue

            if material.name not in failed_material_names:
                continue

            material_data = failed_materials[
                material.name
            ]

            object_materials.append({
                "slot_index": slot_index,
                "material_name": material.name,
                "unconnected_node_count": material_data.get(
                    "unconnected_node_count",
                    0,
                ),
                "missing_output": material_data.get(
                    "missing_output",
                    False,
                ),
                "disconnected_output": material_data.get(
                    "disconnected_output",
                    False,
                ),
            })

        if not object_materials:
            continue

        failed_objects[obj.name] = {
            "object_type": obj.type,
            "material_count": len(
                object_materials
            ),
            "materials": object_materials,
        }

    return failed_objects
