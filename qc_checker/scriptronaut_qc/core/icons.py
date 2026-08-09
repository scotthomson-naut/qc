"""Scriptronaut QC Checks internal module."""

from typing import Any


def get_severity_icon(severity):
    """
    Returns the Blender icon for a QC severity.
    """

    icons = {
        "critical": "KEYTYPE_EXTREME_VEC",
        "warning": "KEYTYPE_KEYFRAME_VEC",
        "info": "KEYTYPE_BREAKDOWN_VEC",
    }

    return icons.get(
        severity,
        "KEYTYPE_KEYFRAME_VEC",
    )
