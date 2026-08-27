"""Scriptronaut QC operators."""

from . import (
    fix,
    info,
    run,
    selection,
    settings,
)

CLASSES = (
    *fix.CLASSES,
    *info.CLASSES,
    *run.CLASSES,
    *selection.CLASSES,
    *settings.CLASSES,
)