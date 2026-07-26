# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Collection Hidden In Viewport But Still Renders (Local)"
DESCRIPTION = (
    "Checks if collections are hidden via the per-view-layer Eye "
    "icon (LayerCollection.hide_viewport is True) but will still "
    "render (Camera ON, global). Scoped to one view layer at a time, "
    "distinct from the Monitor-icon version which is global."
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
    failed_objects = get_eye_hidden_visible_render_collections()

    issues = []

    for collection_name, collection_data in failed_objects.items():
        issues.append(
            "Failed collection: {} - Hidden via Eye icon but will "
            "still render, in view layer(s): {}".format(
                collection_name,
                ", ".join(collection_data["view_layers"]),
            )
        )

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Toggling a collection's Eye icon affects every object inside it at
# once - not safe to assume it's a mistake and auto-toggle it for the
# whole collection.

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

def get_eye_hidden_visible_render_collections(view_layers=None):
    """
    Finds collections hidden via the per-view-layer Eye icon
    (LayerCollection.hide_viewport is True) that will still render
    (Collection.hide_render is False).

    Note:
        Must iterate per view layer, since LayerCollection.hide_viewport
        is stored independently for each one. This is the per-view-
        layer counterpart to
        visibility_collection_hidden_viewport_visible_render_global.py,
        which checks the equivalent global Collection.hide_viewport
        flag instead.

        Excluded collections (Exclude checkbox unchecked) are skipped
        here - that state is covered by its own dedicated checks, and
        the Eye icon's value is largely moot on a collection that
        isn't part of the view layer at all.

    Args:
        view_layers (iterable[bpy.types.ViewLayer] | None):
            Defaults to every view layer on the current scene.

    Returns:
        dict:
        {
            "Props": {
                "view_layers": ["ViewLayer_001"],
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

            if layer_collection.exclude:
                continue

            eye_hidden = layer_collection.hide_viewport

            if eye_hidden and not collection.hide_render:
                collection_data = failed_objects.setdefault(
                    collection.name,
                    {"view_layers": []},
                )

                collection_data["view_layers"].append(view_layer.name)

    return failed_objects
