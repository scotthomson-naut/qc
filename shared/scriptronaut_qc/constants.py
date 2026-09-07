from pathlib import Path
import bpy

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
CHECKS_DIR = str(EXTENSION_ROOT / "checks")

# Backward-compatibility alias for older internal/external code.
# New code should use CHECKS_DIR.
QC_MODULES_DIR = CHECKS_DIR
COMMON_CATEGORY = "common"
CHECK_SETTINGS_FILE = "check_settings.json"
CHECK_PREFERENCES_DIR = bpy.utils.user_resource(
    "CONFIG", path="scriptronaut_qc", create=True
)
CHECK_PREFERENCES_FILE = str(
    Path(CHECK_PREFERENCES_DIR) / "check_preferences.json"
)
TIER = "Core"
VERSION = "1.0.0"

# Temporary private-beta links. Remove these and the feedback operator when
# the beta feedback workflow is retired.
BETA_FEEDBACK_URL = "https://scriptronaut.com/beta-feedback.html"
BETA_DOCUMENTATION_URL = "https://scriptronaut.com/docs/qc_checker/core/index.html"

QC_IS_RUNNING = False
QC_IGNORE_CHANGES_UNTIL = 0.0

# Alpha
SCENE_TRIANGLE_LIMIT = 1000000
