bl_info = {
    "name": "Scriptronaut QC Checks",
    "author": "Scriptronaut",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > Scriptronaut > QC Checks",
    "description": "Run QC check scripts from categorized folders",
    "category": "Scriptronaut",
}

# Python imports
import os
import glob
import json
import traceback
import importlib.util

# Blender imports
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    EnumProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy.app.handlers import persistent

# Constants
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
QC_MODULES_DIR = os.path.join(ADDON_DIR, "qc_modules")
COMMON_CATEGORY = "common"
CHECK_SETTINGS_FILE = "check_settings.json"

# Tier Level
TIER = "Pro"

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def load_check_list(folder_path):
    """
    Loads the optional CHECK_SETTINGS_FILE configuration.

    Args:
        folder_path (str): Root QC modules folder.

    Returns:
        dict: Category names mapped to lists of script names.
              Returns an empty dictionary when the file is missing
              or invalid.
    """
    json_path = os.path.join(folder_path, CHECK_SETTINGS_FILE)

    if not os.path.isfile(json_path):
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as stream:
            data = json.load(stream)

        return data if isinstance(data, dict) else {}

    except Exception:
        print("Could not read QC check list:")
        print(traceback.format_exc())
        return {}


def save_check_list(folder_path, check_list):
    """
    Saves the QC category configuration to CHECK_SETTINGS_FILE.

    Args:
        folder_path (str): Root QC modules directory.
        check_list (dict): Category names mapped to script-name lists.

    Returns:
        tuple[bool, str]: Success state and error message.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return False, "QC modules folder does not exist."

    json_path = os.path.join(folder_path, CHECK_SETTINGS_FILE)

    try:
        with open(json_path, "w", encoding="utf-8") as stream:
            json.dump(check_list, stream, indent=4, sort_keys=True)
        return True, ""
    except Exception:
        return False, traceback.format_exc()


def sanitize_category_name(category_name):
    """
    Converts a user-entered category into a safe JSON key.
    """
    category_name = category_name.strip().lower()
    category_name = category_name.replace("-", "_")
    category_name = "_".join(category_name.split())
    return "".join(
        character
        for character in category_name
        if character.isalnum() or character == "_"
    )


def load_module_from_path(module_name, script_path):
    """
    Loads a Python module from a file path.

    Args:
        module_name (str): Temporary name to assign to the module.
        script_path (str): Full path to the Python script.

    Returns:
        module: The imported Python module.
    """
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_categories(folder_path, use_json=False):
    """
    Returns available QC categories.

    When JSON mode is enabled, categories come from CHECK_SETTINGS_FILE.
    Otherwise categories come from folders under qc_modules.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        list[str]: Sorted category names.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    if use_json:
        check_list = load_check_list(folder_path)

        if not check_list:
            return []

        return sorted(
            category
            for category, checks in check_list.items()
            if isinstance(category, str)
            and isinstance(checks, list)
        )

    return sorted([
        os.path.basename(folder)
        for folder in glob.glob(os.path.join(folder_path, "*"))
        if (
            os.path.isdir(folder)
            and os.path.basename(folder) not in {
                "__pycache__",
                COMMON_CATEGORY,
            }
            and glob.glob(os.path.join(folder, "*.py"))
        )
    ])


