"""Small in-memory diagnostic buffer used by private beta feedback."""

from __future__ import annotations

from datetime import datetime, timezone
import traceback


_LAST_TRACEBACK = ""
_LAST_TRACEBACK_TIME = ""


def record_traceback(traceback_text: str) -> None:
    """Remember the latest Python traceback for the current Blender session."""
    global _LAST_TRACEBACK
    global _LAST_TRACEBACK_TIME

    text = str(traceback_text or "").strip()
    if not text:
        return

    _LAST_TRACEBACK = text
    _LAST_TRACEBACK_TIME = datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )


def get_last_traceback() -> tuple[str, str]:
    """Return ``(traceback, recorded_at_utc)`` for the current session."""
    return _LAST_TRACEBACK, _LAST_TRACEBACK_TIME


def capture_current_traceback() -> str:
    """Format, record, and return the exception currently being handled."""
    traceback_text = traceback.format_exc()
    record_traceback(traceback_text)
    return traceback_text


def clear_last_traceback() -> None:
    """Clear the diagnostic buffer."""
    global _LAST_TRACEBACK
    global _LAST_TRACEBACK_TIME

    _LAST_TRACEBACK = ""
    _LAST_TRACEBACK_TIME = ""
