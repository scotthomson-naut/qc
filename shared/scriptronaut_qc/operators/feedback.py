"""Private-beta feedback launcher."""

from __future__ import annotations

import platform
from pathlib import Path
from urllib.parse import urlencode

import bpy
from bpy.types import Operator

from ..constants import BETA_FEEDBACK_URL, TIER, VERSION
from ..utils.diagnostics import get_last_traceback


MAX_TRACEBACK_URL_CHARS = 6000


class SCRIPTRONAUT_OT_QC_BetaFeedback(Operator):
    """Open the private-beta feedback form with useful context prefilled."""

    bl_idname = "scriptronaut.qc_beta_feedback"
    bl_label = "Send Beta Feedback"
    bl_description = (
        "Open the private-beta feedback form with QC Checker and Blender "
        "details prefilled"
    )

    def execute(self, context):
        scene = context.scene
        settings = getattr(
            scene,
            "scriptronaut_qc_settings",
            None,
        )
        checks = getattr(
            scene,
            "scriptronaut_qc_checks",
            (),
        )

        category = ""
        check_id = ""
        check_name = ""
        issue_text = ""

        if settings is not None:
            category = str(
                getattr(settings, "category", "")
            )
            check_index = int(
                getattr(settings, "check_index", -1)
            )

            if 0 <= check_index < len(checks):
                item = checks[check_index]
                check_id = str(
                    getattr(item, "check_id", "")
                    or getattr(item, "name", "")
                )
                check_name = str(
                    getattr(item, "display_name", "")
                    or getattr(item, "name", "")
                )
                issue_text = str(
                    getattr(item, "issues", "")
                )

        traceback_text, traceback_time = get_last_traceback()
        if not traceback_text and "Traceback (most recent call last)" in issue_text:
            traceback_text = issue_text

        blend_path = Path(
            bpy.data.filepath
        )

        query = urlencode(
            {
                "source": "blender",
                "tier": TIER,
                "qc_version": VERSION,
                "blender_version": bpy.app.version_string,
                "operating_system": platform.platform(),
                "blend_file": blend_path.name if blend_path.name else "Unsaved",
                "category": category,
                "check_id": check_id,
                "check_name": check_name,
                "traceback": traceback_text[-MAX_TRACEBACK_URL_CHARS:],
                "traceback_time": traceback_time,
            }
        )

        # Use a URL fragment rather than a query string. Browsers make the
        # fragment available to the form script but do not send it in the
        # initial HTTP request or ordinary web-server access log.
        bpy.ops.wm.url_open(
            url="{}#{}".format(
                BETA_FEEDBACK_URL,
                query,
            )
        )

        return {"FINISHED"}


CLASSES = (
    SCRIPTRONAUT_OT_QC_BetaFeedback,
)
