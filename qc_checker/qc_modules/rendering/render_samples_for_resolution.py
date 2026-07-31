# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Render Samples Too High"
DESCRIPTION = (
    "Checks whether Cycles render samples are higher than "
    "recommended for the current output resolution."
)

# -------------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------------

SETTINGS = {
    "samples_720p": {
        "type": "int",
        "label": "Maximum Samples at 720p",
        "description": (
            "Maximum recommended Cycles samples for output "
            "up to 1280 × 720."
        ),
        "default": 256,
        "min": 1,
        "max": 100000,
    },

    "samples_1080p": {
        "type": "int",
        "label": "Maximum Samples at 1080p",
        "description": (
            "Maximum recommended Cycles samples for output "
            "up to 1920 × 1080."
        ),
        "default": 512,
        "min": 1,
        "max": 100000,
    },

    "samples_1440p": {
        "type": "int",
        "label": "Maximum Samples at 1440p",
        "description": (
            "Maximum recommended Cycles samples for output "
            "up to 2560 × 1440."
        ),
        "default": 768,
        "min": 1,
        "max": 100000,
    },

    "samples_4k": {
        "type": "int",
        "label": "Maximum Samples at 4K",
        "description": (
            "Maximum recommended Cycles samples for output "
            "up to 3840 × 2160."
        ),
        "default": 1024,
        "min": 1,
        "max": 100000,
    },

    "allow_auto_fix": {
        "type": "bool",
        "label": "Allow Automatic Fix",
        "description": (
            "Allow the check to reduce the scene sample count "
            "to the recommended value."
        ),
        "default": True,
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Checks render samples against output resolution.

    Returns:
        dict
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    failed = get_render_sample_issue(settings)
    issues = []

    if failed:
        issues.append(
            "Cycles samples ({}) exceed the recommended maximum "
            "({}) for {} x {} output.".format(
                failed["current_samples"],
                failed["recommended_samples"],
                failed["width"],
                failed["height"],
            )
        )

    return {
        "issues": issues,
        "failed_settings": failed,
        "settings": settings,
    }


def fix(result_data, preferences=None):
    """
    Automatically reduces render samples to the recommended amount.
    """
    settings = resolve_settings(
        SETTINGS,
        preferences
    )

    if not settings["allow_auto_fix"]:
        return {
            "fixed_objects": {},
            "issues": [
                "Automatic fixing is disabled in this check's settings."
            ],
        }

    return fix_render_samples(
        result_data
    )


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_render_sample_issue(settings):
    scene = bpy.context.scene

    if scene.render.engine != "CYCLES":
        return None

    resolution_scale = (
        scene.render.resolution_percentage
        / 100.0
    )

    width = int(
        scene.render.resolution_x
        * resolution_scale
    )

    height = int(
        scene.render.resolution_y
        * resolution_scale
    )

    pixel_count = width * height

    sample_limits = [
        (
            1280 * 720,
            settings["samples_720p"],
        ),
        (
            1920 * 1080,
            settings["samples_1080p"],
        ),
        (
            2560 * 1440,
            settings["samples_1440p"],
        ),
        (
            3840 * 2160,
            settings["samples_4k"],
        ),
    ]

    recommended_samples = (
        settings["samples_4k"]
    )

    for maximum_pixels, samples in sample_limits:
        if pixel_count <= maximum_pixels:
            recommended_samples = samples
            break

    current_samples = scene.cycles.samples

    if current_samples <= recommended_samples:
        return None

    return {
        "width": width,
        "height": height,
        "pixel_count": pixel_count,
        "current_samples": current_samples,
        "recommended_samples": recommended_samples,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_render_samples(result_data=None):
    """
    Sets render samples to the recommended amount.
    """
    if not isinstance(result_data, dict):
        result_data = {}

    failed = result_data.get(
        "failed_settings"
    )

    if not failed:
        return {
            "fixed_objects": {},
            "issues": [],
        }

    scene = bpy.context.scene

    previous = scene.cycles.samples

    scene.cycles.samples = failed[
        "recommended_samples"
    ]

    return {
        "fixed_objects": {
            "Scene": {
                "previous_samples": previous,
                "samples": scene.cycles.samples,
            }
        },
        "issues": [],
    }
