# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "info"
LABEL = "Collection Excluded From View Layer"
DESCRIPTION = (
    "Checks if collections are excluded from a view layer (Exclude "
    "checkbox unchecked). Normal part of workflow, but worth "
    "surfacing. Skips collections named to match a hero/deliverable "
    "pattern - those are covered by a separate, Warning-severity "
    "check instead."
)

DELIVERABLE_COLLECTION_KEYWORDS = (
    "hero",
    "deliverable",
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
    failed_objects = get_excluded_collections()

    issues = []

    for collection_name, collection_data in failed_objects.items():
        issues.append(
            "Failed collection: {} - Excluded from view layer(s): "
            "{}".format(
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
# Un-excluding a collection to "fix" this could pull a whole branch
# of objects back into the view layer that were deliberately taken
# out - not safe to assume it's a mistake and auto-toggle it.

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


def is_deliverable_collection(collection):
    """
    Args:
        collection (bpy.types.Collection): Collection to classify.

    Returns:
        bool: True if the collection's name matches a known
            hero/deliverable pattern.
    """
    name_lower = collection.name.lower()

    return any(
        keyword in name_lower for keyword in DELIVERABLE_COLLECTION_KEYWORDS
    )


# -------------------------
# Find
# -------------------------

def get_excluded_collections(view_layers=None):
    """
    Finds collections excluded from a view layer, skipping ones named
    to match a hero/deliverable pattern.

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

        checked_collections = set()

        for layer_collection in iterate_layer_collections(
            view_layer.layer_collection
        ):
            collection = layer_collection.collection

            if collection is None:
                # The root LayerCollection wraps the scene master
                # collection - nothing meaningful to flag.
                continue

            if collection.name in checked_collections:
                continue

            checked_collections.add(collection.name)

            if not layer_collection.exclude:
                continue

            if is_deliverable_collection(collection):
                # Covered by the separate Warning-severity check
                # instead, not this one.
                continue

            collection_data = failed_objects.setdefault(
                collection.name,
                {"view_layers": []},
            )

            collection_data["view_layers"].append(view_layer.name)

    return failed_objects
