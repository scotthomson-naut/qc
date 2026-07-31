# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Color Space Valid"
DESCRIPTION = (
    "Checks image textures used as normal, roughness, metallic, height, "
    "displacement, masks, or other non-color data and verifies that their "
    "image color space is set to Non-Color."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "required_colorspace": {
        "type": "string",
        "label": "Required Colorspace",
        "description": (
            "Required image color space for textures used as non-color data."
        ),
        "default": "Non-Color",
    },

    "check_normal": {
        "type": "bool",
        "label": "Check Normal Textures",
        "default": True,
    },

    "check_roughness": {
        "type": "bool",
        "label": "Check Roughness Textures",
        "default": True,
    },

    "check_metallic": {
        "type": "bool",
        "label": "Check Metallic Textures",
        "default": True,
    },

    "check_height": {
        "type": "bool",
        "label": "Check Height and Displacement",
        "default": True,
    },

    "check_masks": {
        "type": "bool",
        "label": "Check Masks and Data Values",
        "default": True,
    },

    "skip_mixed_usage_on_fix": {
        "type": "bool",
        "label": "Do Not Fix Mixed-Usage Images",
        "description": (
            "Do not automatically change images that are used for both "
            "color and non-color purposes."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds image textures used as non-color data that are not configured
    with the required color space.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "failed_materials": dict,
            "failed_images": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(preferences)

    analysis = analyze_scene_texture_usage(
        settings=settings,
    )

    failed_images = analysis["failed_images"]
    failed_materials = build_failed_materials(
        failed_images=failed_images,
    )
    failed_objects = build_failed_objects(
        failed_materials=failed_materials,
    )

    issues = []

    for image_name, image_data in sorted(
        failed_images.items()
    ):
        usages = sorted(
            set(image_data.get("non_color_usages", []))
        )

        material_names = sorted(
            set(
                usage["material_name"]
                for usage in image_data.get("usages", [])
            )
        )

        message = (
            'Image "{}" is used as {} but its color space is "{}"; '
            'expected "{}". Materials: {}.'
        ).format(
            image_name,
            ", ".join(usages),
            image_data.get("current_colorspace", "Unknown"),
            image_data.get("required_colorspace", "Non-Color"),
            ", ".join(material_names),
        )

        if image_data.get("mixed_usage"):
            message += (
                " The image is also used as color data, so changing its "
                "global image color space may affect other materials."
            )

        issues.append(message)

    return {
        "issues": issues,
        "failed_objects": failed_objects,
        "failed_materials": failed_materials,
        "failed_images": failed_images,
        "settings": settings,
    }


def fix(result_data=None, preferences=None):
    """
    Changes mismatched image datablocks to the required non-color space.

    Mixed-use images are skipped by default.

    Returns:
        dict:
        {
            "fixed_images": dict,
            "fixed_materials": dict,
            "fixed_objects": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(preferences)

    return fix_texture_colorspaces(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def build_failed_objects(failed_materials, scene=None):
    """
    Finds scene objects using materials with color-space mismatches.
    """
    if scene is None:
        scene = bpy.context.scene

    failed_objects = {}

    for obj in scene.objects:
        material_results = []

        for slot_index, slot in enumerate(
            getattr(obj, "material_slots", [])
        ):
            material = getattr(slot, "material", None)

            if material is None:
                continue

            if material.name not in failed_materials:
                continue

            material_data = failed_materials[
                material.name
            ]

            material_results.append({
                "slot_index": slot_index,
                "material_name": material.name,
                "image_count": material_data[
                    "image_count"
                ],
                "images": material_data[
                    "images"
                ],
            })

        if material_results:
            failed_objects[obj.name] = {
                "object_type": obj.type,
                "material_count": len(
                    material_results
                ),
                "materials": material_results,
            }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_texture_colorspaces(
        result_data=None,
        settings=None,
    ):
    """
    Corrects mismatched image color spaces.

    Since color space belongs to the image datablock rather than an
    individual Image Texture node, changing it affects every user of that
    image.
    """
    if settings is None:
        settings = resolve_settings()

    if not isinstance(result_data, dict):
        result_data = {}

    failed_images = result_data.get(
        "failed_images",
        {},
    )

    if not isinstance(failed_images, dict):
        failed_images = {}

    required_colorspace = settings[
        "required_colorspace"
    ]

    skip_mixed = settings[
        "skip_mixed_usage_on_fix"
    ]

    fixed_images = {}
    issues = []

    for image_name, previous_data in failed_images.items():
        image = bpy.data.images.get(image_name)

        if image is None:
            issues.append(
                'Image "{}" no longer exists.'.format(
                    image_name
                )
            )
            continue

        # Reanalyze the current scene instead of relying only on stale data.
        current_result = analyze_single_image_usage(
            image=image,
            settings=settings,
        )

        if current_result is None:
            continue

        current_colorspace = get_image_colorspace(
            image
        )

        if colorspace_matches(
            current=current_colorspace,
            required=required_colorspace,
        ):
            continue

        if (
            current_result["mixed_usage"]
            and skip_mixed
        ):
            issues.append(
                (
                    'Image "{}" was not changed because it is used '
                    "for both color and non-color data."
                ).format(image_name)
            )
            continue

        try:
            previous_colorspace = current_colorspace

            image.colorspace_settings.name = (
                required_colorspace
            )

        except Exception as error:
            issues.append(
                (
                    'Could not set image "{}" to color space "{}": {}'
                ).format(
                    image_name,
                    required_colorspace,
                    error,
                )
            )
            continue

        fixed_images[image_name] = {
            "previous_colorspace": previous_colorspace,
            "current_colorspace": get_image_colorspace(
                image
            ),
            "non_color_usages": current_result[
                "non_color_usages"
            ],
            "color_usages": current_result[
                "color_usages"
            ],
            "mixed_usage": current_result[
                "mixed_usage"
            ],
        }

    current_analysis = analyze_scene_texture_usage(
        settings=settings,
    )

    current_failed_materials = build_failed_materials(
        current_analysis["failed_images"]
    )

    fixed_materials = {}
    fixed_objects = {}

    for image_name in fixed_images:
        previous_image_data = failed_images.get(
            image_name,
            {},
        )

        material_names = sorted(
            set(
                usage["material_name"]
                for usage in previous_image_data.get(
                    "usages",
                    []
                )
            )
        )

        for material_name in material_names:
            fixed_materials.setdefault(
                material_name,
                {
                    "fixed_images": [],
                },
            )

            fixed_materials[
                material_name
            ]["fixed_images"].append(
                image_name
            )

    for obj in bpy.context.scene.objects:
        fixed_object_materials = []

        for slot_index, slot in enumerate(
            getattr(obj, "material_slots", [])
        ):
            material = getattr(
                slot,
                "material",
                None,
            )

            if (
                material is None
                or material.name not in fixed_materials
            ):
                continue

            fixed_object_materials.append({
                "slot_index": slot_index,
                "material_name": material.name,
                "fixed_images": fixed_materials[
                    material.name
                ]["fixed_images"],
            })

        if fixed_object_materials:
            fixed_objects[obj.name] = {
                "materials": fixed_object_materials,
            }

    return {
        "fixed_images": fixed_images,
        "fixed_materials": fixed_materials,
        "fixed_objects": fixed_objects,
        "issues": issues,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def resolve_settings(preferences=None):
    """
    Merges saved preferences over the check defaults.
    """
    resolved = {
        setting_name: definition.get("default")
        for setting_name, definition
        in SETTINGS.items()
    }

    if isinstance(preferences, dict):
        for setting_name, value in preferences.items():
            if setting_name in resolved:
                resolved[setting_name] = value

    return resolved


def analyze_scene_texture_usage(settings=None):
    """
    Examines materials assigned to objects in the current scene.

    Each Image Texture node is traced forward through the node tree to
    determine whether it contributes to color data, non-color data, or both.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings()

    image_usage = {}

    for material in get_scene_materials():
        if not material.use_nodes:
            continue

        node_tree = material.node_tree

        if node_tree is None:
            continue

        for node in node_tree.nodes:
            if node.type != "TEX_IMAGE":
                continue

            image = getattr(node, "image", None)

            if image is None:
                continue

            node_usage = classify_image_texture_usage(
                node=node,
                settings=settings,
            )

            if not node_usage["non_color_usages"]:
                continue

            image_key = get_datablock_key(image)

            if image_key not in image_usage:
                image_usage[image_key] = {
                    "image": image,
                    "image_name": image.name,
                    "filepath": image.filepath,
                    "current_colorspace": get_image_colorspace(image),
                    "required_colorspace": settings[
                        "required_colorspace"
                    ],
                    "non_color_usages": set(),
                    "color_usages": set(),
                    "usages": [],
                }

            record = image_usage[image_key]

            record["non_color_usages"].update(
                node_usage["non_color_usages"]
            )
            record["color_usages"].update(
                node_usage["color_usages"]
            )

            record["usages"].append({
                "material_name": material.name,
                "node_name": node.name,
                "node_label": node.label,
                "non_color_usages": sorted(
                    node_usage["non_color_usages"]
                ),
                "color_usages": sorted(
                    node_usage["color_usages"]
                ),
            })

    failed_images = {}

    required_colorspace = settings["required_colorspace"]

    for record in image_usage.values():
        image = record.pop("image")

        current_colorspace = get_image_colorspace(image)

        if colorspace_matches(
            current=current_colorspace,
            required=required_colorspace,
        ):
            continue

        record["current_colorspace"] = current_colorspace
        record["non_color_usages"] = sorted(
            record["non_color_usages"]
        )
        record["color_usages"] = sorted(
            record["color_usages"]
        )
        record["mixed_usage"] = bool(
            record["non_color_usages"]
            and record["color_usages"]
        )

        failed_images[image.name] = record

    return {
        "failed_images": failed_images,
    }


# -------------------------------------------------------------------------
# Usage classification
# -------------------------------------------------------------------------

def classify_image_texture_usage(node, settings=None):
    """
    Traces links forward from an Image Texture node.

    Returns:
        dict:
        {
            "non_color_usages": set[str],
            "color_usages": set[str],
        }
    """
    if settings is None:
        settings = resolve_settings()

    result = {
        "non_color_usages": set(),
        "color_usages": set(),
    }

    visited = set()

    for output_socket in node.outputs:
        for link in output_socket.links:
            trace_socket_usage(
                node=link.to_node,
                input_socket=link.to_socket,
                settings=settings,
                result=result,
                visited=visited,
            )

    return result


def trace_socket_usage(
        node,
        input_socket,
        settings,
        result,
        visited,
    ):
    """
    Traces a node graph forward and classifies the final usage.

    The visited key includes the node and destination socket so a node can
    still be analyzed through separate inputs.
    """
    if node is None or input_socket is None:
        return

    key = (
        get_datablock_key(node),
        getattr(input_socket, "identifier", input_socket.name),
    )

    if key in visited:
        return

    visited.add(key)

    usage = classify_destination_socket(
        node=node,
        socket=input_socket,
        settings=settings,
    )

    if usage is not None:
        usage_type, usage_name = usage

        if usage_type == "NON_COLOR":
            result["non_color_usages"].add(usage_name)
        elif usage_type == "COLOR":
            result["color_usages"].add(usage_name)

    # Continue through this node's outputs. This allows the check to trace
    # through Mix, Math, Separate Color, Color Ramp, Reroute and node groups.
    for output_socket in getattr(node, "outputs", []):
        for link in getattr(output_socket, "links", []):
            trace_socket_usage(
                node=link.to_node,
                input_socket=link.to_socket,
                settings=settings,
                result=result,
                visited=visited,
            )


def classify_destination_socket(node, socket, settings):
    """
    Classifies a destination socket as color, non-color, or unknown.

    Returns:
        tuple[str, str] | None
    """
    node_type = getattr(node, "type", "")
    socket_name = normalize_name(
        getattr(socket, "name", "")
    )

    # ------------------------------------------------------------------
    # Dedicated normal and bump nodes
    # ------------------------------------------------------------------

    if node_type == "NORMAL_MAP":
        if settings["check_normal"] and socket_name in {
            "color",
            "strength",
        }:
            return "NON_COLOR", "Normal"

    if node_type == "BUMP":
        if settings["check_height"] and socket_name in {
            "height",
            "distance",
            "strength",
        }:
            return "NON_COLOR", "Height/Bump"

        if settings["check_normal"] and socket_name == "normal":
            return "NON_COLOR", "Normal"

    # ------------------------------------------------------------------
    # Principled and other shader inputs
    # ------------------------------------------------------------------

    if settings["check_roughness"] and is_roughness_socket(
        socket_name
    ):
        return "NON_COLOR", "Roughness"

    if settings["check_metallic"] and is_metallic_socket(
        socket_name
    ):
        return "NON_COLOR", "Metallic"

    if settings["check_normal"] and is_normal_socket(
        socket_name
    ):
        return "NON_COLOR", "Normal"

    if settings["check_height"] and is_height_socket(
        socket_name
    ):
        return "NON_COLOR", "Height/Displacement"

    if settings["check_masks"] and is_mask_or_data_socket(
        node=node,
        socket_name=socket_name,
    ):
        return "NON_COLOR", get_data_usage_label(
            socket_name
        )

    # ------------------------------------------------------------------
    # Material Output
    # ------------------------------------------------------------------

    if node_type == "OUTPUT_MATERIAL":
        if socket_name == "displacement" and settings["check_height"]:
            return "NON_COLOR", "Displacement"

        if socket_name in {
            "surface",
            "volume",
        }:
            return "COLOR", "Shader Color"

    # ------------------------------------------------------------------
    # Clearly color-based shader inputs
    # ------------------------------------------------------------------

    if is_color_socket(
        node=node,
        socket_name=socket_name,
    ):
        return "COLOR", get_color_usage_label(
            socket_name
        )

    return None


# -------------------------------------------------------------------------
# Socket rules
# -------------------------------------------------------------------------

def is_roughness_socket(socket_name):
    return socket_name in {
        "roughness",
        "coat roughness",
        "clearcoat roughness",
        "transmission roughness",
        "sheen roughness",
        "anisotropic roughness",
    }


def is_metallic_socket(socket_name):
    return socket_name in {
        "metallic",
        "metalness",
    }


def is_normal_socket(socket_name):
    return socket_name in {
        "normal",
        "tangent",
        "clearcoat normal",
        "coat normal",
    }


def is_height_socket(socket_name):
    return socket_name in {
        "height",
        "distance",
        "displacement",
        "scale",
        "midlevel",
    }


def is_mask_or_data_socket(node, socket_name):
    non_color_names = {
        "alpha",
        "fac",
        "factor",
        "weight",
        "value",
        "ior",
        "specular ior level",
        "specular",
        "anisotropic",
        "anisotropy",
        "rotation",
        "density",
        "thickness",
        "occlusion",
        "ambient occlusion",
        "ao",
        "mask",
        "opacity",
        "subsurface weight",
        "transmission weight",
        "coat weight",
        "sheen weight",
        "emission strength",
    }

    if socket_name in non_color_names:
        return True

    node_type = getattr(node, "type", "")

    # Math inputs represent scalar data.
    if node_type == "MATH":
        return True

    # Vector Math normally represents vectors/data rather than display color.
    if node_type == "VECT_MATH":
        return True

    # Displacement nodes expect scalar height values.
    if node_type == "DISPLACEMENT":
        return True

    return False


def is_color_socket(node, socket_name):
    color_names = {
        "base color",
        "color",
        "emission color",
        "emission",
        "subsurface radius",
        "subsurface color",
        "coat tint",
        "sheen tint",
        "transmission color",
    }

    if socket_name not in color_names:
        return False

    node_type = getattr(node, "type", "")

    # These nodes can process either color or data. Do not finalize their
    # classification here; traversal should continue to their destination.
    passthrough_types = {
        "MIX",
        "MIX_RGB",
        "VALTORGB",
        "SEPRGB",
        "COMBRGB",
        "SEPARATE_COLOR",
        "COMBINE_COLOR",
        "REROUTE",
        "GROUP",
    }

    return node_type not in passthrough_types


def get_data_usage_label(socket_name):
    labels = {
        "alpha": "Alpha",
        "opacity": "Opacity",
        "mask": "Mask",
        "ambient occlusion": "Ambient Occlusion",
        "occlusion": "Ambient Occlusion",
        "ao": "Ambient Occlusion",
        "fac": "Factor/Mask",
        "factor": "Factor/Mask",
        "weight": "Weight/Mask",
        "value": "Scalar Data",
    }

    return labels.get(
        socket_name,
        "Non-Color Data",
    )


def get_color_usage_label(socket_name):
    labels = {
        "base color": "Base Color",
        "emission": "Emission Color",
        "emission color": "Emission Color",
        "subsurface color": "Subsurface Color",
        "coat tint": "Coat Tint",
        "sheen tint": "Sheen Tint",
    }

    return labels.get(
        socket_name,
        "Color",
    )


# -------------------------------------------------------------------------
# Result building
# -------------------------------------------------------------------------

def build_failed_materials(failed_images):
    """
    Converts image-based results into material-based results.
    """
    failed_materials = {}

    for image_name, image_data in failed_images.items():
        for usage in image_data.get("usages", []):
            material_name = usage["material_name"]

            material_result = failed_materials.setdefault(
                material_name,
                {
                    "material_name": material_name,
                    "image_count": 0,
                    "images": [],
                },
            )

            material_result["images"].append({
                "image_name": image_name,
                "node_name": usage["node_name"],
                "node_label": usage["node_label"],
                "current_colorspace": image_data[
                    "current_colorspace"
                ],
                "required_colorspace": image_data[
                    "required_colorspace"
                ],
                "non_color_usages": usage[
                    "non_color_usages"
                ],
                "color_usages": usage[
                    "color_usages"
                ],
                "mixed_usage": image_data[
                    "mixed_usage"
                ],
            })

    for material_data in failed_materials.values():
        material_data["image_count"] = len(
            material_data["images"]
        )

    return failed_materials


def analyze_single_image_usage(image, settings=None):
    """
    Rechecks all scene Image Texture nodes using one image.
    """
    if settings is None:
        settings = resolve_settings()

    non_color_usages = set()
    color_usages = set()

    for material in get_scene_materials():
        if not material.use_nodes or material.node_tree is None:
            continue

        for node in material.node_tree.nodes:
            if node.type != "TEX_IMAGE":
                continue

            if node.image != image:
                continue

            usage = classify_image_texture_usage(
                node=node,
                settings=settings,
            )

            non_color_usages.update(
                usage["non_color_usages"]
            )
            color_usages.update(
                usage["color_usages"]
            )

    if not non_color_usages:
        return None

    return {
        "non_color_usages": sorted(
            non_color_usages
        ),
        "color_usages": sorted(
            color_usages
        ),
        "mixed_usage": bool(
            non_color_usages and color_usages
        ),
    }


def get_scene_materials(scene=None):
    """
    Returns unique materials assigned to objects in the current scene.
    """
    if scene is None:
        scene = bpy.context.scene

    materials = []
    seen = set()

    for obj in scene.objects:
        for slot in getattr(
            obj,
            "material_slots",
            [],
        ):
            material = getattr(
                slot,
                "material",
                None,
            )

            if material is None:
                continue

            key = get_datablock_key(material)

            if key in seen:
                continue

            seen.add(key)
            materials.append(material)

    return materials


def get_image_colorspace(image):
    try:
        return image.colorspace_settings.name
    except Exception:
        return "Unknown"


def colorspace_matches(current, required):
    """
    Handles minor naming variations such as Non-Color and Non-Colour.
    """
    current = normalize_name(current).replace(
        "colour",
        "color",
    )
    required = normalize_name(required).replace(
        "colour",
        "color",
    )

    return current == required


def normalize_name(value):
    return " ".join(
        str(value).strip().lower().replace(
            "_",
            " ",
        ).split()
    )


def get_datablock_key(datablock):
    try:
        return datablock.as_pointer()
    except Exception:
        return id(datablock)
