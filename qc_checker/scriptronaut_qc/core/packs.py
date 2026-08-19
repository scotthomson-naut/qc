"""Registered QC check-pack services."""

from collections import OrderedDict
import os


_PACKS = OrderedDict()


def _notify_registry_changed():
    """
    Requests a QC category refresh without creating an import cycle.
    """
    try:
        from .runtime import (
            notify_check_pack_registry_changed,
        )

        notify_check_pack_registry_changed()

    except Exception as error:
        print(
            "Scriptronaut QC pack refresh notification failed: {}".format(
                error
            )
        )


def register_check_pack(
        pack_id,
        name,
        checks_path,
        version="0.0.0",
        priority=100,
        metadata=None,
    ):
    """
    Registers a QC check pack.

    A check pack is simply a directory containing QC category folders:

        checks/
            animation/
                action_present.py
            rigging/
                ...
            common/
                ...

    Args:
        pack_id (str):
            Stable unique identifier, for example:
                "scriptronaut_animation"

        name (str):
            Friendly pack name.

        checks_path (str):
            Absolute path to the directory containing category folders.

        version (str):
            Pack version.

        priority (int):
            Lower values are discovered first.

        metadata (dict | None):
            Optional future-facing pack metadata.

    Returns:
        dict:
            Registered pack record.

    Raises:
        ValueError:
            Invalid id/path or conflicting registration.
    """
    pack_id = str(
        pack_id
    ).strip()

    if not pack_id:
        raise ValueError(
            "QC pack_id cannot be empty."
        )

    checks_path = os.path.abspath(
        os.path.expanduser(
            str(
                checks_path
            )
        )
    )

    if not os.path.isdir(
        checks_path
    ):
        raise ValueError(
            "QC pack checks path does not exist: {}".format(
                checks_path
            )
        )

    existing = _PACKS.get(
        pack_id
    )

    if (
        existing is not None
        and os.path.normcase(
            existing["checks_path"]
        )
        != os.path.normcase(
            checks_path
        )
    ):
        raise ValueError(
            (
                "QC pack '{}' is already registered from '{}', "
                "cannot also register '{}'."
            ).format(
                pack_id,
                existing["checks_path"],
                checks_path,
            )
        )

    record = {
        "pack_id":
            pack_id,

        "name":
            str(
                name
                or pack_id
            ),

        "checks_path":
            checks_path,

        "version":
            str(
                version
                or "0.0.0"
            ),

        "priority":
            int(
                priority
            ),

        "metadata":
            dict(
                metadata
                or {}
            ),
    }

    _PACKS[
        pack_id
    ] = record

    print(
        "Scriptronaut QC registered check pack: {} {} -> {}".format(
            record["name"],
            record["version"],
            record["checks_path"],
        )
    )

    _notify_registry_changed()

    return dict(
        record
    )


def unregister_check_pack(
        pack_id,
    ):
    """
    Unregisters one QC check pack.

    Returns:
        bool:
            True when a pack was removed.
    """
    pack_id = str(
        pack_id
    ).strip()

    record = _PACKS.pop(
        pack_id,
        None,
    )

    if record is None:
        return False

    print(
        "Scriptronaut QC unregistered check pack: {}".format(
            record["name"]
        )
    )

    _notify_registry_changed()

    return True


def get_registered_check_packs():
    """
    Returns registered check packs in deterministic discovery order.
    """
    packs = [
        dict(
            record
        )
        for record in _PACKS.values()
    ]

    return sorted(
        packs,
        key=lambda item: (
            item["priority"],
            item["pack_id"],
        ),
    )


def get_registered_check_pack(
        pack_id,
    ):
    """
    Returns one registered pack record or None.
    """
    record = _PACKS.get(
        str(
            pack_id
        )
    )

    if record is None:
        return None

    return dict(
        record
    )


def is_check_pack_registered(
        pack_id,
    ):
    """
    Returns whether a pack id is currently registered.
    """
    return str(
        pack_id
    ) in _PACKS


def clear_registered_check_packs():
    """
    Clears the registry.

    Intended for addon shutdown/reload.
    """
    _PACKS.clear()
