"""Scriptronaut QC Checks internal module."""

from ..icons import get_icon_id


def get_severity_icon(
        severity,
    ):
    """
    Returns the custom icon ID for a QC severity.
    """

    icons = {
        "critical":
            "severity_critical",

        "warning":
            "severity_warning",

        "info":
            "severity_info",
    }

    icon_name = icons.get(
        severity,
        "severity_warning",
    )

    return get_icon_id(
        icon_name
    )