def get_scripts(folder_path, category, use_json=False):
    """
    Returns the QC scripts assigned to a category.

    JSON mode:
        - Discovers all scripts recursively.
        - Requires globally unique script names.
        - Uses CHECK_SETTINGS_FILE to assign scripts to categories.
        - Ignores missing script entries and prints warnings.

    Folder mode:
        - Loads all scripts from common.
        - Loads all scripts from the selected category.

    Args:
        folder_path (str): Root QC modules directory.
        category (str): Selected category.

    Returns:
        list[dict]: Script metadata records.
    """
    if (
        not folder_path
        or not category
        or category in {"NONE", "----------------"}
    ):
        return []

    registry, duplicate_names = discover_check_scripts(folder_path)

    if duplicate_names:
        print("QC checks contain duplicate script names:")

        for script_name, paths in duplicate_names.items():
            print("  Duplicate check: {}".format(script_name))

            for path in paths:
                print("    {}".format(path))

        # Do not continue because JSON references would be ambiguous.
        return []

    if use_json:
        check_list = load_check_list(folder_path)
        configured_names = check_list.get(category, [])

        if not isinstance(configured_names, list):
            print(
                'QC category "{}" must contain a JSON list.'.format(
                    category
                )
            )
            return []

        script_records = []
        added_names = set()

        for script_name in configured_names:
            if not isinstance(script_name, str):
                print(
                    "Invalid QC script entry in category '{}': {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            if script_name in added_names:
                print(
                    "Duplicate JSON entry ignored: {} -> {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            script_data = registry.get(script_name)

            if script_data is None:
                print(
                    "QC script listed in JSON but not found: "
                    "{} -> {}".format(
                        category,
                        script_name,
                    )
                )
                continue

            added_names.add(script_name)
            script_records.append(dict(script_data))

        return script_records

    # ---------------------------------------------------------
    # Folder-based fallback
    # ---------------------------------------------------------
    script_records = []

    source_categories = [
        COMMON_CATEGORY,
        category,
    ]

    for script_data in registry.values():
        if script_data["source_category"] in source_categories:
            script_records.append(dict(script_data))

    return sorted(
        script_records,
        key=lambda item: (
            item["source_category"] != COMMON_CATEGORY,
            item["name"],
        ),
    )


def normalize_check_result(result):
    """
    Converts a QC check result into a standard dictionary format.

    Supported return types:
        None
        str
        list
        tuple
        dict

    Returns:
        dict: Dictionary containing at least an "issues" key.
    """
    if result is None:
        return {"issues": []}

    if isinstance(result, str):
        return {"issues": [result]}

    if isinstance(result, (list, tuple)):
        return {"issues": list(result)}

    if isinstance(result, dict):
        if "issues" not in result:
            result["issues"] = []
        return result

    return {"issues": [str(result)]}


def get_issues_from_result(result_data):
    """
    Extracts the issues list from normalized result data.

    Args:
        result_data (dict): Normalized QC result.

    Returns:
        list[str]: List of issue strings.
    """
    issues = result_data.get("issues", [])

    if issues is None:
        return []

    if isinstance(issues, str):
        return [issues]

    if isinstance(issues, (list, tuple)):
        return list(issues)

    return [str(issues)]


def result_data_to_json(result_data):
    """
    Serializes QC result data into JSON.

    Args:
        result_data (dict): Result dictionary.

    Returns:
        str: JSON representation of the result.
    """
    try:
        return json.dumps(result_data, indent=4)
    except Exception:
        return json.dumps({
            "issues": ["Result data could not be converted to JSON."],
            "raw_result": str(result_data),
        }, indent=4)


def result_data_from_json(json_text):
    """
    Deserializes JSON into QC result data.

    Args:
        json_text (str): JSON string.

    Returns:
        dict: Parsed result dictionary.
    """
    if not json_text:
        return {}

    try:
        return json.loads(json_text)
    except Exception:
        return {}


def refresh_issues_display(context):
    """
    Updates the Issues display based on the currently selected QC check.

    Args:
        context (bpy.types.Context): Blender context.
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    checks = scene.scriptronaut_qc_checks

    if settings.check_index < 0 or settings.check_index >= len(checks):
        settings.issues_display = ""
        return

    item = checks[settings.check_index]

    if item.issues:
        settings.issues_display = item.issues
    else:
        settings.issues_display = "No issues found."


def load_qc_category(context):
    """
    Returns the EnumProperty items for the QC category dropdown.

    Args:
        context (bpy.types.Context): Blender context.

    Returns:
        list[tuple]: EnumProperty item list.
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    checks = scene.scriptronaut_qc_checks

    old_index = settings.check_index

    checks.clear()
    settings.issues_display = ""

    folder_path = settings.folder_path
    category = settings.category

    if not os.path.isdir(folder_path):
        return False, "QC folder does not exist."

    scripts = get_scripts(
        folder_path,
        category,
        use_json=settings.use_check_settings,
    )

    for script_data in scripts:
        item = checks.add()
        item.name = script_data["name"]
        item.script_path = script_data["script_path"]
        item.source_category = script_data["source_category"]

        item.selected = True
        item.status = "NOT_RUN"
        item.has_fix = False
        item.issues = "Not run yet."
        item.result_data = "{}"

    if len(checks) > 0:
        settings.check_index = min(old_index, len(checks) - 1)
    else:
        settings.check_index = 0

    refresh_issues_display(context)

    return True, ""


def qc_category_items(self, context):
    """
    Returns the EnumProperty items for the QC category dropdown.

    Args:
        context (bpy.types.Context): Blender context.

    Returns:
        list[tuple]: EnumProperty item list.
    """
    categories = get_categories(
        self.folder_path,
        use_json=self.use_check_settings,
    )

    if not categories:
        return [("NONE", "No Categories Found", "")]

    return [(category, category, "") for category in categories]


def qc_editor_category_items(self, context):
    """
    Returns categories stored in CHECK_SETTINGS_FILE for the editor.
    """
    if context is None or context.scene is None:
        return [("NONE", "No Categories", "")]

    settings = context.scene.scriptronaut_qc_settings
    check_list = load_check_list(settings.folder_path)
    categories = sorted(
        category
        for category, script_names in check_list.items()
        if isinstance(category, str) and isinstance(script_names, list)
    )

    if not categories:
        return [("NONE", "No Categories", "")]

    return [
        (category, category.replace("_", " ").title(), "")
        for category in categories
    ]


def populate_qc_editor(context, category=None):
    """
    Populates the editor with all discovered scripts.
    """
    scene = context.scene
    settings = scene.scriptronaut_qc_settings
    editor_items = scene.scriptronaut_qc_editor_items
    editor_items.clear()

    registry, duplicate_names = discover_check_scripts(settings.folder_path)
    if duplicate_names:
        lines = []
        for script_name, paths in duplicate_names.items():
            lines.append("{}: {}".format(script_name, ", ".join(paths)))
        return False, "Duplicate script names found:\n{}".format("\n".join(lines))

    check_list = load_check_list(settings.folder_path)
    if category is None:
        category = settings.editor_category

    assigned_names = set(
        check_list.get(category, [])
        if category and category != "NONE"
        else []
    )

    for script_name in sorted(registry):
        script_data = registry[script_name]
        item = editor_items.add()
        item.name = script_name
        item.script_path = script_data["script_path"]
        item.source_category = script_data["source_category"]
        item.selected = script_name in assigned_names

    settings.editor_index = 0
    return True, ""


def update_use_check_settings(self, context):
    """
    Reloads categories when JSON assignment mode changes.
    """
    if context is None or context.scene is None:
        return

    checks = context.scene.scriptronaut_qc_checks
    checks.clear()
    self.issues_display = ""

    categories = get_categories(
        self.folder_path,
        use_json=self.use_check_settings,
    )

    if not categories:
        try:
            self.category = "NONE"
        except TypeError:
            pass
        return

    if self.category not in categories:
        self.category = categories[0]
    else:
        load_qc_category(context)


def update_qc_folder_path(self, context):
    """
    Callback executed when the QC folder path changes.

    Reloads available categories and refreshes the QC check list.

    Args:
        context (bpy.types.Context): Blender context.
    """
    categories = get_categories(
        self.folder_path,
        use_json=self.use_check_settings,
    )

    if categories:
        self.category = categories[0]
        load_qc_category(context)
    else:
        context.scene.scriptronaut_qc_checks.clear()
        self.category = "NONE"
        self.issues_display = ""


def update_qc_category(self, context):
    """
    Callback executed when the selected QC category changes.

    Loads the QC scripts contained in the selected category.

    Args:
        context (bpy.types.Context): Blender context.
    """
    if self.category != "NONE":
        load_qc_category(context)


def update_qc_check_index(self, context):
    """
    Callback executed when the selected QC check changes.

    Refreshes the displayed issues.

    Args:
        context (bpy.types.Context): Blender context.
    """
    refresh_issues_display(context)


def initialize_qc_checks_timer():
    """
    Timer wrapper used when enabling the addon.
    """
    initialize_qc_checks_after_load()
    return None


def validate_check_configuration(folder_path, use_json=False):
    """
    Validates discovered QC scripts and the optional JSON configuration.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        dict:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
        }
    """
    errors = []
    warnings = []

    registry, duplicate_names = discover_check_scripts(folder_path)

    for script_name, paths in duplicate_names.items():
        errors.append(
            "Duplicate QC script name '{}': {}".format(
                script_name,
                ", ".join(paths),
            )
        )

    if use_json:
        check_list = load_check_list(folder_path)

        if not check_list:
            errors.append(
                "JSON mode is enabled, but CHECK_SETTINGS_FILE is missing "
                "or invalid."
            )
        else:
            for category, script_names in check_list.items():
                if not isinstance(script_names, list):
                    errors.append(
                        "Category '{}' must contain a list.".format(
                            category
                        )
                    )
                    continue

                seen_names = set()

                for script_name in script_names:
                    if not isinstance(script_name, str):
                        errors.append(
                            "Category '{}' contains a non-string entry: "
                            "{}".format(category, script_name)
                        )
                        continue

                    if script_name in seen_names:
                        warnings.append(
                            "Category '{}' lists '{}' more than once.".format(
                                category,
                                script_name,
                            )
                        )
                        continue

                    seen_names.add(script_name)

                    if script_name not in registry:
                        errors.append(
                            "Category '{}' references missing check "
                            "'{}'.".format(
                                category,
                                script_name,
                            )
                        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def discover_check_scripts(folder_path):
    """
    Finds every QC check script under the QC modules directory.

    Script names must be unique across all folders.

    Args:
        folder_path (str): Root QC modules directory.

    Returns:
        tuple:
            registry (dict): Script names mapped to script metadata.
            duplicate_names (dict): Duplicate names mapped to paths.

        Example registry:
        {
            "freeze_transforms": {
                "name": "freeze_transforms",
                "script_path": ".../common/freeze_transforms.py",
                "source_category": "common",
            }
        }
    """
    registry = {}
    duplicate_names = {}

    if not folder_path or not os.path.isdir(folder_path):
        return registry, duplicate_names

    pattern = os.path.join(folder_path, "**", "*.py")

    for script_path in sorted(glob.glob(pattern, recursive=True)):
        filename = os.path.basename(script_path)

        if filename == "__init__.py":
            continue

        script_name = os.path.splitext(filename)[0]

        relative_folder = os.path.relpath(
            os.path.dirname(script_path),
            folder_path,
        )

        source_category = relative_folder.replace("\\", "/")

        script_data = {
            "name": script_name,
            "script_path": os.path.abspath(script_path),
            "source_category": source_category,
        }

        if script_name in registry:
            duplicate_names.setdefault(
                script_name,
                [registry[script_name]["script_path"]],
            )
            duplicate_names[script_name].append(
                script_data["script_path"]
            )
            continue

        registry[script_name] = script_data

    return registry, duplicate_names


def rebuild_failed_objects(context):
    """
    Builds a unique list of objects that failed any QC check.

    Each object stores how many checks it failed.
    """
    scene = context.scene
    checks = scene.scriptronaut_qc_checks
    failed_items = scene.scriptronaut_qc_failed_objects
    settings = scene.scriptronaut_qc_settings

    previous_name = None

    if (
        failed_items
        and 0 <= settings.failed_object_index < len(failed_items)
    ):
        previous_name = (
            failed_items[
                settings.failed_object_index
            ].name
        )

    failed_items.clear()

    object_failures = {}

    for check_index, check_item in enumerate(checks):

        if check_item.status != "FAIL":
            continue

        result_data = result_data_from_json(
            check_item.result_data
        )

        failed_objects = result_data.get(
            "failed_objects",
            {},
        )

        if not isinstance(
            failed_objects,
            dict,
        ):
            continue

        for object_name in failed_objects:

            object_failures.setdefault(
                object_name,
                [],
            ).append(
                check_index
            )

    for object_name in sorted(
        object_failures
    ):
        item = failed_items.add()

        item.name = object_name

        item.failed_check_count = len(
            object_failures[
                object_name
            ]
        )

    # Restore selection when possible.
    settings.failed_object_index = 0

    if previous_name:

        for index, item in enumerate(
            failed_items
        ):
            if item.name == previous_name:

                settings.failed_object_index = (
                    index
                )

                break

    refresh_object_failed_checks(
        context
    )


def refresh_object_failed_checks(context):
    """
    Populates the failed-check list for the currently
    selected object in Object Mode.
    """
    if (
        context is None
        or context.scene is None
    ):
        return

    scene = context.scene

    settings = (
        scene.scriptronaut_qc_settings
    )

    failed_objects = (
        scene.scriptronaut_qc_failed_objects
    )

    object_checks = (
        scene.scriptronaut_qc_object_checks
    )

    checks = (
        scene.scriptronaut_qc_checks
    )

    object_checks.clear()

    if (
        settings.failed_object_index < 0
        or
        settings.failed_object_index
        >= len(failed_objects)
    ):
        return

    object_name = failed_objects[
        settings.failed_object_index
    ].name

    for check_index, check_item in enumerate(
        checks
    ):

        if check_item.status != "FAIL":
            continue

        result_data = result_data_from_json(
            check_item.result_data
        )

        check_failed_objects = (
            result_data.get(
                "failed_objects",
                {},
            )
        )

        if not isinstance(
            check_failed_objects,
            dict,
        ):
            continue

        if object_name not in check_failed_objects:
            continue

        item = object_checks.add()

        item.name = check_item.name
        item.script_path = (
            check_item.script_path
        )
        item.has_fix = (
            check_item.has_fix
        )
        item.check_index = (
            check_index
        )

    settings.object_check_index = 0


def get_filtered_result_for_object(
        result_data,
        object_name,
    ):
    """
    Returns a copy of QC result data containing only
    one failed object.

    This lets existing fix(result_data) implementations
    fix a single object without modification.
    """
    filtered_result = dict(
        result_data
    )

    failed_objects = result_data.get(
        "failed_objects",
        {},
    )

    if not isinstance(
        failed_objects,
        dict,
    ):
        return filtered_result

    if object_name not in failed_objects:

        filtered_result[
            "failed_objects"
        ] = {}

        return filtered_result

    filtered_result[
        "failed_objects"
    ] = {
        object_name:
            failed_objects[
                object_name
            ]
    }

    return filtered_result


def rerun_qc_check_item(item):
    """
    Re-runs one QC check item and updates its stored result.
    """
    script_path = item.script_path

    if not os.path.isfile(
        script_path
    ):
        return False

    try:

        module = load_module_from_path(
            "qc_rerun_{}".format(
                item.name
            ),
            script_path,
        )

        main_function = getattr(
            module,
            "main",
            None,
        )

        if not callable(
            main_function
        ):
            return False

        raw_result = (
            main_function()
        )

        result_data = (
            normalize_check_result(
                raw_result
            )
        )

        result_data[
            "check_name"
        ] = item.name

        result_data[
            "script_path"
        ] = script_path

        issues = (
            get_issues_from_result(
                result_data
            )
        )

        item.result_data = (
            result_data_to_json(
                result_data
            )
        )

        item.has_fix = callable(
            getattr(
                module,
                "fix",
                None,
            )
        )

        if issues:

            item.status = "FAIL"

            item.issues = "\n".join(
                str(issue)
                for issue in issues
            )

        else:

            item.status = "PASS"

            item.issues = (
                "No issues found."
            )

        return True

    except Exception:

        print(
            traceback.format_exc()
        )

        return False


@persistent
def initialize_qc_checks_after_load(_dummy=None):
    """
    Initializes the QC category and script list after a Blender file loads.
    """
    for scene in bpy.data.scenes:
        if not hasattr(scene, "scriptronaut_qc_settings"):
            continue

        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        categories = get_categories(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )

        if not categories:
            checks.clear()
            settings.issues_display = ""
            continue

        if settings.category not in categories:
            settings.category = categories[0]

        # Load using a context override for this scene.
        window = bpy.context.window

        if window is not None:
            with bpy.context.temp_override(
                window=window,
                scene=scene,
            ):
                load_qc_category(bpy.context)


# -------------------------------------------------------------------------
# Properties
# -------------------------------------------------------------------------

class SCRIPTRONAUT_QC_CheckItem(PropertyGroup):
    """
    Stores information for a single QC check displayed in the UI.

    Includes the script path, status, issues, fix availability,
    and serialized result data.
    """
    name: StringProperty(default="")
    script_path: StringProperty(default="")
    selected: BoolProperty(default=True)

    status: EnumProperty(
        name="Status",
        items=[
            ("NOT_RUN", "Not Run", ""),
            ("PASS", "Pass", ""),
            ("FAIL", "Fail", ""),
            ("RUNNING", "Running", ""),
        ],
        default="NOT_RUN",
    )

    source_category: StringProperty(
        name="Source Category",
        default="",
    )

    has_fix: BoolProperty(default=False)
    issues: StringProperty(default="")
    result_data: StringProperty(default="{}")


class SCRIPTRONAUT_QC_EditorItem(PropertyGroup):
    """
    Represents one available QC script in the JSON editor.
    """
    name: StringProperty(name="Script Name", default="")
    script_path: StringProperty(name="Script Path", default="")
    source_category: StringProperty(name="Source Folder", default="")
    selected: BoolProperty(name="Enabled", default=False)


class SCRIPTRONAUT_QC_Settings(PropertyGroup):
    """
    Stores addon settings shared across the QC panel.

    Includes the QC modules folder, selected category,
    active check index, and displayed issue text.
    """
    folder_path: StringProperty(
        name="QC Folder",
        subtype="DIR_PATH",
        default=QC_MODULES_DIR,
    )

    use_check_settings: BoolProperty(
        name="Use Check Settings",
        description=(
            "Use CHECK_SETTINGS_FILE to determine which checks belong "
            "to each category"
        ),
        default=False,
        update=update_use_check_settings,
    )

    mode: EnumProperty(
        name="Mode",
        description="Choose how QC results are viewed and fixed",
        items=[
            (
                "CHECKS",
                "Checks",
                "View checks and fix all failed objects for a check",
                "CHECKMARK",
                0,
            ),
            (
                "OBJECTS",
                "Objects",
                "View failed objects and the checks each object failed",
                "OBJECT_DATA",
                1,
            ),
        ],
        default="CHECKS",
    )

    failed_object_index: IntProperty(
        name="Failed Object Index",
        default=0,
        update=lambda self, context: refresh_object_failed_checks(context),
    )

    object_check_index: IntProperty(
        name="Object Check Index",
        default=0,
    )

    editor_category: EnumProperty(
        name="Category",
        description="Category to edit",
        items=qc_editor_category_items,
    )

    editor_new_category: StringProperty(
        name="New Category",
        description="Optional new category name",
        default="",
    )

    editor_index: IntProperty(name="Editor Index", default=0)

    category: EnumProperty(
        name="Category",
        description="QC category folder",
        items=qc_category_items,
        update=update_qc_category,
    )

    check_index: IntProperty(
        default=0,
        update=update_qc_check_index,
    )

    issues_display: StringProperty(
        name="Issues",
        default="",
    )


# -------------------------------------------------------------------------
# UI List
# -------------------------------------------------------------------------

class SCRIPTRONAUT_UL_QC_Checks(UIList):
    """
    Custom UIList used to display QC checks, their selection state,
    execution status, and pass/fail icons.
    """
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(align=True)

        if item.status == "PASS":
            icon_name = "CHECKMARK"
            status_text = "Pass"
        elif item.status == "FAIL":
            icon_name = "CANCEL"
            status_text = "Fail"
            row.alert = True
        elif item.status == "RUNNING":
            icon_name = "TIME"
            status_text = "Running"
        else:
            icon_name = "VIEWZOOM"
            #icon_name = "QUESTION"
            status_text = "Not Run"

        # Selection checkbox
        row.prop(item, "selected", text="")

        # Split remaining row:
        # 80% for check name, 20% for status
        split = row.split(factor=0.8, align=True)

        name_column = split.row(align=True)
        status_column = split.row(align=True)

        display_name = item.name

        if item.source_category == COMMON_CATEGORY:
            display_name = "[Common] {}".format(item.name)

        name_column.label(
            text=display_name,
            icon=icon_name,
        )

        status_column.label(
            text=status_text,
        )


class SCRIPTRONAUT_UL_QC_EditorScripts(UIList):
    """Displays discovered QC scripts with selection checkboxes."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        split = row.split(factor=0.65, align=True)
        split.label(text=item.name, icon="FILE_SCRIPT")
        split.label(text=item.source_category)


# -------------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------------

class SCRIPTRONAUT_OT_QC_OpenJsonEditor(Operator):
    """
    Opens the QC JSON category editor.
    """
    bl_idname = "scriptronaut.qc_open_json_editor"
    bl_label = "Edit Check Categories"
    bl_description = "Assign QC scripts to JSON categories"

    def invoke(self, context, event):
        settings = context.scene.scriptronaut_qc_settings
        if not settings.use_check_settings:
            self.report({"WARNING"}, "Enable Use Check Settings first.")
            return {"CANCELLED"}

        check_list = load_check_list(settings.folder_path)
        categories = sorted(check_list.keys())
        if categories:
            try:
                settings.editor_category = categories[0]
            except TypeError:
                pass

        settings.editor_new_category = ""
        success, message = populate_qc_editor(
            context,
            category=settings.editor_category,
        )
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self, width=620)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.scriptronaut_qc_settings

        category_box = layout.box()
        category_box.label(text="Category", icon="FILE_FOLDER")
        category_box.prop(settings, "editor_category", text="Existing")
        category_box.prop(settings, "editor_new_category", text="New")

        row = layout.row(align=True)
        row.operator(
            "scriptronaut.qc_editor_load_category",
            text="Load Category",
            icon="FILE_REFRESH",
        )
        row.operator(
            "scriptronaut.qc_editor_delete_category",
            text="Delete Category",
            icon="TRASH",
        )

        select_row = layout.row(align=True)
        select_row.operator(
            "scriptronaut.qc_editor_select_all",
            text="Select All",
            icon="CHECKBOX_HLT",
        )
        select_row.operator(
            "scriptronaut.qc_editor_select_none",
            text="Select None",
            icon="CHECKBOX_DEHLT",
        )

        layout.template_list(
            "SCRIPTRONAUT_UL_QC_EditorScripts",
            "",
            scene,
            "scriptronaut_qc_editor_items",
            settings,
            "editor_index",
            rows=14,
        )

        selected_count = sum(
            1 for item in scene.scriptronaut_qc_editor_items if item.selected
        )
        layout.label(
            text="{} script(s) selected".format(selected_count),
            icon="INFO",
        )

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        editor_items = scene.scriptronaut_qc_editor_items

        new_category = settings.editor_new_category.strip()
        category = (
            sanitize_category_name(new_category)
            if new_category
            else settings.editor_category
        )

        if not category or category == "NONE":
            self.report({"ERROR"}, "Enter or select a category.")
            return {"CANCELLED"}

        selected_scripts = [
            item.name for item in editor_items if item.selected
        ]

        check_list = load_check_list(settings.folder_path)
        check_list[category] = selected_scripts
        success, message = save_check_list(settings.folder_path, check_list)
        if not success:
            print(message)
            self.report({"ERROR"}, "Could not save CHECK_SETTINGS_FILE.")
            return {"CANCELLED"}

        categories = get_categories(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )
        if category in categories:
            try:
                settings.category = category
            except TypeError:
                pass

        load_qc_category(context)
        self.report(
            {"INFO"},
            'Saved {} check(s) to category "{}".'.format(
                len(selected_scripts), category
            ),
        )
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorLoadCategory(Operator):
    bl_idname = "scriptronaut.qc_editor_load_category"
    bl_label = "Load Category"

    def execute(self, context):
        settings = context.scene.scriptronaut_qc_settings
        success, message = populate_qc_editor(
            context,
            category=settings.editor_category,
        )
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        settings.editor_new_category = ""
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectAll(Operator):
    bl_idname = "scriptronaut.qc_editor_select_all"
    bl_label = "Select All Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_editor_items:
            item.selected = True
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorSelectNone(Operator):
    bl_idname = "scriptronaut.qc_editor_select_none"
    bl_label = "Select No Editor Scripts"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_editor_items:
            item.selected = False
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_EditorDeleteCategory(Operator):
    bl_idname = "scriptronaut.qc_editor_delete_category"
    bl_label = "Delete QC Category"

    def execute(self, context):
        settings = context.scene.scriptronaut_qc_settings
        category = settings.editor_category
        if not category or category == "NONE":
            self.report({"WARNING"}, "No category selected.")
            return {"CANCELLED"}

        check_list = load_check_list(settings.folder_path)
        if category not in check_list:
            self.report({"WARNING"}, "Category was not found.")
            return {"CANCELLED"}

        del check_list[category]
        success, message = save_check_list(settings.folder_path, check_list)
        if not success:
            print(message)
            self.report({"ERROR"}, "Could not update JSON file.")
            return {"CANCELLED"}

        remaining = sorted(check_list.keys())
        if remaining:
            try:
                settings.editor_category = remaining[0]
            except TypeError:
                pass
            populate_qc_editor(context, remaining[0])
        else:
            context.scene.scriptronaut_qc_editor_items.clear()

        self.report({"INFO"}, 'Deleted category "{}".'.format(category))
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_RefreshCategories(Operator):
    """
    Reloads the available QC categories and scripts from disk.
    """
    bl_idname = "scriptronaut.qc_refresh_categories"
    bl_label = "Refresh QC Categories"

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings

        categories = get_categories(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )

        validation = validate_check_configuration(
            settings.folder_path,
            use_json=settings.use_check_settings,
        )

        for warning in validation["warnings"]:
            print("QC warning: {}".format(warning))

        if not validation["valid"]:
            for error in validation["errors"]:
                print("QC error: {}".format(error))

            scene.scriptronaut_qc_checks.clear()
            settings.issues_display = (
                "QC configuration contains errors. "
                "See the system console."
            )

            self.report(
                {"ERROR"},
                "QC configuration contains errors.",
            )
            return {"CANCELLED"}

        if not categories:
            scene.scriptronaut_qc_checks.clear()
            settings.issues_display = ""
            self.report({"ERROR"}, "No QC categories found.")
            return {"CANCELLED"}

        if settings.category == "NONE" or settings.category not in categories:
            settings.category = categories[0]

        success, message = load_qc_category(context)

        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_SelectAll(Operator):
    """
    Selects all QC checks.
    """
    bl_idname = "scriptronaut.qc_select_all"
    bl_label = "Select All Checks"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_checks:
            item.selected = True

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_SelectNone(Operator):
    """
    Deselects all QC checks.
    """
    bl_idname = "scriptronaut.qc_select_none"
    bl_label = "Select None"

    def execute(self, context):
        for item in context.scene.scriptronaut_qc_checks:
            item.selected = False

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_RunSelected(Operator):
    """
    Executes all selected QC scripts and stores the results.

    Each script must implement a main() function.
    """
    bl_idname = "scriptronaut.qc_run_selected"
    bl_label = "Run Selected Checks"

    def execute(self, context):
        scene = context.scene
        checks = scene.scriptronaut_qc_checks

        ran_any = False

        for item in checks:
            if not item.selected:
                continue

            ran_any = True

            item.status = "RUNNING"
            item.issues = "Running..."
            item.result_data = "{}"

            script_path = item.script_path

            if not os.path.isfile(script_path):
                result_data = {
                    "issues": [
                        "Script does not exist:\n{}".format(script_path)
                    ],
                    "script_path": script_path,
                }

                item.status = "FAIL"
                item.issues = "\n".join(result_data["issues"])
                item.result_data = result_data_to_json(result_data)
                continue

            try:
                module_name = "qc_{}".format(item.name)
                module = load_module_from_path(module_name, script_path)

                if not hasattr(module, "main"):
                    result_data = {
                        "issues": ["Missing main() function."],
                        "script_path": script_path,
                    }

                    item.status = "FAIL"
                    item.issues = "\n".join(result_data["issues"])
                    item.result_data = result_data_to_json(result_data)
                    continue

                raw_result = module.main()
                result_data = normalize_check_result(raw_result)

                result_data["check_name"] = item.name
                result_data["script_path"] = script_path

                issues = get_issues_from_result(result_data)

                item.result_data = result_data_to_json(result_data)
                item.has_fix = hasattr(module, "fix")

                if issues:
                    item.status = "FAIL"
                    item.issues = "\n".join(str(x) for x in issues)
                else:
                    item.status = "PASS"
                    item.issues = "No issues found."

            except Exception:
                result_data = {
                    "issues": [traceback.format_exc()],
                    "check_name": item.name,
                    "script_path": script_path,
                }

                item.status = "FAIL"
                item.issues = "\n".join(result_data["issues"])
                item.result_data = result_data_to_json(result_data)

        if not ran_any:
            self.report({"WARNING"}, "No checks selected.")
            return {"CANCELLED"}

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_FixCurrent(Operator):
    """
    Executes the fix() function of the currently selected QC check.

    The fix function receives the stored result data from the
    previous QC execution when supported.
    """
    bl_idname = "scriptronaut.qc_fix_current"
    bl_label = "Fix Current Check"

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        if settings.check_index < 0 or settings.check_index >= len(checks):
            return {"CANCELLED"}

        item = checks[settings.check_index]

        if not item.has_fix:
            self.report({"WARNING"}, "Selected check has no fix.")
            return {"CANCELLED"}

        try:
            module_name = "qc_fix_{}".format(item.name)
            module = load_module_from_path(module_name, item.script_path)

            if not hasattr(module, "fix"):
                item.has_fix = False
                self.report({"ERROR"}, "Missing fix() function.")
                return {"CANCELLED"}

            result_data = result_data_from_json(item.result_data)

            try:
                raw_fix_result = module.fix(result_data)
            except TypeError:
                raw_fix_result = module.fix()

            fix_result_data = normalize_check_result(raw_fix_result)

            fix_result_data["check_name"] = item.name
            fix_result_data["script_path"] = item.script_path
            fix_result_data["previous_result_data"] = result_data

            issues = get_issues_from_result(fix_result_data)

            item.result_data = result_data_to_json(fix_result_data)

            if issues:
                item.status = "FAIL"
                item.issues = "\n".join(str(x) for x in issues)
            else:
                item.status = "PASS"
                item.issues = "Fixed. No issues found."

            refresh_issues_display(context)

        except Exception:
            result_data = {
                "issues": [traceback.format_exc()],
                "check_name": item.name,
                "script_path": item.script_path,
            }

            item.status = "FAIL"
            item.issues = "\n".join(result_data["issues"])
            item.result_data = result_data_to_json(result_data)

            refresh_issues_display(context)
            return {"CANCELLED"}

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_SelectObject(Operator):
    """
    Selects and activates an object associated with a QC issue.
    """

    bl_idname = "scriptronaut.qc_select_object"
    bl_label = "Select QC Object"
    bl_description = "Select this object in the scene"

    object_name: StringProperty(
        name="Object Name",
        default="",
    )

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)

        if obj is None:
            self.report(
                {"ERROR"},
                'Object "{}" no longer exists.'.format(self.object_name),
            )
            return {"CANCELLED"}

        # Ensure the object is visible and selectable.
        try:
            obj.hide_set(False)
        except RuntimeError:
            pass

        obj.hide_viewport = False
        obj.hide_select = False

        # Deselect everything currently selected.
        for selected_obj in context.selected_objects:
            selected_obj.select_set(False)

        # Select and activate the failed object.
        obj.select_set(True)
        context.view_layer.objects.active = obj

        self.report(
            {"INFO"},
            'Selected object: "{}"'.format(obj.name),
        )

        return {"FINISHED"}

# -------------------------------------------------------------------------
# Panel UI
# -------------------------------------------------------------------------

class SCRIPTRONAUT_PT_QC_Checks(Panel):
    """
    Main QC Checks panel displayed in the 3D Viewport sidebar.

    Provides two display modes:

        CHECKS
            View QC checks.
            Run selected checks.
            View all failed objects for the selected check.
            Fix all failed objects for the selected check.

        OBJECTS
            View objects that failed one or more checks.
            View all failed checks for the selected object.
            Fix only the selected check on the selected object.
    """

    bl_label = "QC Checks"
    bl_idname = "SCRIPTRONAUT_PT_QC_Checks"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scriptronaut"

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        checks = (
            scene.scriptronaut_qc_checks
        )

        # ---------------------------------------------------------
        # Tier-level settings
        # ---------------------------------------------------------

        if TIER in [
            "Pro",
            "Studio",
        ]:

            layout.prop(
                settings,
                "use_check_settings",
                text="Use Check Settings",
            )

            editor_row = layout.row()

            editor_row.enabled = (
                settings.use_check_settings
            )

            editor_row.operator(
                "scriptronaut.qc_open_json_editor",
                text="Edit Check Settings",
                icon="PREFERENCES",
            )

        # ---------------------------------------------------------
        # Mode
        # ---------------------------------------------------------

        mode_box = layout.box()

        mode_box.label(
            text="Mode",
            icon="OPTIONS",
        )

        mode_box.prop(
            settings,
            "mode",
            expand=True,
        )

        # ---------------------------------------------------------
        # CHECK MODE
        # ---------------------------------------------------------

        if settings.mode == "CHECKS":

            self.draw_checks_mode(
                context,
                layout,
                settings,
                checks,
            )

        # ---------------------------------------------------------
        # OBJECT MODE
        # ---------------------------------------------------------

        elif settings.mode == "OBJECTS":

            self.draw_objects_mode(
                context,
                layout,
                settings,
                checks,
            )

    # ---------------------------------------------------------------------
    # CHECK MODE
    # ---------------------------------------------------------------------

    def draw_checks_mode(
        self,
        context,
        layout,
        settings,
        checks,
    ):
        """
        Draws the traditional check-oriented QC interface.
        """

        scene = context.scene

        # ---------------------------------------------------------
        # Category
        # ---------------------------------------------------------

        layout.prop(
            settings,
            "category",
            text="Category",
        )

        # ---------------------------------------------------------
        # Select All / None
        # ---------------------------------------------------------

        row = layout.row(
            align=True
        )

        row.operator(
            "scriptronaut.qc_select_all",
            icon="CHECKBOX_HLT",
            text="Select All",
        )

        row.operator(
            "scriptronaut.qc_select_none",
            icon="CHECKBOX_DEHLT",
            text="Select None",
        )

        # ---------------------------------------------------------
        # Check list
        # ---------------------------------------------------------

        layout.template_list(
            "SCRIPTRONAUT_UL_QC_Checks",
            "",
            scene,
            "scriptronaut_qc_checks",
            settings,
            "check_index",
            rows=8,
        )

        # ---------------------------------------------------------
        # Run selected
        # ---------------------------------------------------------

        layout.operator(
            "scriptronaut.qc_run_selected",
            icon="PLAY",
            text="Run Selected Checks",
        )

        # ---------------------------------------------------------
        # Current check
        # ---------------------------------------------------------

        current_item = None

        if (
            checks
            and
            0
            <= settings.check_index
            < len(checks)
        ):
            current_item = checks[
                settings.check_index
            ]

        # ---------------------------------------------------------
        # Fix UI
        # ---------------------------------------------------------

        if current_item is not None:
            if (
                current_item.status
                == "FAIL"
                and
                current_item.has_fix
            ):

                fix_row = layout.row()

                fix_row.operator(
                    "scriptronaut.qc_fix_current",
                    icon="TOOL_SETTINGS",
                    text="Fix Current Check",
                )

            elif (
                current_item.status
                == "FAIL"
                and
                not current_item.has_fix
            ):
                fix_row = layout.row()

                fix_row.enabled = False

                fix_row.operator(
                    "scriptronaut.qc_fix_current",
                    icon="INFO",
                    text="Fix Must Be Done Manually",
                )

            else:
                fix_row = layout.row()

                fix_row.enabled = False

                fix_row.operator(
                    "scriptronaut.qc_fix_current",
                    icon="CHECKMARK",
                    text="All Good",
                )

        # ---------------------------------------------------------
        # Issues
        # ---------------------------------------------------------

        box = layout.box()

        box.label(
            text="Issues:",
            icon="INFO",
        )

        if current_item:
            result_data = (
                result_data_from_json(
                    current_item.result_data
                )
            )

            failed_objects = (
                result_data.get(
                    "failed_objects",
                    {},
                )
            )

            if (
                isinstance(
                    failed_objects,
                    dict,
                )
                and
                failed_objects
            ):
                for (
                    object_name,
                    object_data,
                ) in failed_objects.items():
                    row = box.row(
                        align=True
                    )

                    row.alert = True

                    message = (
                        "Failed: {}".format(
                            object_name
                        )
                    )

                    message_detail = ""

                    # ---------------------------------------------
                    # Optional details
                    # ---------------------------------------------

                    if (
                        isinstance(
                            object_data,
                            dict,
                        )
                    ):
                        if (
                            "ngon_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} N Gons".format(
                                    object_data.get(
                                        "ngon_count"
                                    )
                                )
                            )

                        elif (
                            "poly_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Polys".format(
                                    object_data.get(
                                        "poly_count"
                                    )
                                )
                            )

                        elif (
                            "zero_area_face_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Zero Area UV Faces".format(
                                    object_data.get(
                                        "zero_area_face_count"
                                    )
                                )
                            )

                        elif (
                            "collapsed_edge_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Collapsed UV Edges".format(
                                    object_data.get(
                                        "collapsed_edge_count"
                                    )
                                )
                            )

                        elif (
                            "flipped_face_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Flipped UV Faces".format(
                                    object_data.get(
                                        "flipped_face_count"
                                    )
                                )
                            )

                        elif (
                            "overlapping_face_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Overlapping UV Faces".format(
                                    object_data.get(
                                        "overlapping_face_count"
                                    )
                                )
                            )

                        elif (
                            "small_island_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Small UV Islands".format(
                                    object_data.get(
                                        "small_island_count"
                                    )
                                )
                            )

                        elif (
                            "tiny_shell_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Tiny UV Shells".format(
                                    object_data.get(
                                        "tiny_shell_count"
                                    )
                                )
                            )

                        elif (
                            "oversized_shell_count"
                            in object_data
                        ):
                            message_detail = (
                                "- {} Oversized UV Shells".format(
                                    object_data.get(
                                        "oversized_shell_count"
                                    )
                                )
                            )

                    operator = row.operator(
                        "scriptronaut.qc_select_object",
                        text="{} {}".format(
                            message,
                            message_detail,
                        ),
                        icon="ERROR",
                    )

                    operator.object_name = (
                        object_name
                    )

            elif settings.issues_display:
                for line in (
                    settings.issues_display
                    .split("\n")
                ):
                    box.label(
                        text=line
                    )

            else:
                box.label(
                    text="No issues found.",
                    icon="CHECKMARK",
                )

        else:
            box.label(
                text="No issues selected."
            )

    # ---------------------------------------------------------------------
    # OBJECT MODE
    # ---------------------------------------------------------------------

    def draw_objects_mode(
        self,
        context,
        layout,
        settings,
        checks,
    ):
        """
        Draws QC results organized by failed object.
        """
        scene = context.scene

        failed_objects = (
            scene.scriptronaut_qc_failed_objects
        )

        object_checks = (
            scene.scriptronaut_qc_object_checks
        )

        # ---------------------------------------------------------
        # No results yet
        # ---------------------------------------------------------

        if not checks:
            box = layout.box()

            box.label(
                text="No QC results available.",
                icon="INFO",
            )

            box.label(
                text="Run checks in Checks mode first."
            )

            return

        # ---------------------------------------------------------
        # Failed objects
        # ---------------------------------------------------------

        object_box = layout.box()

        object_box.label(
            text="Failed Objects",
            icon="OBJECT_DATA",
        )

        if not failed_objects:
            object_box.label(
                text="No failed objects.",
                icon="CHECKMARK",
            )

            return

        object_box.template_list(
            "SCRIPTRONAUT_UL_QC_FailedObjects",
            "",
            scene,
            "scriptronaut_qc_failed_objects",
            settings,
            "failed_object_index",
            rows=6,
        )

        # ---------------------------------------------------------
        # Selected object
        # ---------------------------------------------------------

        current_object_item = None

        if (
            0
            <= settings.failed_object_index
            < len(failed_objects)
        ):
            current_object_item = (
                failed_objects[
                    settings.failed_object_index
                ]
            )

        if current_object_item:
            info_row = object_box.row()

            info_row.label(
                text="Selected: {}".format(
                    current_object_item.name
                ),
                icon="RESTRICT_SELECT_OFF",
            )

            object_box.operator(
                "scriptronaut.qc_select_current_failed_object",
                text="Select Object",
                icon="RESTRICT_SELECT_OFF",
            )

        # ---------------------------------------------------------
        # Failed checks for selected object
        # ---------------------------------------------------------

        check_box = layout.box()

        check_box.label(
            text="Failed Checks",
            icon="ERROR",
        )

        if not object_checks:
            check_box.label(
                text="No failed checks for this object.",
                icon="CHECKMARK",
            )

            return

        check_box.template_list(
            "SCRIPTRONAUT_UL_QC_ObjectChecks",
            "",
            scene,
            "scriptronaut_qc_object_checks",
            settings,
            "object_check_index",
            rows=6,
        )

        # ---------------------------------------------------------
        # Current failed check
        # ---------------------------------------------------------

        current_object_check = None

        if (
            0
            <= settings.object_check_index
            < len(object_checks)
        ):
            current_object_check = (
                object_checks[
                    settings.object_check_index
                ]
            )

        if current_object_check is None:
            return

        # ---------------------------------------------------------
        # Fix selected check on selected object
        # ---------------------------------------------------------

        if current_object_check.has_fix:
            check_box.operator(
                "scriptronaut.qc_fix_object_check",
                text="Fix This Check On This Object",
                icon="TOOL_SETTINGS",
            )

        else:
            manual_row = check_box.row()

            manual_row.enabled = False

            manual_row.label(
                text="Fix Must Be Done Manually",
                icon="INFO",
            )

        # ---------------------------------------------------------
        # Optional check information
        # ---------------------------------------------------------

        details_box = layout.box()

        details_box.label(
            text="Selected Check:",
            icon="INFO",
        )

        details_box.label(
            text=current_object_check.name
        )

        if current_object_check.has_fix:

            details_box.label(
                text="Automatic fix available.",
                icon="TOOL_SETTINGS",
            )

        else:

            details_box.label(
                text="Manual fix required.",
                icon="INFO",
            )


class SCRIPTRONAUT_QC_FailedObjectItem(PropertyGroup):
    """
    Represents an object that failed one or more QC checks.
    """
    name: StringProperty(default="")
    failed_check_count: IntProperty(default=0)


class SCRIPTRONAUT_QC_ObjectCheckItem(PropertyGroup):
    """
    Represents a QC check failed by the currently selected object.
    """
    name: StringProperty(default="")
    script_path: StringProperty(default="")
    has_fix: BoolProperty(default=False)

    check_index: IntProperty(
        default=-1,
    )


class SCRIPTRONAUT_UL_QC_FailedObjects(UIList):
    """
    Displays objects that failed one or more QC checks.
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(
            align=True
        )

        split = row.split(
            factor=0.75,
            align=True,
        )

        split.label(
            text=item.name,
            icon="OBJECT_DATA",
        )

        split.label(
            text="{} Fail{}".format(
                item.failed_check_count,
                ""
                if item.failed_check_count == 1
                else "s",
            )
        )


class SCRIPTRONAUT_UL_QC_ObjectChecks(UIList):
    """
    Displays checks failed by the selected object.
    """

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row(
            align=True
        )

        row.label(
            text=item.name,
            icon=(
                "TOOL_SETTINGS"
                if item.has_fix
                else "INFO"
            ),
        )

        if item.has_fix:
            row.label(
                text="Auto Fix"
            )
        else:
            row.label(
                text="Manual"
            )

class SCRIPTRONAUT_OT_QC_FixObjectCheck(
    Operator
):
    """
    Fixes only the selected check for the selected object.
    """

    bl_idname = (
        "scriptronaut.qc_fix_object_check"
    )

    bl_label = (
        "Fix Check For Object"
    )

    def execute(
        self,
        context,
    ):
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        failed_objects = (
            scene.scriptronaut_qc_failed_objects
        )

        object_checks = (
            scene.scriptronaut_qc_object_checks
        )

        checks = (
            scene.scriptronaut_qc_checks
        )

        # -----------------------------------------------------
        # Validate object
        # -----------------------------------------------------

        if (
            settings.failed_object_index < 0
            or
            settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # -----------------------------------------------------
        # Validate check
        # -----------------------------------------------------

        if (
            settings.object_check_index < 0
            or
            settings.object_check_index
            >= len(object_checks)
        ):
            return {"CANCELLED"}

        object_check = object_checks[
            settings.object_check_index
        ]

        if not object_check.has_fix:

            self.report(
                {"WARNING"},
                "This check must be fixed manually.",
            )

            return {"CANCELLED"}

        if (
            object_check.check_index < 0
            or
            object_check.check_index
            >= len(checks)
        ):
            return {"CANCELLED"}

        check_item = checks[
            object_check.check_index
        ]

        # -----------------------------------------------------
        # Load QC module
        # -----------------------------------------------------

        try:

            module = load_module_from_path(
                "qc_object_fix_{}".format(
                    check_item.name
                ),
                check_item.script_path,
            )

            fix_function = getattr(
                module,
                "fix",
                None,
            )

            if not callable(
                fix_function
            ):

                check_item.has_fix = False

                self.report(
                    {"ERROR"},
                    "Missing fix() function.",
                )

                return {"CANCELLED"}

            # -------------------------------------------------
            # Filter result to one object
            # -------------------------------------------------

            result_data = (
                result_data_from_json(
                    check_item.result_data
                )
            )

            filtered_result = (
                get_filtered_result_for_object(
                    result_data,
                    object_name,
                )
            )

            try:

                fix_function(
                    filtered_result
                )

            except TypeError:

                # A fix() with no result_data argument cannot
                # safely be restricted to a single object.
                self.report(
                    {"ERROR"},
                    (
                        "This fix() does not accept result_data "
                        "and cannot safely fix one object only."
                    ),
                )

                return {"CANCELLED"}

            # -------------------------------------------------
            # Re-run this QC check
            # -------------------------------------------------

            rerun_qc_check_item(
                check_item
            )

            refresh_issues_display(
                context
            )

            rebuild_failed_objects(
                context
            )

        except Exception:

            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                "Could not fix object.",
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            'Fixed "{}" for "{}".'.format(
                check_item.name,
                object_name,
            ),
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject(
    Operator
):
    bl_idname = (
        "scriptronaut.qc_select_current_failed_object"
    )

    bl_label = (
        "Select Failed Object"
    )

    def execute(
        self,
        context,
    ):
        scene = context.scene

        settings = (
            scene.scriptronaut_qc_settings
        )

        failed_objects = (
            scene.scriptronaut_qc_failed_objects
        )

        if (
            settings.failed_object_index < 0
            or
            settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        obj = bpy.data.objects.get(
            object_name
        )

        if obj is None:
            return {"CANCELLED"}

        for selected_obj in (
            context.selected_objects
        ):
            selected_obj.select_set(
                False
            )

        try:
            obj.hide_set(False)
        except RuntimeError:
            pass

        obj.hide_viewport = False
        obj.hide_select = False

        obj.select_set(
            True
        )

        context.view_layer.objects.active = (
            obj
        )

        return {"FINISHED"}


# -------------------------------------------------------------------------
# Register
# -------------------------------------------------------------------------

classes = (
    SCRIPTRONAUT_QC_CheckItem,
    SCRIPTRONAUT_QC_EditorItem,
    SCRIPTRONAUT_QC_Settings,
    SCRIPTRONAUT_UL_QC_Checks,
    SCRIPTRONAUT_UL_QC_EditorScripts,
    SCRIPTRONAUT_OT_QC_OpenJsonEditor,
    SCRIPTRONAUT_OT_QC_EditorLoadCategory,
    SCRIPTRONAUT_OT_QC_EditorSelectAll,
    SCRIPTRONAUT_OT_QC_EditorSelectNone,
    SCRIPTRONAUT_OT_QC_EditorDeleteCategory,
    SCRIPTRONAUT_OT_QC_RefreshCategories,
    SCRIPTRONAUT_OT_QC_SelectAll,
    SCRIPTRONAUT_OT_QC_SelectNone,
    SCRIPTRONAUT_OT_QC_RunSelected,
    SCRIPTRONAUT_OT_QC_FixCurrent,
    SCRIPTRONAUT_OT_QC_SelectObject,
    SCRIPTRONAUT_PT_QC_Checks,
    SCRIPTRONAUT_QC_FailedObjectItem,
    SCRIPTRONAUT_QC_ObjectCheckItem,
    SCRIPTRONAUT_UL_QC_FailedObjects,
    SCRIPTRONAUT_UL_QC_ObjectChecks,
    SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject,
    SCRIPTRONAUT_OT_QC_FixObjectCheck,
)


def register():
    """
    Registers all addon classes and Scene properties.
    """
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.scriptronaut_qc_settings = PointerProperty(
        type=SCRIPTRONAUT_QC_Settings
    )

    bpy.types.Scene.scriptronaut_qc_checks = CollectionProperty(
        type=SCRIPTRONAUT_QC_CheckItem
    )

    bpy.types.Scene.scriptronaut_qc_editor_items = CollectionProperty(
        type=SCRIPTRONAUT_QC_EditorItem
    )

    if initialize_qc_checks_after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(
            initialize_qc_checks_after_load
        )

    bpy.app.timers.register(
        initialize_qc_checks_timer,
        first_interval=0.1,
    )

    bpy.types.Scene.scriptronaut_qc_failed_objects = (
        CollectionProperty(
            type=SCRIPTRONAUT_QC_FailedObjectItem
        )
    )

    bpy.types.Scene.scriptronaut_qc_object_checks = (
        CollectionProperty(
            type=SCRIPTRONAUT_QC_ObjectCheckItem
        )
    )


def unregister():
    """
    Unregisters addon classes and Scene properties.
    """
    if initialize_qc_checks_after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(
            initialize_qc_checks_after_load
        )

    if bpy.app.timers.is_registered(initialize_qc_checks_timer):
        bpy.app.timers.unregister(initialize_qc_checks_timer)

    del bpy.types.Scene.scriptronaut_qc_editor_items
    del bpy.types.Scene.scriptronaut_qc_settings
    del bpy.types.Scene.scriptronaut_qc_checks
    del bpy.types.Scene.scriptronaut_qc_failed_objects
    del bpy.types.Scene.scriptronaut_qc_object_checks

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
