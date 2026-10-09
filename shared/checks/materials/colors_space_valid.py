# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "Color Space Valid"
DESCRIPTION = (
    'Checks image textures used as normal, roughness, metallic, height, '
    'displacement, masks, or other non-color data and verifies that their '
    'image color space is set to non-color data. Also checks image textures '
    'used purely as color (Base Color, Emission Color, etc.) and verifies '
    'they are not set to Non-Color. Images used '
    'for both color and non-color purposes are skipped by default because one '
    'global image color-space setting cannot be correct for both uses.'
)
WHY = (
    'Prevents color-management transforms such as sRGB gamma from altering '
    'numeric texture data used by shader calculations. It also prevents color '
    'textures set to Non-Color from rendering with incorrect colors '
    '(typically washed out).'
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
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

    "report_mixed_usage": {
        "type": "bool",
        "label": "Report Mixed-Usage Images",
        "description": (
            "Report images that are used for both color and non-color data. "
            "These require manual material review because one global image "
            "color-space setting cannot be correct for both uses."
        ),
        "default": False,
    },

    "skip_mixed_usage_on_fix": {
        "type": "bool",
        "label": "Do Not Fix Mixed-Usage Images",
        "description": (
            "When mixed-usage reporting is enabled, do not automatically "
            "change images that are used for both color and non-color purposes."
        ),
        "default": True,
    },
}

# Shown in results as the expected state. The check itself relies on
# Blender's "is_data" flag, so it works with any OCIO config regardless of
# what that config names its non-color / data space.
REQUIRED_COLORSPACE_LABEL = "Non-Color (data)"

