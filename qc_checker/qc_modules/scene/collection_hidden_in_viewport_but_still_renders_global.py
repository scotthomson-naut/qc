# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Collection Hidden In Viewport But Still Renders (Global)"
DESCRIPTION = (
    "Checks if collections are disabled from viewport (Monitor OFF) "
    "but will still render (Camera ON), globally in every view "
    "layer. Common, often intentional pattern for heavy content kept "
    "out of the way during layout - surfaced here so it isn't a "
    "surprise at render time."
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
    failed_objects = get_hidden_viewport_visible_render_collections()

    issues = [
        "Failed collection: {} - Hidden in viewport but will still "
        "render (Monitor OFF, Camera ON)".format(
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
# Toggling a collection's Monitor icon affects every object inside it
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

def get_hidden_viewport_visible_render_collections(view_layers=None):
    """
    Finds collections disabled from viewport (Collection.hide_viewport
    is True) that will still render (Collection.hide_render is False),
    using the collection datablock's global flags.

    Note:
        Both flags checked here are global, the same in every view
        layer, so results aren't tagged per view layer - unlike the
        Eye-icon version of this same check
        (visibility_collection_eye_hidden_visible_render.py), which
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
                "issue": "Hidden in viewport but will still render.",
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

            if collection.hide_viewport and not collection.hide_render:
                failed_objects[collection.name] = {
                    "issue": (
                        "Hidden in viewport but will still render."
                    ),
                }

    return failed_objects