# Standard python imports

# Blender imports
import bpy

# Company imports

# Meta data
SEVERITY = "critical"
LABEL = "Render Intent Not Overridden"
DESCRIPTION = (
    "Checks if an object's own render visibility intent (the Camera/"
    "Disable in Renders icon) is being silently overridden by an "
    "excluded or render-disabled ancestor collection"
)

# Object types this check evaluates. Cameras/lights/speakers etc.
# don't meaningfully participate in the visibility cascade.
RELEVANT_OBJECT_TYPES = {
    "MESH",
    "CURVE",
    "SURFACE",
    "META",
    "FONT",
    "EMPTY",
    "ARMATURE",
    "LATTICE",
    "VOLUME",
    "GPENCIL",
}

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Returns:
        dict: {issues (list(str)), failed_objects(dict)}
    """
    failed_objects = get_cascade_override_objects()

    issues = []

    for object_name, object_data in failed_objects.items():
        for conflict in object_data["conflicts"]:
            message = (
                "Failed object: {} - Intends to render (hide_render="
                "False) but an ancestor collection is excluding it or "
                "disabling it from render in view layer '{}'".format(
                    object_name,
                    conflict["view_layer"],
                )
            )

            if conflict["resolver_uncertain"]:
                message += (
                    " [multi-linked object - resolver assumption "
                    "unverified for this case, confirm manually]"
                )

            issues.append(message)

    return {
        "issues": issues,
        "failed_objects": failed_objects,
    }

# No fix() for this check.
#
# Un-excluding or re-enabling render on an ancestor collection to
# "fix" one object could silently change the correct, intended state
# of every other object sharing that same collection. This always
# needs an artist to look at the actual scene and decide.

# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------

# -------------------------
# Resolver
# -------------------------

def find_object_layer_collection_chains(
        obj,
        layer_collection,
        current_chain=None,
    ):
    """
    Finds every path from a view layer's root LayerCollection down to
    a LayerCollection that directly contains this object.

    An object linked into more than one collection resolves to
    multiple chains here. This is the multi-linked edge case the
    design spec calls out as unconfirmed - see
    resolve_object_visibility() for how it's handled.

    Args:
        obj (bpy.types.Object):
            Object to search for.

        layer_collection (bpy.types.LayerCollection):
            Node to search from.

        current_chain (list[bpy.types.LayerCollection] | None):
            Internal recursion state - leave as None.

    Returns:
        list[list[bpy.types.LayerCollection]]:
            One entry per path found, root-first, ending at the
            LayerCollection that directly holds the object.
    """
    if current_chain is None:
        current_chain = []

    chains = []

    new_chain = current_chain + [layer_collection]

    if obj.name in layer_collection.collection.objects:
        chains.append(new_chain)

    for child in layer_collection.children:
        chains.extend(
            find_object_layer_collection_chains(
                obj,
                child,
                current_chain=new_chain,
            )
        )

    return chains


def chain_blocks_render(chain):
    """
    Checks whether any collection in a chain would block the render.

    Args:
        chain (list[bpy.types.LayerCollection]):
            Root-first chain, as returned by
            find_object_layer_collection_chains().

    Returns:
        bool:
            True if this specific chain blocks the render.
    """
    for layer_collection in chain:
        if layer_collection.exclude:
            return True

        if layer_collection.collection.hide_render:
            return True

    return False


def chain_blocks_viewport(chain):
    """
    Checks whether any collection in a chain would block viewport
    visibility.

    This mirrors chain_blocks_render() and exists only to
    self-validate the multi-chain resolution strategy - see
    resolve_object_visibility().

    Args:
        chain (list[bpy.types.LayerCollection]):
            Root-first chain.

    Returns:
        bool:
            True if this specific chain blocks viewport visibility.
    """
    for layer_collection in chain:
        if layer_collection.exclude:
            return True

        if layer_collection.hide_viewport:
            return True

        if layer_collection.collection.hide_viewport:
            return True

    return False


def resolve_object_visibility(obj, view_layer):
    """
    Resolves effective viewport and render visibility for an object
    within one view layer, matching Blender's cascade logic.

    Note:
        Viewport visibility is read directly from Blender's own
        object.visible_get(), which is authoritative. There is no
        built-in equivalent for render visibility, so it's computed
        manually here by walking the collection hierarchy.

        UNCONFIRMED ASSUMPTION (per the design spec, section 5): for
        an object linked into more than one collection, this assumes
        Blender uses "most permissive chain wins" - i.e. the object
        renders if AT LEAST ONE of its collection chains allows it,
        not only if ALL of them do. This matches the confirmed
        behavior of object.visible_get() for viewport visibility, but
        that has not been confirmed for the render case specifically.

        To avoid silently trusting an unverified assumption, this
        function self-checks it: it recomputes viewport visibility
        using the identical chain-walking logic and compares that
        against object.visible_get() (the ground truth). If they
        disagree, "resolver_uncertain" is set True, meaning the
        render result for this object should be treated with caution
        and confirmed manually rather than trusted outright.

    Args:
        obj (bpy.types.Object):
            Object to resolve.

        view_layer (bpy.types.ViewLayer):
            View layer to resolve against.

    Returns:
        dict:
        {
            "effective_viewport_visible": bool,
            "effective_render_visible": bool,
            "is_multi_linked": bool,
            "resolver_uncertain": bool,
        }
    """
    effective_viewport_visible = obj.visible_get(view_layer=view_layer)

    chains = find_object_layer_collection_chains(
        obj,
        view_layer.layer_collection,
    )

    is_multi_linked = len(chains) > 1

    if not chains:
        # Not reachable from this view layer's collection tree at
        # all - nothing to walk, defer entirely to Blender's own
        # resolution rather than guessing.
        effective_render_visible = (
            effective_viewport_visible and not obj.hide_render
        )
        resolver_uncertain = False

    else:
        chain_allows_render = any(
            not chain_blocks_render(chain) for chain in chains
        )

        effective_render_visible = (
            not obj.hide_render and chain_allows_render
        )

        chain_allows_viewport = any(
            not chain_blocks_viewport(chain) for chain in chains
        )

        computed_viewport_visible = (
            not obj.hide_get(view_layer=view_layer)
            and not obj.hide_viewport
            and chain_allows_viewport
        )

        resolver_uncertain = (
            computed_viewport_visible != effective_viewport_visible
        )

    return {
        "effective_viewport_visible": effective_viewport_visible,
        "effective_render_visible": effective_render_visible,
        "is_multi_linked": is_multi_linked,
        "resolver_uncertain": resolver_uncertain,
    }


# -------------------------
# Find
# -------------------------

def get_cascade_override_objects(objects=None, view_layers=None):
    """
    Finds objects whose own render intent (hide_render) is being
    silently overridden by an ancestor collection, in any view layer.

    A mismatch here means an ancestor collection is excluding the
    object or disabling it from render, even though the object's own
    Camera icon says it should render. This is invisible unless
    specifically checked for, since the object's own flags look
    completely correct in isolation.

    Note:
        Given how resolve_object_visibility() derives
        effective_render_visible (it can only ever be True if
        hide_render is already False), the only mismatch that can
        occur is "wants to render but resolves as not rendering."
        The reverse is not mathematically possible with that formula,
        so it isn't checked for here.

    Args:
        objects (iterable[bpy.types.Object] | None):
            Defaults to all objects in the current scene.

        view_layers (iterable[bpy.types.ViewLayer] | None):
            Defaults to every view layer on the current scene.

    Returns:
        dict:
        {
            "Cube": {
                "conflicts": [
                    {
                        "view_layer": "ViewLayer_001",
                        "resolver_uncertain": False,
                    },
                ],
            },
            ...
        }
    """
    scene = bpy.context.scene

    if objects is None:
        objects = scene.objects

    if view_layers is None:
        view_layers = scene.view_layers

    failed_objects = {}

    for view_layer in view_layers:
        for obj in objects:
            if obj.type not in RELEVANT_OBJECT_TYPES:
                continue

            resolved = resolve_object_visibility(obj, view_layer)

            wants_to_render = not obj.hide_render
            resolved_render_visible = resolved["effective_render_visible"]

            if not (wants_to_render and not resolved_render_visible):
                continue

            object_data = failed_objects.setdefault(
                obj.name,
                {"conflicts": []},
            )

            object_data["conflicts"].append(
                {
                    "view_layer": view_layer.name,
                    "resolver_uncertain": resolved["resolver_uncertain"],
                }
            )

    return failed_objects