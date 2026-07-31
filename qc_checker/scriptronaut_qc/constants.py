from pathlib import Path
import bpy

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
QC_MODULES_DIR = str(EXTENSION_ROOT / "qc_modules")
COMMON_CATEGORY = "common"
CHECK_SETTINGS_FILE = "check_settings.json"
CHECK_PREFERENCES_DIR = bpy.utils.user_resource(
    "CONFIG", path="scriptronaut_qc", create=True
)
CHECK_PREFERENCES_FILE = str(
    Path(CHECK_PREFERENCES_DIR) / "check_preferences.json"
)
TIER = "Core"

QC_IS_RUNNING = False
QC_IGNORE_CHANGES_UNTIL = 0.0
