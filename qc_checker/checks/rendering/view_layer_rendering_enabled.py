# Blender imports
import bpy

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "critical"
LABEL = "View Layer Rendering Enabled"
DESCRIPTION = (
    "Checks if every view layer has 'Use for Rendering' enabled."
)
WHY = (
    "Tells which specific scene layers to include when you "
    "hit render. If this box is unchecked, Blender skips that entire layer. "
    "This saves render time, avoids clutter, and lets you work on "
    "complex scenes step by step."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Note:
        Uses ViewLayer.use, based on the "Use for Rendering" checkbox
        in the View Layer Properties tab. This property name has not
        been confirmed against a live Blender console check - verify
        with bpy.context.view_layer.use before trusting this in
        production.

        View layers aren't objects and aren't selectable in the
        viewport - like aov_denoising.py and
        view_layer_render_single_disabled.py, this only ever returns
        "failed_settings", never "failed_objects". A per-name entry
        in failed_objects was previously enough to make the panel
        show a "Select Failed Objects" button with nothing valid to
        select.

    Returns:
        dict: {issues (list(str)), failed_settings(dict)}
    """
    scene = bpy.context.scene

    disabled_view_layers = get_view_layers_not_used_for_rendering(
        scene=scene,
    )

    total_count = len(scene.view_layers)
    disabled_count = len(disabled_view_layers)

    issues = []
    failed_settings = {}

    if disabled_view_layers:
        disabled_names = sorted(disabled_view_layers.keys())

        issues.append(
            "Failed: {}/{} view layers have 'Use for Rendering' "
            "disabled ({})".format(
                disabled_count,
                total_count,
                ", ".join(disabled_names),
            )
        )

        failed_settings["use_for_rendering"] = {
            "disabled_count": disabled_count,
            "total_count": total_count,
            "disabled_view_layers": disabled_names,
        }

    return {
        "issues": issues,
        "failed_settings": failed_settings,
    }


def fix(result_data=None):
    """
    Fix for issue.

    Note:
        This reverses an earlier "manual-only, period" decision on
        this same check - that's fine, since the Fix button is only
        ever triggered by an artist choosing to click it, not run
        automatically. If a disabled view layer was intentional, the
        artist simply doesn't click Fix.

    Args:
        result_data (dict | None): Result returned by main().
    Returns:
        dict: Fix result.
    """
    return fix_view_layers_not_used_for_rendering(result_data)

# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_view_layers_not_used_for_rendering(scene=None):
    """
    Finds view layers that have 'Use for Rendering' disabled.

    Args:
        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
        {
            "ViewLayer_001": {
                "issue": "'Use for Rendering' is disabled.",
            },
            ...
        }
    """
    if scene is None:
        scene = bpy.context.scene

    failed_objects = {}

    for view_layer in scene.view_layers:
        if not view_layer.use:
            failed_objects[view_layer.name] = {
                "issue": "'Use for Rendering' is disabled.",
            }

    return failed_objects


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_view_layers_not_used_for_rendering(result_data=None, scene=None):
    """
    Enables 'Use for Rendering' on every currently-disabled view
    layer.

    Note:
        Rechecks the scene fresh rather than trusting result_data's
        recorded list, in case the scene changed between when the
        check last ran and when Fix was clicked.

    Args:
        result_data (dict | None):
            Result returned by main(). Not relied on for the actual
            fix - see note above.

        scene (bpy.types.Scene | None):
            Defaults to bpy.context.scene.

    Returns:
        dict:
            Fix result.
    """
    if scene is None:
        scene = bpy.context.scene

    disabled_view_layers = get_view_layers_not_used_for_rendering(
        scene=scene,
    )

    issues = []
    fixed_names = []

    for view_layer_name in disabled_view_layers:
        view_layer = scene.view_layers.get(view_layer_name)

        if view_layer is None:
            issues.append(
                "View layer no longer exists: {}".format(
                    view_layer_name
                )
            )
            continue

        view_layer.use = True
        fixed_names.append(view_layer_name)

    if not fixed_names:
        return {
            "issues": issues,
            "fixed_settings": {},
        }

    return {
        "issues": issues,
        "fixed_settings": {
            "use_for_rendering": {
                "enabled_view_layers": fixed_names,
            },
        },
    }