# Color space expected for images used purely as color. A color texture only
# fails when it is marked as data (Non-Color); other color spaces such as
# Linear Rec.709 are left alone because they can be legitimate for HDR color.
COLOR_COLORSPACE_NAME = "sRGB"


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds image textures used as non-color data that are not configured as
    data, and image textures used exclusively as color that are configured
    as non-color data.

    Images used for both color and non-color purposes are ignored by default
    because there is no single globally correct image color space for both
    uses. They can optionally be reported for manual review.

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
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    analysis = analyze_scene_texture_usage(
        settings=settings,
    )

    failed_images = analysis[
        "failed_images"
    ]

    auto_fixable_images = [
        image_name
        for image_name, image_data
        in failed_images.items()
        if not (
            image_data.get(
                "mixed_usage",
                False,
            )
            and settings[
                "skip_mixed_usage_on_fix"
            ]
        )
    ]

    failed_materials = build_failed_materials(
        failed_images=failed_images,
    )

    failed_objects = get_failed_colorspace_objects(
        failed_materials=failed_materials,
    )

    issues = []

    for image_name, image_data in sorted(
        failed_images.items()
    ):
        usage_key = (
            "color_usages"
            if image_data.get(
                "failure_kind"
            ) == "color"
            else "non_color_usages"
        )

        usages = sorted(
            set(
                image_data.get(
                    usage_key,
                    [],
                )
            )
        )

        material_names = sorted(
            set(
                usage[
                    "material_name"
                ]
                for usage in image_data.get(
                    "usages",
                    [],
                )
            )
        )

        message = (
            'Image "{}" is used as {} but its color space is "{}"; '
            'expected "{}". Materials: {}.'
        ).format(
            image_name,
            ", ".join(
                usages
            ),
            image_data.get(
                "current_colorspace",
                "Unknown",
            ),
            image_data.get(
                "required_colorspace",
                "Non-Color",
            ),
            ", ".join(
                material_names
            ),
        )

        if image_data.get(
            "mixed_usage"
        ):
            color_places = get_usage_locations(
                image_data,
                color=True,
            )

            message += (
                " The image is also used as color data{}. No single global "
                "image color-space setting is correct for both uses; manual "
                "material/node-tree review is required."
            ).format(
                " ({})".format(
                    ", ".join(
                        color_places
                    )
                )
                if color_places
                else ""
            )

        issues.append(
            message
        )

    return {
        "issues":
            issues,

        "failed_objects":
            failed_objects,

        "failed_materials":
            failed_materials,

        "failed_images":
            failed_images,

        "settings":
            settings,

        "can_auto_fix":
            bool(
                auto_fixable_images
            ),
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Sets failed images to the required color space where safe.

    Returns:
        dict
    """
    return fix_color_space(
        result_data=result_data,
        preferences=preferences,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_failed_colorspace_objects(
        failed_materials,
        scene=None,
    ):
    """
    Finds scene objects using materials with color-space mismatches.
    """
    if scene is None:
        scene = bpy.context.scene

    failed_objects = {}

    for obj in get_qc_objects(
        scene.objects
    ):

        if obj.library is not None:
            continue

        material_results = []

        for slot_index, slot in enumerate(
            getattr(
                obj,
                "material_slots",
                [],
            )
        ):
            material = getattr(
                slot,
                "material",
                None,
            )

            if material is None:
                continue

            if (
                material.name
                not in failed_materials
            ):
                continue

            material_data = (
                failed_materials[
                    material.name
                ]
            )

            material_results.append({
                "slot_index":
                    slot_index,

                "material_name":
                    material.name,

                "image_count":
                    material_data[
                        "image_count"
                    ],

                "images":
                    material_data[
                        "images"
                    ],
            })

        if material_results:
            failed_objects[
                obj.name
            ] = {
                "object_type":
                    obj.type,

                "material_count":
                    len(
                        material_results
                    ),

                "materials":
                    material_results,
            }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_color_space(
        result_data=None,
        preferences=None,
    ):
    """
    Sets failed non-color images to the required color space.

    Images used for both color and non-color data are skipped when
    skip_mixed_usage_on_fix is enabled.

    Returns:
        dict:
        {
            "issues": list[str],
            "fixed_images": dict,
            "skipped_images": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    if not isinstance(
        result_data,
        dict,
    ):
        result_data = {}

    failed_images = result_data.get(
        "failed_images",
        {},
    )

    fixed_images = {}
    skipped_images = {}
    issues = []

    for image_name, image_data in (
        failed_images.items()
    ):

        image = bpy.data.images.get(
            image_name
        )

        if image is None:
            issues.append(
                'Image "{}" no longer exists.'.format(
                    image_name
                )
            )
            continue

        if image.library is not None:
            continue

        # -----------------------------------------------------
        # Mixed color / non-color usage
        # -----------------------------------------------------

        if (
            image_data.get(
                "mixed_usage",
                False,
            )
            and settings[
                "skip_mixed_usage_on_fix"
            ]
        ):
            skipped_images[
                image_name
            ] = {
                "reason": (
                    "Image is used for both color and "
                    "non-color data."
                ),

                "current_colorspace":
                    get_image_colorspace(
                        image
                    ),

                "required_colorspace":
                    REQUIRED_COLORSPACE_LABEL,
            }

            continue

        # -----------------------------------------------------
        # Set color space
        # -----------------------------------------------------

        old_colorspace = (
            get_image_colorspace(
                image
            )
        )

        set_color_space = (
            set_image_as_color
            if image_data.get(
                "failure_kind"
            ) == "color"
            else set_image_as_data
        )

        try:
            success = set_color_space(
                image
            )

        except Exception as error:
            issues.append(
                (
                    'Could not set color space for image "{}": {}'
                ).format(
                    image_name,
                    error,
                )
            )
            continue

        if not success:
            issues.append(
                (
                    'Could not set the color space of image "{}" to "{}".'
                ).format(
                    image_name,
                    image_data.get(
                        "required_colorspace",
                        REQUIRED_COLORSPACE_LABEL,
                    ),
                )
            )
            continue

        fixed_images[
            image_name
        ] = {
            "old_colorspace":
                old_colorspace,

            "new_colorspace":
                get_image_colorspace(
                    image
                ),
        }

    return {
        "issues":
            issues,

        "fixed_images":
            fixed_images,

        "skipped_images":
            skipped_images,
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def analyze_scene_texture_usage(
        settings=None,
    ):
    """
    Examines materials assigned to objects in the current scene.

    Each Image Texture node is traced forward through the node tree to
    determine whether it contributes to color data, non-color data, or both.

    Genuine mixed-use images are excluded from failures by default. Set
    report_mixed_usage=True to include them for manual review.

    Returns:
        dict
    """
    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

    image_usage = {}

    for material in get_scene_materials():

        if not material.use_nodes:
            continue

        node_tree = (
            material.node_tree
        )

        if node_tree is None:
            continue

        for node in node_tree.nodes:

            if node.type != "TEX_IMAGE":
                continue

            image = getattr(
                node,
                "image",
                None,
            )

            if image is None:
                continue

            if image.library is not None:
                continue

            node_usage = (
                classify_image_texture_usage(
                    node=node,
                    settings=settings,
                )
            )

            if not (
                node_usage[
                    "non_color_usages"
                ]
                or node_usage[
                    "color_usages"
                ]
            ):
                continue

            image_key = (
                get_datablock_key(
                    image
                )
            )

            if image_key not in image_usage:

                image_usage[
                    image_key
                ] = {
                    "image":
                        image,

                    "image_name":
                        image.name,

                    "filepath":
                        image.filepath,

                    "current_colorspace":
                        get_image_colorspace(
                            image
                        ),

                    "required_colorspace":
                        REQUIRED_COLORSPACE_LABEL,

                    "non_color_usages":
                        set(),

                    "color_usages":
                        set(),

                    "usages":
                        [],
                }

            record = image_usage[
                image_key
            ]

            record[
                "non_color_usages"
            ].update(
                node_usage[
                    "non_color_usages"
                ]
            )

            record[
                "color_usages"
            ].update(
                node_usage[
                    "color_usages"
                ]
            )

            record[
                "usages"
            ].append({
                "material_name":
                    material.name,

                "node_name":
                    node.name,

                "node_label":
                    node.label,

                "non_color_usages":
                    sorted(
                        node_usage[
                            "non_color_usages"
                        ]
                    ),

                "color_usages":
                    sorted(
                        node_usage[
                            "color_usages"
                        ]
                    ),
            })

    failed_images = {}

    for record in image_usage.values():

        image = record.pop(
            "image"
        )

        current_colorspace = (
            get_image_colorspace(
                image
            )
        )

        if record[
            "non_color_usages"
        ]:
            # Used as non-color data (alone, or mixed with color use).
            if is_image_data(
                image
            ):
                continue

            record[
                "failure_kind"
            ] = "non_color"

        else:
            # Used purely as color.
            if not is_image_data(
                image
            ):
                continue

            record[
                "failure_kind"
            ] = "color"

            record[
                "required_colorspace"
            ] = COLOR_COLORSPACE_NAME

        record[
            "current_colorspace"
        ] = current_colorspace

        record[
            "non_color_usages"
        ] = sorted(
            record[
                "non_color_usages"
            ]
        )

        record[
            "color_usages"
        ] = sorted(
            record[
                "color_usages"
            ]
        )

        record[
            "mixed_usage"
        ] = bool(
            record[
                "non_color_usages"
            ]
            and record[
                "color_usages"
            ]
        )

        # A Blender Image datablock has one global color-space setting.
        # Genuine mixed-use images therefore have no single automatically
        # correct value. Ignore them by default and only surface them when
        # the user explicitly enables Report Mixed-Usage Images.
        if (
            record[
                "mixed_usage"
            ]
            and not settings.get(
                "report_mixed_usage",
                False,
            )
        ):
            continue

        failed_images[
            image.name
        ] = record

    return {
        "failed_images":
            failed_images,
    }


# -------------------------------------------------------------------------
# Usage classification
# -------------------------------------------------------------------------

def classify_image_texture_usage(
        node,
        settings=None,
    ):
    """
    Traces links forward from an Image Texture node.

    Separate links from the same Image Texture are traced independently.
    Therefore a texture genuinely used both as Base Color and as a mask/data
    input is still classified as mixed usage.

    Returns:
        dict:
        {
            "non_color_usages": set[str],
            "color_usages": set[str],
        }
    """
    if settings is None:
        settings = resolve_settings(
            SETTINGS
        )

    result = {
        "non_color_usages":
            set(),

        "color_usages":
            set(),
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
    Traces one image path forward and classifies its semantic usage.

    Once a destination socket establishes a meaningful usage such as Base
    Color, Roughness, Normal, Mask/Factor, etc., traversal stops for THAT
    path. This prevents a non-color mask from being incorrectly reclassified
    as color merely because the downstream shader eventually connects to
    Material Output / Surface.

    Separate links from the original Image Texture are still traced
    independently, so genuine mixed usage is preserved.
    """
    if (
        node is None
        or input_socket is None
    ):
        return

    key = (
        get_datablock_key(
            node
        ),
        getattr(
            input_socket,
            "identifier",
            input_socket.name,
        ),
    )

    if key in visited:
        return

    visited.add(
        key
    )

    usage = (
        classify_destination_socket(
            node=node,
            socket=input_socket,
            settings=settings,
        )
    )

    if usage is not None:

        usage_type, usage_name = (
            usage
        )

        if usage_type == "NON_COLOR":
            result[
                "non_color_usages"
            ].add(
                usage_name
            )

        elif usage_type == "COLOR":
            result[
                "color_usages"
            ].add(
                usage_name
            )

        # The semantic purpose of this path is now known.
        # Do not continue through the entire downstream shader graph.
        return

    # Continue only through nodes whose current input did not itself define
    # a semantic color/non-color purpose.
    for output_socket in getattr(
        node,
        "outputs",
        [],
    ):
        for link in getattr(
            output_socket,
            "links",
            [],
        ):
            trace_socket_usage(
                node=link.to_node,
                input_socket=link.to_socket,
                settings=settings,
                result=result,
                visited=visited,
            )


def classify_destination_socket(
        node,
        socket,
        settings,
    ):
    """
    Classifies a destination socket as color, non-color, or unknown.

    Returns:
        tuple[str, str] | None
    """
    node_type = getattr(
        node,
        "type",
        "",
    )

    socket_name = normalize_name(
        getattr(
            socket,
            "name",
            "",
        )
    )

    # ------------------------------------------------------------------
    # Intermediate processing nodes
    # ------------------------------------------------------------------
    #
    # Color Ramp, Math, Map Range, Mix (color inputs), etc. only transform
    # a value on its way to somewhere else. Their input sockets (Fac, Value,
    # Color...) do NOT describe what the image is used for, so classifying
    # by socket name here wrongly labeled color textures as masks (for
    # example a Base Color texture routed through a Color Ramp "Fac" input).
    # Return None so the trace keeps following the links and the final
    # destination decides the usage.

    if is_passthrough_input(
        node=node,
        socket_name=socket_name,
    ):
        return None

    # ------------------------------------------------------------------
    # Dedicated normal and bump nodes
    # ------------------------------------------------------------------

    if node_type == "NORMAL_MAP":

        if (
            settings[
                "check_normal"
            ]
            and socket_name in {
                "color",
                "strength",
            }
        ):
            return (
                "NON_COLOR",
                "Normal",
            )

    if node_type == "BUMP":

        if (
            settings[
                "check_height"
            ]
            and socket_name in {
                "height",
                "distance",
                "strength",
            }
        ):
            return (
                "NON_COLOR",
                "Height/Bump",
            )

        if (
            settings[
                "check_normal"
            ]
            and socket_name == "normal"
        ):
            return (
                "NON_COLOR",
                "Normal",
            )

    # ------------------------------------------------------------------
    # Principled and other shader inputs
    # ------------------------------------------------------------------

    if (
        settings[
            "check_roughness"
        ]
        and is_roughness_socket(
            socket_name
        )
    ):
        return (
            "NON_COLOR",
            "Roughness",
        )

    if (
        settings[
            "check_metallic"
        ]
        and is_metallic_socket(
            socket_name
        )
    ):
        return (
            "NON_COLOR",
            "Metallic",
        )

    if (
        settings[
            "check_normal"
        ]
        and is_normal_socket(
            socket_name
        )
    ):
        return (
            "NON_COLOR",
            "Normal",
        )

    if (
        settings[
            "check_height"
        ]
        and is_height_socket(
            socket_name
        )
    ):
        return (
            "NON_COLOR",
            "Height/Displacement",
        )

    if (
        settings[
            "check_masks"
        ]
        and is_mask_or_data_socket(
            node=node,
            socket_name=socket_name,
        )
    ):
        return (
            "NON_COLOR",
            get_data_usage_label(
                socket_name
            ),
        )

    # ------------------------------------------------------------------
    # Material Output
    # ------------------------------------------------------------------

    if node_type == "OUTPUT_MATERIAL":

        if (
            socket_name == "displacement"
            and settings[
                "check_height"
            ]
        ):
            return (
                "NON_COLOR",
                "Displacement",
            )

        # Surface and Volume sockets receive shader closures, not raw image
        # color values. Real color usage should already have been established
        # at a semantic shader input such as Base Color or Emission Color.
        #
        # Treating Surface as "Shader Color" caused false mixed-usage results
        # for masks/factors that merely flowed through a shader network.
        if socket_name in {
            "surface",
            "volume",
        }:
            return None

    # ------------------------------------------------------------------
    # Clearly color-based shader inputs
    # ------------------------------------------------------------------

    if is_color_socket(
        node=node,
        socket_name=socket_name,
    ):
        return (
            "COLOR",
            get_color_usage_label(
                socket_name
            ),
        )

    return None


# -------------------------------------------------------------------------
# Socket rules
# -------------------------------------------------------------------------

# Node types that only process a value and hand it on. Every input socket on
# these nodes is "in transit"; the real usage is decided by wherever the
# chain finally ends.
PASSTHROUGH_NODE_TYPES = {
    "VALTORGB",         # Color Ramp
    "MATH",
    "VECT_MATH",
    "MAP_RANGE",
    "CLAMP",
    "INVERT",
    "HUE_SAT",
    "BRIGHTCONTRAST",
    "GAMMA",
    "CURVE_RGB",
    "RGBTOBW",
    "SEPRGB",
    "COMBRGB",
    "SEPARATE_COLOR",
    "COMBINE_COLOR",
    "SEPARATE_XYZ",
    "COMBINE_XYZ",
    "REROUTE",
}

# Mix nodes: the color inputs (A / B) are in transit, but the Factor input
# is a real mask usage (a texture driving the blend amount is data).
MIX_NODE_TYPES = {
    "MIX",
    "MIX_RGB",
}


def is_passthrough_input(
        node,
        socket_name,
    ):
    """
    Return True when this input socket belongs to an intermediate
    processing node, so tracing should continue past it instead of
    classifying the image by this socket's name.
    """
    node_type = getattr(
        node,
        "type",
        "",
    )

    if node_type in MIX_NODE_TYPES:
        return socket_name not in {
            "fac",
            "factor",
        }

    return node_type in PASSTHROUGH_NODE_TYPES


def is_roughness_socket(
        socket_name,
    ):
    """Return True when the socket represents roughness data."""
    return socket_name in {
        "roughness",
        "coat roughness",
        "clearcoat roughness",
        "transmission roughness",
        "sheen roughness",
        "anisotropic roughness",
    }


def is_metallic_socket(
        socket_name,
    ):
    """Return True when the socket represents metallic data."""
    return socket_name in {
        "metallic",
        "metalness",
    }


def is_normal_socket(
        socket_name,
    ):
    """Return True when the socket represents normal-map data."""
    return socket_name in {
        "normal",
        "tangent",
        "clearcoat normal",
        "coat normal",
    }


def is_height_socket(
        socket_name,
    ):
    """Return True when the socket represents height or displacement data."""
    return socket_name in {
        "height",
        "distance",
        "displacement",
        "scale",
        "midlevel",
    }


def is_mask_or_data_socket(
        node,
        socket_name,
    ):
    """Return True when the socket represents mask or other non-color data."""
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
        "subsurface radius",
    }

    if socket_name in non_color_names:
        return True

    node_type = getattr(
        node,
        "type",
        "",
    )

    if node_type == "DISPLACEMENT":
        return True

    return False


def is_color_socket(
        node,
        socket_name,
    ):
    """Return True when the socket represents color data."""
    color_names = {
        "base color",
        "color",
        "emission color",
        "emission",
        "subsurface color",
        "coat tint",
        "sheen tint",
        "transmission color",
    }

    if socket_name not in color_names:
        return False

    node_type = getattr(
        node,
        "type",
        "",
    )

    # Node Groups can expose sockets with color-like names while processing
    # either color or data internally. Do not finalize their classification
    # here; traversal should continue to their destination.
    #
    # Other processing nodes (Mix, Color Ramp, Separate/Combine Color,
    # Reroute...) are already handled by is_passthrough_input() before this
    # function is ever reached.
    return node_type != "GROUP"


def get_data_usage_label(
        socket_name,
    ):
    """Return a readable label describing the detected non-color data usage."""
    labels = {
        "alpha":
            "Alpha",

        "opacity":
            "Opacity",

        "mask":
            "Mask",

        "ambient occlusion":
            "Ambient Occlusion",

        "occlusion":
            "Ambient Occlusion",

        "ao":
            "Ambient Occlusion",

        "fac":
            "Factor/Mask",

        "factor":
            "Factor/Mask",

        "weight":
            "Weight/Mask",

        "value":
            "Scalar Data",

        "subsurface radius":
            "Subsurface Radius",
    }

    return labels.get(
        socket_name,
        "Non-Color Data",
    )


def get_color_usage_label(
        socket_name,
    ):
    """Return a readable label describing the detected color usage."""
    labels = {
        "base color":
            "Base Color",

        "emission":
            "Emission Color",

        "emission color":
            "Emission Color",

        "subsurface color":
            "Subsurface Color",

        "coat tint":
            "Coat Tint",

        "sheen tint":
            "Sheen Tint",
    }

    return labels.get(
        socket_name,
        "Color",
    )


# -------------------------------------------------------------------------
# Result building
# -------------------------------------------------------------------------

def build_failed_materials(
        failed_images,
    ):
    """
    Converts image-based results into material-based results.
    """
    failed_materials = {}

    for image_name, image_data in (
        failed_images.items()
    ):

        for usage in image_data.get(
            "usages",
            [],
        ):
            material_name = usage[
                "material_name"
            ]

            material_result = (
                failed_materials.setdefault(
                    material_name,
                    {
                        "material_name":
                            material_name,

                        "image_count":
                            0,

                        "images":
                            [],
                    },
                )
            )

            material_result[
                "images"
            ].append({
                "image_name":
                    image_name,

                "node_name":
                    usage[
                        "node_name"
                    ],

                "node_label":
                    usage[
                        "node_label"
                    ],

                "current_colorspace":
                    image_data[
                        "current_colorspace"
                    ],

                "required_colorspace":
                    image_data[
                        "required_colorspace"
                    ],

                "non_color_usages":
                    usage[
                        "non_color_usages"
                    ],

                "color_usages":
                    usage[
                        "color_usages"
                    ],

                "mixed_usage":
                    image_data[
                        "mixed_usage"
                    ],

                # Image-wide view. The two usage lists above only describe
                # this node, while an image can be used by many nodes and
                # materials. These fields show the whole picture.
                "image_non_color_usages":
                    image_data[
                        "non_color_usages"
                    ],

                "image_color_usages":
                    image_data[
                        "color_usages"
                    ],

                "used_as_color_in":
                    get_usage_locations(
                        image_data,
                        color=True,
                        exclude=(
                            material_name,
                            usage[
                                "node_name"
                            ],
                        ),
                    ),

                "used_as_data_in":
                    get_usage_locations(
                        image_data,
                        color=False,
                        exclude=(
                            material_name,
                            usage[
                                "node_name"
                            ],
                        ),
                    ),
            })

    for material_data in (
        failed_materials.values()
    ):
        material_data[
            "image_count"
        ] = len(
            material_data[
                "images"
            ]
        )

    return failed_materials


def get_usage_locations(
        image_data,
        color,
        exclude=None,
        limit=5,
    ):
    """
    Lists where an image is used, as readable "Material / Node: Usage"
    strings.

    Args:
        image_data (dict):
            Image record containing the per-node "usages" list.

        color (bool):
            True to list nodes where the image is used as color,
            False to list nodes where it is used as non-color data.

        exclude (tuple[str, str] | None):
            (material_name, node_name) of a node to leave out, so an
            entry can list only the OTHER places the image is used.

        limit (int):
            Maximum number of locations returned before the rest are
            summarised as "+N more".

    Returns:
        list[str]
    """
    usage_key = (
        "color_usages"
        if color
        else "non_color_usages"
    )

    locations = []

    for usage in image_data.get(
        "usages",
        [],
    ):
        if exclude is not None and (
            usage["material_name"],
            usage["node_name"],
        ) == exclude:
            continue

        usage_names = usage.get(
            usage_key,
            [],
        )

        if not usage_names:
            continue

        locations.append(
            "{} / {}: {}".format(
                usage["material_name"],
                usage["node_name"],
                ", ".join(
                    usage_names
                ),
            )
        )

    if len(locations) > limit:
        extra = len(locations) - limit

        locations = locations[:limit] + [
            "+{} more".format(
                extra
            )
        ]

    return locations


def get_scene_materials(
        scene=None,
    ):
    """
    Returns unique materials assigned to objects in the current scene.
    """
    if scene is None:
        scene = bpy.context.scene

    materials = []
    seen = set()

    for obj in get_qc_objects(
        scene.objects
    ):

        if obj.library is not None:
            continue

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

            if material.library is not None:
                continue

            key = (
                get_datablock_key(
                    material
                )
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            materials.append(
                material
            )

    return materials


def get_image_colorspace(
        image,
    ):
    """
    Return the image color-space name, or an empty value when unavailable.
    """
    try:
        return (
            image.colorspace_settings.name
        )

    except Exception:
        return "Unknown"


def is_image_data(
        image,
    ):
    """
    Return True when Blender treats the image as non-color data.

    Uses Blender's own "is_data" flag so the result does not depend on how
    a given OCIO config names its non-color space. If the flag is
    unavailable, falls back to comparing against the default "Non-Color"
    name.
    """
    try:
        return bool(
            image.colorspace_settings.is_data
        )

    except Exception:
        return (
            normalize_name(
                get_image_colorspace(
                    image
                )
            ).replace(
                "colour",
                "color",
            )
            == "non-color"
        )


def set_image_as_data(
        image,
    ):
    """
    Marks an image as non-color data. Returns True when the image ends up
    treated as data.

    Tries the "is_data" flag first. If that has no effect on this Blender
    build, falls back to the default "Non-Color" color space name.
    """
    colorspace_settings = (
        image.colorspace_settings
    )

    try:
        colorspace_settings.is_data = True

    except Exception:
        pass

    if is_image_data(
        image
    ):
        return True

    colorspace_settings.name = "Non-Color"

    return is_image_data(
        image
    )


def set_image_as_color(
        image,
    ):
    """
    Sets an image used as color to the expected color space. Returns True
    when the image is no longer treated as data.
    """
    image.colorspace_settings.name = (
        COLOR_COLORSPACE_NAME
    )

    return not is_image_data(
        image
    )


def normalize_name(
        value,
    ):
    """
    Normalize a name for case-insensitive usage comparisons.
    """
    return " ".join(
        str(
            value
        )
        .strip()
        .lower()
        .replace(
            "_",
            " ",
        )
        .split()
    )


def get_datablock_key(
        datablock,
    ):
    """
    Return a stable key for identifying a Blender datablock during analysis.
    """
    try:
        return (
            datablock.as_pointer()
        )

    except Exception:
        return id(
            datablock
        )