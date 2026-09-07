"""Scriptronaut QC operators."""

from . import (
    feedback,
    fix,
    info,
    run,
    selection,
    settings,
)

CLASSES = (
    *feedback.CLASSES,
    *fix.CLASSES,
    *info.CLASSES,
    *run.CLASSES,
    *selection.CLASSES,
    *settings.CLASSES,
)
