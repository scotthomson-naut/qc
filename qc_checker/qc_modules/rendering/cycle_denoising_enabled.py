# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Cycles Denoising Enabled"
DESCRIPTION = (
    "Checks whether Cycles render denoising is enabled."
)

# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "required": {
        "type": "bool",
        "label": "Require Denoising",
        "description": (
            "If enabled, the check fails when Cycles render "
            "denoising is disabled."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks whether Cycles render denoising is enabled.

    Returns:
        dict
    """
    return get_cycles_denoise_setting(preferences)


def fix(
        result_data=None,
        preferences=None,
    ):
    """
    Enables Cycles render denoising.
    """
    return fix_cycles_denoise_setting()


# -------------------------------------------------------------------------
# Get
# -------------------------------------------------------------------------

def get_cycles_denoise_setting(preferences=None):
    """
    Checks whether Cycles render denoising is enabled.

    Returns:
        dict
    """
    settings = resolve_settings(preferences)

    scene = bpy.context.scene

    issues = []
    failed_settings = {}

    # Ignore non-Cycles render engines.
    if scene.render.engine != "CYCLES":
        return {
            "issues": [],
            "failed_settings": {},
        }

    if not settings["required"]:
        return {
            "issues": [],
            "failed_settings": {},
        }

    cycles = scene.cycles

    if not cycles.use_denoising:
        issues.append(
            "Cycles render denoising is disabled."
        )

        failed_settings["use_denoising"] = {
            "current": False,
            "expected": True,
        }

    return {
        "issues": issues,
        "failed_settings": failed_settings,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_cycles_denoise_setting():
    """
    Enables Cycles render denoising.
    """
    scene = bpy.context.scene
    if scene.render.engine != "CYCLES":
        return {
            "fixed_settings": {},
            "issues": [
                "Scene is not using the Cycles render engine."
            ],
        }

    cycles = scene.cycles
    previous = cycles.use_denoising
    cycles.use_denoising = True

    return {
        "fixed_settings": {
            "use_denoising": {
                "previous": previous,
                "current": True,
            }
        },
        "issues": [],
    }


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def resolve_settings(preferences=None):
    """
    Resolve user preferences over defaults.
    """
    resolved = {
        name: definition.get("default")
        for name, definition in SETTINGS.items()
    }

    if isinstance(preferences, dict):
        for key, value in preferences.items():
            if key in resolved:
                resolved[key] = value

    return resolved
