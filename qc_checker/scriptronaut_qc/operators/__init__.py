"""Scriptronaut QC operators."""

from . import (
    category_editor,
    fix,
    info,
    run,
    selection,
    settings,
)

CLASSES = (
    *category_editor.CLASSES,
    *fix.CLASSES,
    *info.CLASSES,
    *run.CLASSES,
    *selection.CLASSES,
    *settings.CLASSES,
)