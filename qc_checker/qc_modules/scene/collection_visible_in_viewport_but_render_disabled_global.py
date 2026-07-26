# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Collection Visible In Viewport But Render Disabled (Global)"
DESCRIPTION = (
    "Checks if collections are visible in the viewport (Monitor ON) "
    "but disabled from render (Camera OFF), globally in every view "
    "layer. Mirrors the object-level check, at the collection level "
    "instead."
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
    failed_objects = get_viewport_visible_render_disabled_collections()

    issues = [
        "Failed collection: {} - Visible in viewport but disabled "
        "from render (Monitor ON, Camera OFF)".format(
            collection_name
        )
        for collection_name in failed_objects
    ]

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Toggling a collection's Camera icon affects every object inside it
# at once - not safe to assume it's a mistake and auto-toggle it for
# the whole collection.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Helpers
# -------------------------

def iterate_layer_collections(layer_collection):
    """
    Yields a LayerCollection and all of its descendants.

    Args:
        layer_collection (bpy.types.LayerCollection):
            Root to start from (typically view_layer.layer_collection).

    Yields:
        bpy.types.LayerCollection
    """
    yield layer_collection

    for child in layer_collection.children:
        for descendant in iterate_layer_collections(child):
            yield descendant


# -------------------------
# Find
# -------------------------

def get_viewport_visible_render_disabled_collections(view_layers=None):
    """
    Finds collections visible in the viewport (Collection.hide_viewport
    is False) but disabled from render (Collection.hide_render is
    True), using the collection datablock's global flags.

    Note:
        Both flags checked here are global, the same in every view
        layer, so results aren't tagged per view layer - unlike the
        Eye-icon version of this same check
        (visibility_collection_eye_visible_render_disabled.py), which
        is scoped to LayerCollection.hide_viewport, a per-view-layer
        flag, instead.

    Args:
        view_layers (iterable[bpy.types.ViewLayer] | None):
            Defaults to every view layer on the current scene - used
            only to walk each view layer's collection tree, not to
            tag results per layer.

    Returns:
        dict:
        {
            "Props": {
                "issue": "Visible in viewport but disabled from render.",
            },
            ...
        }
    """
    if view_layers is None:
        view_layers = bpy.context.scene.view_layers

    failed_objects = {}

    for view_layer in view_layers:
        for layer_collection in iterate_layer_collections(
            view_layer.layer_collection
        ):
            collection = layer_collection.collection

            if collection is None:
                continue

            if collection.name in failed_objects:
                continue

            if not collection.hide_viewport and collection.hide_render:
                failed_objects[collection.name] = {
                    "issue": (
                        "Visible in viewport but disabled from render."
                    ),
                }

    return failed_objects
