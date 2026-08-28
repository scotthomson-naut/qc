# Python imports
import re

# Blender imports
import bpy


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

SEVERITY = "warning"
LABEL = "Rig Name Validation"
DESCRIPTION = (
    "Checks armature and bone names for unsupported characters, "
    "Blender auto suffixes, spacing, and optional left/right suffix rules."
)
WHY = (
    "Consistent rig naming improves scripting, mirroring, retargeting, "
    "export, and debugging."
)

SETTINGS = {
    "allow_spaces": {
        "type": "bool",
        "label": "Allow Spaces",
        "default": False,
    },
    "flag_auto_suffixes": {
        "type": "bool",
        "label": "Flag Auto Suffixes",
        "default": True,
    },
    "require_side_suffix": {
        "type": "bool",
        "label": "Require Side Suffix",
        "default": False,
    },
    "left_suffix": {
        "type": "string",
        "label": "Left Suffix",
        "default": ".L",
    },
    "right_suffix": {
        "type": "string",
        "label": "Right Suffix",
        "default": ".R",
    },
}


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main(preferences=None):
    """
    Finds objects.

    Returns:
        dict:
        {
            "issues": list[str],
            "failed_objects": dict,
            "can_auto_fix": bool
        }
    """
    settings = resolve_settings(
        SETTINGS,
        preferences,
    )

    failures = find_name_issues(
        settings=settings
    )

    issues = []

    for object_name, data in sorted(
        failures.items()
    ):
        for problem in data.get("problems", []):
            issues.append(
                '{}: {}.'.format(
                    object_name,
                    problem,
                )
            )

        for bone_name, problems in sorted(
            data.get("bones", {}).items()
        ):
            for problem in problems:
                issues.append(
                    '{} / {}: {}.'.format(
                        object_name,
                        bone_name,
                        problem,
                    )
                )

    return {
        "issues": issues,
        "failed_objects": failures,
        "settings": settings,
        "can_auto_fix": False,
    }


# -------------------------------------------------------------------------
# Find
# -------------------------------------------------------------------------

def find_name_issues(
        objects=None,
        settings=None,
    ):
    if objects is None:
        objects = bpy.context.scene.objects

    if settings is None:
        settings = resolve_settings(SETTINGS)

    failures = {}

    for obj in get_qc_objects(objects):
        if obj.type != "ARMATURE":
            continue

        object_problems = validate_name(
            obj.name,
            settings,
        )

        bone_failures = {}

        for bone in obj.data.bones:
            problems = validate_name(
                bone.name,
                settings,
            )

            if problems:
                bone_failures[bone.name] = problems

        if object_problems or bone_failures:
            failures[obj.name] = {
                "problems": object_problems,
                "bones": bone_failures,
            }

    return failures


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def validate_name(name, settings):
    problems = []
    allow_spaces = bool(
        settings.get("allow_spaces", False)
    )

    if name != name.strip():
        problems.append(
            "Name has leading or trailing spaces"
        )

    if not allow_spaces and " " in name:
        problems.append("Name contains spaces")

    pattern = (
        r"^[A-Za-z0-9_.\- ]+$"
        if allow_spaces
        else r"^[A-Za-z0-9_.\-]+$"
    )

    if re.match(pattern, name) is None:
        problems.append(
            "Name contains unsupported characters"
        )

    if (
        settings.get(
            "flag_auto_suffixes",
            True,
        )
        and re.search(
            r"\.\d{3}$",
            name,
        )
    ):
        problems.append(
            "Name has a Blender automatic numeric suffix"
        )

    if settings.get(
        "require_side_suffix",
        False,
    ):
        lower_name = name.lower()
        left_suffix = str(
            settings.get("left_suffix", ".L")
        )
        right_suffix = str(
            settings.get("right_suffix", ".R")
        )

        appears_left = any(
            token in lower_name
            for token in (
                "left",
                "_l",
                ".l",
            )
        )

        appears_right = any(
            token in lower_name
            for token in (
                "right",
                "_r",
                ".r",
            )
        )

        if (
            appears_left
            and not name.endswith(
                left_suffix
            )
        ):
            problems.append(
                'Expected left suffix "{}"'.format(
                    left_suffix
                )
            )

        if (
            appears_right
            and not name.endswith(
                right_suffix
            )
        ):
            problems.append(
                'Expected right suffix "{}"'.format(
                    right_suffix
                )
            )

    return problems
