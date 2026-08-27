bl_info = {
    "name": "Scriptronaut QC Rigging Pack",
    "author": "Scriptronaut",
    "version": (0, 1, 0),
    "blender": (4, 3, 0),
    "location": "Scriptronaut QC Checker",
    "description": "Rigging pack for the Scriptronaut registered-check API",
    "category": "Scriptronaut",
}

from pathlib import Path


PACK_ID = "scriptronaut_rigging_pack"


def register():
    try:
        import scriptronaut_qc_api
    except ImportError as error:
        raise RuntimeError(
            "Scriptronaut QC Core must be enabled before the Pack."
        ) from error

    checks_path = str(
        Path(__file__).resolve().parent
        / "checks"
    )

    scriptronaut_qc_api.register_check_pack(
        pack_id=PACK_ID,
        name="Scriptronaut QC Rigging Pack",
        checks_path=checks_path,
        version="0.1.0",
        priority=100,
        metadata={
            "kind": "rigging",
        },
    )


def unregister():
    try:
        import scriptronaut_qc_api
    except ImportError:
        return

    scriptronaut_qc_api.unregister_check_pack(
        PACK_ID
    )
