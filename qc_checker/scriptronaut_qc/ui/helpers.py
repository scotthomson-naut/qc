"""Scriptronaut QC Checks internal module."""

import textwrap


def draw_wrapped_text(
        layout,
        text,
        width=80,
        icon="INFO",
    ):
    """
    Draw word-wrapped text in a Blender layout.

    Args:
        layout:
            Blender UI layout.

        text (str):
            Text to display.

        width (int):
            Approximate maximum characters per line.

        icon (str):
            Icon displayed on the first line.
    """
    if not text:
        return

    lines = textwrap.wrap(
        str(text),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )

    for index, line in enumerate(
        lines
    ):
        row = layout.row()

        row.label(
            text=line,
            icon=(
                icon
                if index == 0
                else "BLANK1"
            ),
        )
