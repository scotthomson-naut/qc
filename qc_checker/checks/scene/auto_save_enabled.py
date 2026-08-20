# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Auto Save Enabled"
DESCRIPTION = (
    "Checks if Blender's 'Auto Save Temporary Files' preference is "
    "enabled. "
)
WHY = (
    "Safety net prevents massive data loss if the software crashes, "
    "your computer loses power, or you forget to save your progress."
)

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    """
    Run for issue.

    Note:
        This checks a Blender application preference, not data stored
        in the .blend file. The result reflects whichever machine
        actually runs this check - not something saved with the
        scene, and not something that reflects every artist's
        individual setup.

    Returns:
        dict: {issues (list(str)), failed_settings(dict)}
    """

    return get_autosave_status()


def fix(result_data):
    """
    Fix for issue.

    Note:
        Unlike every other check in this QC tool so far, this one is
        safe to auto-fix: it's a personal Blender preference, not
        shared scene content, so flipping it can't affect anyone
        else's work or any artist's creative decisions. Only enables
        it locally, on whichever machine runs this - it does not
        propagate to other artists' machines or get saved into the
        .blend file.

    Args:
        result_data (list[str]): List of object names.
    Returns:
        dict: Issues
    """
    # Call Function
    fix_result = fix_autosave_disabled(result_data)

    return fix_result


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def get_autosave_status():
    """
    Reads Blender's current Auto Save Temporary Files preference.

    Returns:
        dict:
        {
            "enabled": bool,
            "interval_minutes": float,
        }
    """
    failed_settings = {}
    issues = []

    filepaths_prefs = bpy.context.preferences.filepaths

    if not filepaths_prefs.use_auto_save_temporary_files:
        failed_settings["Auto Save Temporary Files"] = {
            "issue": "Auto Save Temporary Files is disabled.",
        }
        issues.append(
            "Failed: Auto Save Temporary Files is disabled in "
            "Blender's preferences."
        )

    return {
        "issues": issues,
        "failed_settings": failed_settings,
    }


# -------------------------------------------------------------------------
# Fix
# -------------------------------------------------------------------------

def fix_autosave_disabled(result_data):
    """
    Enables Auto Save Temporary Files if it was found disabled.

    Args:
        result_data (dict):
            Result returned by main().

    Returns:
        dict:
            Fix result.
    """
    bpy.context.preferences.filepaths.use_auto_save_temporary_files = True

    return {
        "fixed_settings": {},
        "issues": [],
    }
