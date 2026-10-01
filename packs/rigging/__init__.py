"""Scriptronaut Rigging Pack."""

import importlib
import os
import sys


bl_info = {
    "name": "Scriptronaut QC Rigging Pack",
    "author": "Scriptronaut",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "Scriptronaut QC Checker",
    "description": "Rigging Pack for the Scriptronaut registered-check API",
    "category": "Scriptronaut",
}

PACK_ID = "scriptronaut_qc_rigging_pack"
PACK_NAME = "Rigging Pack"

_QC_EXTENSION_IDS = (
    "scriptronaut_qc_checker_pro",
    "scriptronaut_qc_checker_core",
)


def _get_qc_api():
    """Returns the public API from the loaded QC Checker extension."""
    for extension_id in _QC_EXTENSION_IDS:
        suffix = ".{}.scriptronaut_qc.api".format(
            extension_id
        )

        for module_name, module in tuple(
            sys.modules.items()
        ):
            if (
                module_name.endswith(suffix)
                and module is not None
            ):
                return module

        # Normal Blender Extension namespace.
        module_name = (
            "bl_ext.user_default."
            "{}.scriptronaut_qc.api".format(
                extension_id
            )
        )
        try:
            return importlib.import_module(
                module_name
            )
        except ModuleNotFoundError:
            pass

    raise RuntimeError(
        "Scriptronaut QC Checker Core or Pro must be "
        "installed and enabled before the Rigging Pack."
    )


def register():
    """Registers this Rigging Pack with QC Checker."""
    qc_api = _get_qc_api()

    checks_path = os.path.join(
        os.path.dirname(__file__),
        "checks",
    )

    qc_api.register_check_pack(
        pack_id=PACK_ID,
        name=PACK_NAME,
        checks_path=checks_path,
        version="1.0.0",
    )


def unregister():
    """Unregisters this Rigging Pack from QC Checker."""
    qc_api = _get_qc_api()
    qc_api.unregister_check_pack(
        PACK_ID
    )
