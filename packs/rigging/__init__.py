"""Scriptronaut Rigging Pack."""

bl_info = {
    "name": "Scriptronaut QC Rigging Pack",
    "author": "Scriptronaut",
    "version": (0, 1, 0),
    "blender": (4, 3, 0),
    "location": "Scriptronaut QC Checker",
    "description": "Rigging Pack for the Scriptronaut registered-check API",
    "category": "Scriptronaut",
}

from pathlib import Path


PACK_ID = "scriptronaut_rigging_pack"
PACK_NAME = "Rigging Pack"


def register():
    import scriptronaut_qc_api

    checks_path = os.path.join(
        os.path.dirname(__file__),
        "checks",
    )

    scriptronaut_qc_api.register_check_pack(
        pack_id=PACK_ID,
        name=PACK_NAME,
        checks_path=checks_path,
        version="1.0.0",
    )


def unregister():
    import scriptronaut_qc_api

    scriptronaut_qc_api.unregister_check_pack(
        PACK_ID
    )
