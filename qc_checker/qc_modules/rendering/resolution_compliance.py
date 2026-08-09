import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Resolution Compliance"
DESCRIPTION = (
    "Checks that the scene render resolution percentage is set to 100%."
)
WHY = (
    "Leaving it unadjusted means your final output will render at "
    "a different size instead of your target size."
)


# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "required_percentage": {
        "type": "int",
        "label": "Required Percentage",
        "description": (
            "Required render resolution percentage."
        ),
        "default": 100,
        "min": 1,
        "max": 100,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks the current scene's render resolution percentage.

    Args:
        preferences (dict | None):
            User-configured check settings.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_settings": dict,
            "settings": dict,
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed_settings = get_resolution_percentage_mismatch(
        settings=settings,
    )

    issues = []

    if failed_settings:
        current_percentage = failed_settings[
            "resolution_percentage"
        ]

        required_percentage = failed_settings[
            "required_percentage"
        ]

        issues.append(
            (
                "Render resolution percentage is set to {}%. "
                "It must be set to {}%."
            ).format(
                current_percentage,
                required_percentage,
            )
        )

    return {
        "issues": issues,
        "failed_settings": failed_settings,
        "settings": settings,
    }


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Sets the render resolution percentage to the required value.

    Args:
        result_data (dict | None):
            Result returned by main().

        preferences (dict | None):
            User-configured check settings.

    Returns:
        dict:
        {
            "fixed_settings": dict,
            "issues": list[str],
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    return fix_resolution_percentage(
        result_data=result_data,
        settings=settings,
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_resolution_percentage_mismatch(
        scene=None,
        settings=None,
    ):
    """
    Checks whether the scene render resolution percentage matches the
    required percentage.

    Args:
        scene (bpy.types.Scene | None):
            Scene to inspect. Defaults to the current scene.

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
            Empty dictionary when the check passes.

            Otherwise:
            {
                "scene_name": str,
                "resolution_percentage": int,
                "required_percentage": int,
                "resolution_x": int,
                "resolution_y": int,
                "effective_resolution_x": int,
                "effective_resolution_y": int,
            }
    """
    if scene is None:
        scene = bpy.context.scene

    if scene is None:
        return {}

    if settings is None:
        settings = resolve_settings(SETTINGS)

    required_percentage = int(
        settings.get(
            "required_percentage",
            100,
        )
    )

    render = scene.render

    current_percentage = int(
        render.resolution_percentage
    )

    if current_percentage == required_percentage:
        return {}

    resolution_x = int(
        render.resolution_x
    )

    resolution_y = int(
        render.resolution_y
    )

    scale = current_percentage / 100.0

    effective_resolution_x = round(
        resolution_x * scale
    )

    effective_resolution_y = round(
        resolution_y * scale
    )

    return {
        "scene_name": scene.name,
        "resolution_percentage": current_percentage,
        "required_percentage": required_percentage,
        "resolution_x": resolution_x,
        "resolution_y": resolution_y,
        "effective_resolution_x": effective_resolution_x,
        "effective_resolution_y": effective_resolution_y,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_resolution_percentage(
        result_data=None,
        settings=None,
    ):
    """
    Sets the current scene's render resolution percentage to the required
    percentage.

    The setting is rechecked before it is changed so the fix does not rely
    entirely on potentially stale result data.

    Args:
        result_data (dict | None):
            Result returned by main().

        settings (dict | None):
            Resolved check settings.

    Returns:
        dict:
        {
            "fixed_settings": dict,
            "issues": list[str],
        }
    """
    if settings is None:
        settings = resolve_settings(SETTINGS)

    scene = bpy.context.scene

    if scene is None:
        return {
            "fixed_settings": {},
            "issues": [
                "No active scene is available."
            ],
        }

    current_failure = get_resolution_percentage_mismatch(
        scene=scene,
        settings=settings,
    )

    if not current_failure:
        return {
            "fixed_settings": {},
            "issues": [],
        }

    previous_percentage = int(
        scene.render.resolution_percentage
    )

    required_percentage = int(
        settings.get(
            "required_percentage",
            100,
        )
    )

    try:
        scene.render.resolution_percentage = (
            required_percentage
        )

    except Exception as error:
        return {
            "fixed_settings": {},
            "issues": [
                (
                    "Could not set the render resolution "
                    "percentage to {}%: {}"
                ).format(
                    required_percentage,
                    error,
                )
            ],
        }

    current_percentage = int(
        scene.render.resolution_percentage
    )

    return {
        "fixed_settings": {
            "scene_name": scene.name,
            "resolution_percentage": {
                "previous": previous_percentage,
                "current": current_percentage,
            },
        },
        "issues": [],
    }
