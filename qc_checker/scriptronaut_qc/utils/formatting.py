"""Scriptronaut QC Checks internal module."""

import textwrap
from typing import Any

from ..core.results import get_issues_from_result


def get_matching_object_issues(
        result_data,
        object_name,
    ):
    """
    Returns top-level issue messages associated with one object.

    Existing checks usually include the object name in the issue string,
    so this provides useful information without requiring every QC module
    to change its return structure.
    """
    issues = get_issues_from_result(
        result_data
    )

    matching_issues = []

    object_name_lower = (
        str(object_name).lower()
    )

    for issue in issues:
        issue_text = str(issue)

        if (
            object_name_lower
            in issue_text.lower()
        ):
            matching_issues.append(
                issue_text
            )

    return matching_issues


def format_qc_detail_label(key):
    """
    Converts dictionary keys into readable UI labels.

    Example:
        loose_vertex_count -> Loose Vertex Count
    """
    return (
        str(key)
        .replace("_", " ")
        .strip()
        .title()
    )


def format_qc_detail_value(
        value,
        maximum_list_items=20,
    ):
    """
    Converts a QC result value into compact readable text.
    """
    if value is None:
        return "None"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, float):
        return "{:.6g}".format(value)

    if isinstance(value, (list, tuple, set)):
        values = list(value)

        if not values:
            return "None"

        visible_values = values[
            :maximum_list_items
        ]

        text = ", ".join(
            str(item)
            for item in visible_values
        )

        hidden_count = (
            len(values)
            - len(visible_values)
        )

        if hidden_count > 0:
            text += (
                " ... and {} more"
            ).format(
                hidden_count
            )

        return text

    return str(value)


def draw_wrapped_qc_text(
        layout,
        text,
        icon="NONE",
        width=75,
    ):
    """
    Draws multiline text inside Blender UI layouts.

    Blender labels do not automatically wrap, so this breaks long strings
    into reasonably sized rows.
    """
    import textwrap

    text = str(text or "")

    source_lines = (
        text.splitlines()
        if text
        else [""]
    )

    first_line = True

    for source_line in source_lines:
        wrapped_lines = textwrap.wrap(
            source_line,
            width=max(
                20,
                int(width),
            ),
            replace_whitespace=False,
            drop_whitespace=True,
        )

        if not wrapped_lines:
            wrapped_lines = [""]

        for wrapped_line in wrapped_lines:
            layout.label(
                text=wrapped_line,
                icon=(
                    icon
                    if first_line
                    else "NONE"
                ),
            )

            first_line = False


def draw_qc_result_dictionary(
        layout,
        data,
        level=0,
    ):
    """
    Recursively displays serialized QC result data.

    Nested dictionaries receive their own boxes. Lists of dictionaries are
    displayed as numbered entries.
    """
    if not isinstance(data, dict):
        draw_wrapped_qc_text(
            layout,
            format_qc_detail_value(data),
        )
        return

    for key, value in data.items():
        label = format_qc_detail_label(
            key
        )

        # -----------------------------------------------------
        # Nested dictionary
        # -----------------------------------------------------

        if isinstance(value, dict):
            sub_box = layout.box()

            sub_box.label(
                text=label,
                icon="DISCLOSURE_TRI_DOWN",
            )

            if value:
                draw_qc_result_dictionary(
                    sub_box,
                    value,
                    level=level + 1,
                )
            else:
                sub_box.label(
                    text="No data"
                )

            continue

        # -----------------------------------------------------
        # List containing dictionaries
        # -----------------------------------------------------

        if (
            isinstance(value, (list, tuple))
            and value
            and all(
                isinstance(item, dict)
                for item in value
            )
        ):
            list_box = layout.box()

            list_box.label(
                text="{} ({})".format(
                    label,
                    len(value),
                ),
                icon="LINENUMBERS_ON",
            )

            maximum_entries = 20

            for list_index, list_item in enumerate(
                value[:maximum_entries]
            ):
                item_box = list_box.box()

                item_box.label(
                    text="Item {}".format(
                        list_index + 1
                    )
                )

                draw_qc_result_dictionary(
                    item_box,
                    list_item,
                    level=level + 1,
                )

            if len(value) > maximum_entries:
                list_box.label(
                    text="{} additional entries hidden.".format(
                        len(value)
                        - maximum_entries
                    ),
                    icon="INFO",
                )

            continue

        # -----------------------------------------------------
        # Simple value
        # -----------------------------------------------------

        value_text = format_qc_detail_value(
            value
        )

        row = layout.row(
            align=True
        )

        split = row.split(
            factor=0.38,
            align=True,
        )

        split.label(
            text="{}:".format(label)
        )

        value_column = split.column(
            align=True
        )

        draw_wrapped_qc_text(
            value_column,
            value_text,
            width=55,
        )
