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
import inspect
import time

# Blender imports
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    EnumProperty,
    FloatProperty,
)
from bpy.types import (
    Operator, 
    Panel,
    PropertyGroup,
    UIList
)
from bpy.app.handlers import persistent

# Constants
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
QC_MODULES_DIR = os.path.join(ADDON_DIR, "qc_modules")
COMMON_CATEGORY = "common"
CHECK_SETTINGS_FILE = "check_settings.json"
CHECK_PREFERENCES_DIR = bpy.utils.user_resource(
    "CONFIG",
    path="scriptronaut_qc",
    create=True,
)
CHECK_PREFERENCES_FILE = os.path.join(
    CHECK_PREFERENCES_DIR,
    "check_preferences.json",
)
QC_IS_RUNNING = False
QC_IGNORE_CHANGES_UNTIL = 0.0

# Tier Level
TIER = "Pro"

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_matching_object_issues(
        result_data,
        object_name,
    ):
    """
    Returns top-level issue messages associated with one object.

    Existing checks usually include the object name in the issue string,
    so this provides useful information without requiring every QC module
    to change its return structure.
    """
    issues = get_issues_from_result(
        result_data
    )

    matching_issues = []

    object_name_lower = (
        str(object_name).lower()
    )

    for issue in issues:
        issue_text = str(issue)

        if (
            object_name_lower
            in issue_text.lower()
        ):
            matching_issues.append(
                issue_text
            )

    return matching_issues


def format_qc_detail_label(key):
    """
    Converts dictionary keys into readable UI labels.

    Example:
        loose_vertex_count -> Loose Vertex Count
    """
    return (
        str(key)
        .replace("_", " ")
        .strip()
        .title()
    )


def format_qc_detail_value(
        value,
        maximum_list_items=20,
    ):
    """
    Converts a QC result value into compact readable text.
    """
    if value is None:
        return "None"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, float):
        return "{:.6g}".format(value)

    if isinstance(value, (list, tuple, set)):
        values = list(value)

        if not values:
            return "None"

        visible_values = values[
            :maximum_list_items
        ]

        text = ", ".join(
            str(item)
            for item in visible_values
        )

        hidden_count = (
            len(values)
            - len(visible_values)
        )

        if hidden_count > 0:
            text += (
                " ... and {} more"
            ).format(
                hidden_count
            )

        return text

    return str(value)


def draw_wrapped_qc_text(
        layout,
        text,
        icon="NONE",
        width=75,
    ):
    """
    Draws multiline text inside Blender UI layouts.

    Blender labels do not automatically wrap, so this breaks long strings
    into reasonably sized rows.
    """
    import textwrap

    text = str(text or "")

    source_lines = (
        text.splitlines()
        if text
        else [""]
    )

    first_line = True

    for source_line in source_lines:
        wrapped_lines = textwrap.wrap(
            source_line,
            width=max(
                20,
                int(width),
            ),
            replace_whitespace=False,
            drop_whitespace=True,
        )

        if not wrapped_lines:
            wrapped_lines = [""]

        for wrapped_line in wrapped_lines:
            layout.label(
                text=wrapped_line,
                icon=(
                    icon
                    if first_line
                    else "NONE"
                ),
            )

            first_line = False


def draw_qc_result_dictionary(
        layout,
        data,
        level=0,
    ):
    """
    Recursively displays serialized QC result data.

    Nested dictionaries receive their own boxes. Lists of dictionaries are
    displayed as numbered entries.
    """
    if not isinstance(data, dict):
        draw_wrapped_qc_text(
            layout,
            format_qc_detail_value(data),
        )
        return

    for key, value in data.items():
        label = format_qc_detail_label(
            key
        )

        # -----------------------------------------------------
        # Nested dictionary
        # -----------------------------------------------------

        if isinstance(value, dict):
            sub_box = layout.box()

            sub_box.label(
                text=label,
                icon="DISCLOSURE_TRI_DOWN",
            )

            if value:
                draw_qc_result_dictionary(
                    sub_box,
                    value,
                    level=level + 1,
                )
            else:
                sub_box.label(
                    text="No data"
                )

            continue

        # -----------------------------------------------------
        # List containing dictionaries
        # -----------------------------------------------------

        if (
            isinstance(value, (list, tuple))
            and value
            and all(
                isinstance(item, dict)
                for item in value
            )
        ):
            list_box = layout.box()

            list_box.label(
                text="{} ({})".format(
                    label,
                    len(value),
                ),
                icon="LINENUMBERS_ON",
            )

            maximum_entries = 20

            for list_index, list_item in enumerate(
                value[:maximum_entries]
            ):
                item_box = list_box.box()

                item_box.label(
                    text="Item {}".format(
                        list_index + 1
                    )
                )

                draw_qc_result_dictionary(
                    item_box,
                    list_item,
                    level=level + 1,
                )

            if len(value) > maximum_entries:
                list_box.label(
                    text="{} additional entries hidden.".format(
                        len(value)
                        - maximum_entries
                    ),
                    icon="INFO",
                )

            continue

        # -----------------------------------------------------
        # Simple value
        # -----------------------------------------------------

        value_text = format_qc_detail_value(
            value
        )

        row = layout.row(
            align=True
        )

        split = row.split(
            factor=0.38,
            align=True,
        )

        split.label(
            text="{}:".format(label)
        )

        value_column = split.column(
            align=True
        )

        draw_wrapped_qc_text(
            value_column,
            value_text,
            width=55,
        )


def reset_check_settings_dialog(
        self,
        context,
    ):
    """
    Restores every displayed setting to its module default.

    This only changes the values currently displayed in the dialog.
    The defaults are written to disk when the user clicks OK.
    """
    if not self.reset_to_defaults:
        return

    for item in self.settings:

        if item.setting_type == "bool":
            item.bool_value = (
                item.default_bool
            )

        elif item.setting_type == "int":
            item.int_value = (
                item.default_int
            )

        elif item.setting_type == "float":
            item.float_value = (
                item.default_float
            )

        elif item.setting_type == "enum":
            item.enum_value = str(
                value
                if value is not None
                else ""
            )

            item.default_string = str(
                default
                if default is not None
                else ""
            )

        else:
            item.string_value = str(
                value
                if value is not None
                else ""
            )

            item.default_string = str(
                default
                if default is not None
                else ""
            )

    # Return the button to its unpressed state.
    self.reset_to_defaults = False

    # Force the dialog area to redraw.
    if context.area is not None:
        context.area.tag_redraw()


def load_all_check_preferences():
    """
    Loads the complete check-preferences JSON file.

    Returns:
        dict
    """
    if not os.path.isfile(
        CHECK_PREFERENCES_FILE
    ):
        return {}

    try:
        with open(
            CHECK_PREFERENCES_FILE,
            "r",
            encoding="utf-8",
        ) as json_file:
            data = json.load(
                json_file
            )

    except (
        OSError,
        ValueError,
        TypeError,
    ):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def save_all_check_preferences(preferences):
    """
    Saves the complete check-preferences dictionary.
    """
    folder = os.path.dirname(
        CHECK_PREFERENCES_FILE
    )

    if folder:
        os.makedirs(
            folder,
            exist_ok=True,
        )

    temporary_path = (
        CHECK_PREFERENCES_FILE
        + ".tmp"
    )

    with open(
        temporary_path,
        "w",
        encoding="utf-8",
    ) as json_file:
        json.dump(
            preferences,
            json_file,
            indent=4,
            sort_keys=True,
        )

    os.replace(
        temporary_path,
        CHECK_PREFERENCES_FILE,
    )


def get_check_preference_id(category_name, module_name):
    """
    """
    category_name = (
        str(category_name)
        .strip()
        .lower()
        .replace(" ", "_")
    )

    module_name = (
        str(module_name)
        .strip()
        .lower()
    )

    if module_name.endswith(".py"):
        module_name = module_name[:-3]

    return "{}.{}".format(
        category_name,
        module_name,
    )


def get_check_preferences(
        check_id,
        module,
    ):
    """
    Returns settings for one check with user values
    merged over module defaults.
    """
    schema = getattr(
        module,
        "SETTINGS",
        {},
    )

    if not isinstance(schema, dict):
        return {}

    resolved = {}

    for setting_name, definition in schema.items():
        if not isinstance(
            definition,
            dict,
        ):
            continue

        resolved[setting_name] = (
            definition.get("default")
        )

    all_preferences = (
        load_all_check_preferences()
    )

    user_preferences = (
        all_preferences.get(
            check_id,
            {},
        )
    )

    if isinstance(
        user_preferences,
        dict,
    ):
        for setting_name, value in user_preferences.items():
            if setting_name in resolved:
                resolved[setting_name] = value

    return resolved



def get_check_id_for_item(item):
    """
    Returns the stable preference identifier stored on a check item.
    """
    if getattr(item, "check_id", ""):
        return item.check_id

    return get_check_preference_id(
        getattr(item, "source_category", ""),
        getattr(item, "name", ""),
    )


def call_check_main(module, check_id):
    """
    Runs a check's main() and injects preferences when supported.
    """
    main_function = getattr(module, "main", None)

    if not callable(main_function):
        raise AttributeError("QC module has no callable main() function.")

    parameters = inspect.signature(main_function).parameters
    preferences = get_check_preferences(check_id, module)

    if "preferences" in parameters:
        return main_function(preferences=preferences)

    return main_function()


def call_check_fix(
        module,
        check_id,
        result_data=None,
        require_result_data=False,
    ):
    """
    Runs a check's fix() while supporting both current and legacy checks.

    Preferences are passed only when fix() explicitly declares a
    ``preferences`` argument. Result data is supplied by keyword when the
    function declares ``result_data`` and otherwise positionally when the
    function has a compatible positional argument.
    """
    fix_function = getattr(module, "fix", None)

    if not callable(fix_function):
        raise AttributeError("QC module has no callable fix() function.")

    signature = inspect.signature(fix_function)
    parameters = signature.parameters
    preferences = get_check_preferences(check_id, module)

    args = []
    kwargs = {}

    if "result_data" in parameters:
        kwargs["result_data"] = result_data
    else:
        positional_parameters = [
            parameter
            for parameter in parameters.values()
            if parameter.kind in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
            and parameter.name != "preferences"
        ]

        if positional_parameters:
            args.append(result_data)
        elif require_result_data:
            raise TypeError(
                "This fix() does not accept result_data and cannot safely "
                "operate on only one object."
            )

    if "preferences" in parameters:
        kwargs["preferences"] = preferences

    return fix_function(*args, **kwargs)


def module_has_settings(module):
    """
    Returns True when a check module declares a non-empty SETTINGS map.
    """
    schema = getattr(module, "SETTINGS", {})
    return isinstance(schema, dict) and bool(schema)


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


def set_qc_run_timestamp(context):
    """
    Records the current time as the most recent full QC run.

    Also ignores dependency-graph updates for a short period after
    the QC run so delayed Blender updates do not immediately mark
    the scene as modified.
    """
    global QC_IGNORE_CHANGES_UNTIL

    settings = (
        context.scene.scriptronaut_qc_settings
    )

    settings.last_run_time = str(
        time.time()
    )

    settings.scene_modified_since_qc = False

    # Blender may process dependency graph updates slightly after
    # the QC operator finishes.
    QC_IGNORE_CHANGES_UNTIL = (
        time.time() + 1.0
    )


def get_qc_elapsed_text(settings):
    """
    Returns human-readable time since the last full QC run.
    """
    if not settings.last_run_time:
        return "Not Run Yet"

    try:
        last_time = float(settings.last_run_time)
    except (TypeError, ValueError):
        return "Not Run Yet"

    elapsed_seconds = max(0.0, time.time() - last_time)
    elapsed_minutes = int(elapsed_seconds // 60)

    if elapsed_minutes < 1:
        return "Just now"
    if elapsed_minutes < 60:
        return "1 min ago" if elapsed_minutes == 1 else "{} min ago".format(elapsed_minutes)

    elapsed_hours = elapsed_minutes // 60
    remaining_minutes = elapsed_minutes % 60

    if elapsed_hours < 24:
        if remaining_minutes:
            return "{} hr {} min ago".format(elapsed_hours, remaining_minutes)
        return "{} hr ago".format(elapsed_hours)

    elapsed_days = elapsed_hours // 24
    return "1 day ago" if elapsed_days == 1 else "{} days ago".format(elapsed_days)


@persistent
def mark_scene_modified_after_qc(
        scene,
        depsgraph,
    ):
    """
    Marks QC results stale when relevant scene data changes
    after the last full QC run.

    Ignores:
        - Changes generated while QC is running.
        - Delayed dependency updates immediately after QC.
        - Changes to the Scene datablock caused by this addon's
          own status properties.
    """
    global QC_IS_RUNNING
    global QC_IGNORE_CHANGES_UNTIL

    # ---------------------------------------------------------
    # Ignore changes generated by QC itself
    # ---------------------------------------------------------

    if QC_IS_RUNNING:
        return

    # ---------------------------------------------------------
    # Ignore delayed depsgraph updates immediately after QC
    # ---------------------------------------------------------

    if time.time() < QC_IGNORE_CHANGES_UNTIL:
        return

    if scene is None:
        return

    if not hasattr(
        scene,
        "scriptronaut_qc_settings",
    ):
        return

    settings = (
        scene.scriptronaut_qc_settings
    )

    # No QC baseline exists yet.
    if not settings.last_run_time:
        return

    # Already marked dirty; nothing else to do.
    if settings.scene_modified_since_qc:
        return

    # ---------------------------------------------------------
    # Datablocks that can invalidate QC results
    # ---------------------------------------------------------

    relevant_types = (
        bpy.types.Object,
        bpy.types.Mesh,
        bpy.types.Material,
        bpy.types.Image,
        bpy.types.Armature,
        bpy.types.Action,
    )

    for update in depsgraph.updates:
        updated_id = update.id
        if isinstance(
            updated_id,
            relevant_types,
        ):
            settings.scene_modified_since_qc = True
            break


def redraw_qc_status_timer():
    """
    Redraws View3D areas so elapsed QC time updates while idle.
    """
    try:
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass

    return 30.0


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
    Loads all QC scripts for the currently selected category.

    Also reads optional module metadata:

        LABEL
        DESCRIPTION
        fix()

    Returns:
        tuple:
            (success, message)
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

        # -----------------------------------------------------
        # Basic script data
        # -----------------------------------------------------

        item.name = script_data["name"]

        item.display_name = script_data["name"]

        item.script_path = (
            script_data["script_path"]
        )

        item.source_category = (
            script_data["source_category"]
        )

        item.selected = True
        item.status = "NOT_RUN"
        item.has_fix = False
        item.description = ""
        item.issues = "Not run yet."
        item.result_data = "{}"
        item.check_id = get_check_preference_id(
            category,
            item.name,
        )
        item.has_settings = False

        # -----------------------------------------------------
        # Load optional module metadata
        # -----------------------------------------------------

        try:
            module = load_module_from_path(
                "qc_info_{}".format(
                    item.name
                ),
                item.script_path,
            )

            # Optional friendly UI name.
            item.display_name = getattr(
                module,
                "LABEL",
                item.name,
            )

            # Optional tooltip.
            item.description = getattr(
                module,
                "DESCRIPTION",
                "",
            )

            # Severity.
            severity = getattr(
                module,
                "SEVERITY",
                "warning",
            ).lower()

            if severity not in {
                "critical",
                "warning",
                "info",
            }:
                severity = "warning"

            item.severity = severity

            # Determine whether automatic fix exists.
            item.has_fix = callable(
                getattr(
                    module,
                    "fix",
                    None,
                )
            )

            item.has_settings = module_has_settings(
                module
            )

        except Exception:
            print(
                "Could not load QC metadata for '{}':".format(
                    item.name
                )
            )

            print(
                traceback.format_exc()
            )

            # Do NOT stop loading the remaining checks.
            item.display_name = item.name
            item.description = ""
            item.has_fix = False
            item.has_settings = False

    # ---------------------------------------------------------
    # Restore selected index
    # ---------------------------------------------------------

    if len(checks) > 0:
        settings.check_index = min(
            old_index,
            len(checks) - 1,
        )

    else:
        settings.check_index = 0

    refresh_issues_display(
        context
    )

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
        item.script_path = check_item.script_path
        item.has_fix = check_item.has_fix
        item.has_settings = check_item.has_settings
        item.check_id = check_item.check_id
        item.check_index = check_index
        item.display_name = (
            check_item.display_name
            if check_item.display_name
            else check_item.name
        )
        item.severity = check_item.severity
        item.description = check_item.description

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

        check_id = get_check_id_for_item(
            item
        )

        raw_result = call_check_main(
            module,
            check_id,
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

        item.has_settings = module_has_settings(
            module
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


def get_severity_icon(severity):
    """
    Returns the Blender icon for a QC severity.
    """

    icons = {
        "critical": "KEYTYPE_EXTREME_VEC",
        "warning": "KEYTYPE_KEYFRAME_VEC",
        "info": "KEYTYPE_BREAKDOWN_VEC",
    }

    return icons.get(
        severity,
        "KEYTYPE_KEYFRAME_VEC",
    )


# -------------------------------------------------------------------------
# Properties
# -------------------------------------------------------------------------

class SCRIPTRONAUT_QC_CheckItem(PropertyGroup):
    """
    """
    name: StringProperty(
        default=""
    )

    display_name: StringProperty(
        name="Display Name",
        default="",
    )

    description: StringProperty(
        name="Description",
        default="",
    )

    severity: EnumProperty(
        name="Severity",
        items=[
            (
                "critical",
                "Critical",
                "Critical QC issue",
            ),
            (
                "warning",
                "Warning",
                "QC warning",
            ),
            (
                "info",
                "Info",
                "Informational QC check",
            ),
        ],
        default="warning",
    )

    script_path: StringProperty(
        default=""
    )

    selected: BoolProperty(
        default=True
    )

    status: EnumProperty(
        name="Status",
        items=[
            (
                "NOT_RUN",
                "Not Run",
                "",
            ),
            (
                "PASS",
                "Pass",
                "",
            ),
            (
                "FAIL",
                "Fail",
                "",
            ),
            (
                "RUNNING",
                "Running",
                "",
            ),
        ],
        default="NOT_RUN",
    )

    source_category: StringProperty(
        name="Source Category",
        default="",
    )

    has_fix: BoolProperty(
        default=False
    )

    issues: StringProperty(
        default=""
    )

    result_data: StringProperty(
        default="{}"
    )

    check_id: StringProperty(
        default=""
    )

    has_settings: BoolProperty(
        default=False
    )


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

    last_run_time: StringProperty(
        name="Last QC Run Time",
        default="",
    )

    scene_modified_since_qc: BoolProperty(
        name="Scene Modified Since QC",
        default=False,
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
                "CUBE",
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
    Displays QC checks with:

        - Selection checkbox
        - Status icon
        - Check label
        - Description tooltip
        - Status
        - Inline Fix button when available
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

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

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
            status_text = "Not Run"

        # ---------------------------------------------------------
        # Enabled checkbox
        # ---------------------------------------------------------

        row.prop(item, "selected", text="")

        # ---------------------------------------------------------
        # Severity icon
        # ---------------------------------------------------------

        severity_names = {
            "critical": "Critical",
            "warning": "Warning",
            "info": "Info",
        }

        severity_info = row.operator(
            "scriptronaut.qc_check_info",
            text="",
            icon=get_severity_icon(
                item.severity
            ),
            emboss=False,
        )

        severity_info.tooltip_text = (
            "Severity: {}".format(
                severity_names.get(
                    item.severity,
                    "Warning",
                )
            )
        )

        # ---------------------------------------------------------
        # Main columns
        #
        # Name         ~72%
        # Status       ~15%
        # Fix button   remaining
        # ---------------------------------------------------------

        main_split = row.split(
            factor=0.72,
            align=True,
        )

        name_column = main_split.row(
            align=True
        )

        right_side = main_split.row(
            align=True
        )

        status_split = right_side.split(
            factor=0.50,
            align=True,
        )

        status_column = status_split.row(
            align=True
        )

        action_column = status_split.row(
            align=True
        )

        # ---------------------------------------------------------
        # Display name
        # ---------------------------------------------------------

        display_name = (
            item.display_name
            if item.display_name
            else item.name
        )

        if (
            item.source_category
            == COMMON_CATEGORY
        ):
            display_name = (
                "[Common] {}".format(
                    display_name
                )
            )

        # Keep this a label so selecting the UIList row
        # continues to work correctly.
        name_column.label(
            text=display_name,
            icon=icon_name,
        )

        # ---------------------------------------------------------
        # Description tooltip
        # ---------------------------------------------------------

        if item.description:
            info_operator = (
                name_column.operator(
                    "scriptronaut.qc_check_info",
                    text="",
                    icon="INFO",
                    emboss=False,
                )
            )

            info_operator.tooltip_text = (
                item.description
            )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        status_column.label(
            text=status_text,
        )

        # ---------------------------------------------------------
        # Inline Settings / Fix
        # ---------------------------------------------------------

        if item.has_settings:
            settings_operator = action_column.operator(
                "scriptronaut.qc_check_settings",
                text="",
                icon="GREASEPENCIL",
            )
            settings_operator.check_id = item.check_id
            settings_operator.script_path = item.script_path

        if (
            item.status == "FAIL"
            and item.has_fix
        ):
            fix_operator = action_column.operator(
                "scriptronaut.qc_fix_check_inline",
                text="Fix",
                icon="TOOL_SETTINGS",
            )
            fix_operator.check_index = index
        elif not item.has_settings:
            action_column.label(text="")


class SCRIPTRONAUT_UL_QC_EditorScripts(UIList):
    """
    Displays discovered QC scripts with selection checkboxes.
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
    """
    bl_idname = "scriptronaut.qc_run_selected"
    bl_label = "Run Selected Checks"

    def execute(self, context):
        global QC_IS_RUNNING

        scene = context.scene
        checks = scene.scriptronaut_qc_checks
        ran_any = False

        QC_IS_RUNNING = True

        try:
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
                        "issues": ["Script does not exist:\n{}".format(script_path)],
                        "script_path": script_path,
                    }
                    item.status = "FAIL"
                    item.issues = "\n".join(result_data["issues"])
                    item.result_data = result_data_to_json(result_data)
                    continue

                try:
                    module = load_module_from_path(
                        "qc_{}".format(item.name),
                        script_path,
                    )

                    main_function = getattr(module, "main", None)
                    if not callable(main_function):
                        result_data = {
                            "issues": ["Missing main() function."],
                            "script_path": script_path,
                        }
                        item.status = "FAIL"
                        item.issues = "\n".join(result_data["issues"])
                        item.result_data = result_data_to_json(result_data)
                        continue

                    raw_result = call_check_main(
                        module,
                        get_check_id_for_item(item),
                    )
                    result_data = normalize_check_result(raw_result)
                    result_data["check_name"] = item.name
                    result_data["script_path"] = script_path
                    issues = get_issues_from_result(result_data)

                    item.result_data = result_data_to_json(result_data)
                    item.has_fix = callable(getattr(module, "fix", None))
                    item.has_settings = module_has_settings(module)

                    if issues:
                        item.status = "FAIL"
                        item.issues = "\n".join(str(issue) for issue in issues)
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

        finally:
            QC_IS_RUNNING = False

        if not ran_any:
            self.report({"WARNING"}, "No checks selected.")
            return {"CANCELLED"}

        set_qc_run_timestamp(context)
        refresh_issues_display(context)
        rebuild_failed_objects(context)
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
            settings_box = layout.box()
            settings_box.label(
                text="Settings",
                icon="PREFERENCES",
            )

            settings_row = settings_box.row(
                align=True
            )

            # ---------------------------------------------------------
            # Left side - checkbox
            # ---------------------------------------------------------

            use_settings_row = settings_row.row(
                align=True
            )

            use_settings_row.prop(
                settings,
                "use_check_settings",
                text="Use Check Settings",
            )

            # ---------------------------------------------------------
            # Right side - edit button
            # ---------------------------------------------------------

            editor_row = settings_row.row(
                align=True
            )

            editor_row.enabled = (
                settings.use_check_settings
            )

            editor_row.operator(
                "scriptronaut.qc_open_json_editor",
                text="Edit Check Settings",
                icon="GREASEPENCIL",
            )

        # ---------------------------------------------------------
        # Mode
        # ---------------------------------------------------------

        mode_box = layout.box()

        mode_box.label(
            text="Mode",
            icon="OPTIONS",
        )

        mode_row =  mode_box.row()
        mode_row.prop(
            settings,
            "mode",
            expand=True,
        )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        status_box = layout.box()
        status_box.label(
            text="Status",
            icon="INFO",
        )

        elapsed_text = get_qc_elapsed_text(settings)
        status_row = status_box.row()

        if not settings.last_run_time:
            status_row.label(
                text="Last Run: Not Run Yet",
                icon="QUESTION",
            )

        elif settings.scene_modified_since_qc:
            status_row.alert = True
            status_row.label(
                text="Last Run: {}".format(elapsed_text),
                icon="TIME",
            )
            status_row.label(
                text="Scene Modified Since Last Run",
                icon="ERROR",
            )

        else:
            status_row.label(
                text="Last Run: {}".format(elapsed_text),
                icon="TIME",
            )
            status_row.label(
                text="Scene Has Not Changed",
                icon="CHECKMARK",
            )

        # ---------------------------------------------------------
        # Failure Severity Summary
        # ---------------------------------------------------------

        critical_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "critical"
            )
        )

        warning_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "warning"
            )
        )

        info_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.severity == "info"
            )
        )

        severity_row = layout.row(
            align=True
        )

        critical_col = severity_row.column(
            align=True
        )

        warning_col = severity_row.column(
            align=True
        )

        info_col = severity_row.column(
            align=True
        )

        critical_col.label(
            text="Critical: {}".format(
                critical_count
            ),
            icon="KEYTYPE_EXTREME_VEC",
        )

        warning_col.label(
            text="Warning: {}".format(
                warning_count
            ),
            icon="KEYTYPE_KEYFRAME_VEC",
        )

        info_col.label(
            text="Info: {}".format(
                info_count
            ),
            icon="KEYTYPE_BREAKDOWN_VEC",
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
        # Select All / Critical / None
        # ---------------------------------------------------------

        row = layout.row(align=True)

        row.operator(
            "scriptronaut.qc_select_all",
            icon="CHECKBOX_HLT",
            text="Select All",
        )

        row.separator()

        row.operator(
            "scriptronaut.qc_select_critical",
            icon="KEYTYPE_EXTREME_VEC",
            text="",
        )

        row.separator()

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

        selected_check_count = sum(
            1
            for item in checks
            if item.selected
        )

        run_row = layout.row()
        run_row.scale_y = 1.5

        run_row.enabled = (
            selected_check_count > 0
        )

        if selected_check_count == 0:
            run_button_text = (
                "No Checks Selected"
            )
        else:
            run_button_text = (
                "Run ({}) Selected Check{}".format(
                    selected_check_count,
                    ""
                    if selected_check_count == 1
                    else "s",
                )
            )

        run_row.operator(
            "scriptronaut.qc_run_selected",
            icon="PLAY",
            text=run_button_text,
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
        # Fix All
        # ---------------------------------------------------------

        fixable_count = sum(
            1
            for item in checks
            if (
                item.status == "FAIL"
                and item.has_fix
            )
        )

        fix_all_row = layout.row()
        fix_all_row.scale_y = 1.1
        fix_all_row.enabled = (
            fixable_count > 0
        )

        if fixable_count > 0:
            fix_all_text = (
                "Fix All ({})".format(
                    fixable_count
                )
            )
        else:
            fix_all_text = (
                "No Automatic Fixes Available"
            )

        fix_all_row.operator(
            "scriptronaut.qc_fix_all",
            icon="TOOL_SETTINGS",
            text=fix_all_text,
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

                    # -------------------------------------------------
                    # Object selection button
                    # -------------------------------------------------

                    object_button = row.operator(
                        "scriptronaut.qc_select_object",
                        text="Failed: {}".format(
                            object_name
                        ),
                        icon="ERROR",
                    )

                    object_button.object_name = (
                        object_name
                    )

                    # -------------------------------------------------
                    # Details popup button
                    # -------------------------------------------------

                    details_button = row.operator(
                        "scriptronaut.qc_object_details",
                        text="",
                        icon="INFO",
                    )

                    details_button.check_index = (
                        settings.check_index
                    )

                    details_button.object_name = (
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
        # Fix all failed checks for the selected object
        # ---------------------------------------------------------

        fixable_object_check_count = sum(
            1
            for item in object_checks
            if item.has_fix
        )

        fix_all_object_row = layout.row()
        fix_all_object_row.scale_y = 1.4

        fix_all_object_row.enabled = (
            fixable_object_check_count > 0
        )

        if fixable_object_check_count > 0:
            button_text = (
                "Fix All Checks on This Object ({})".format(
                    fixable_object_check_count
                )
            )

        else:
            button_text = (
                "No Automatic Fixes Available"
            )

        fix_all_object_row.operator(
            "scriptronaut.qc_fix_all_object_checks",
            text=button_text,
            icon="TOOL_SETTINGS",
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
    has_settings: BoolProperty(default=False)
    check_id: StringProperty(default="")

    check_index: IntProperty(
        default=-1,
    )

    display_name: StringProperty(default="")
    severity: StringProperty(default="warning")
    description: StringProperty(default="")


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

    Keeps the visual style consistent with Checks Mode:
        - Severity icon
        - Fail X icon
        - Friendly display name
        - Inline Fix button
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

        # This list only contains failed checks.
        row.alert = True

        scene = context.scene
        checks = scene.scriptronaut_qc_checks

        # ---------------------------------------------------------
        # Resolve original check item
        # ---------------------------------------------------------

        source_check = None

        if (
            item.check_index >= 0
            and item.check_index < len(checks)
        ):
            source_check = checks[
                item.check_index
            ]

        # ---------------------------------------------------------
        # Severity
        # ---------------------------------------------------------

        if source_check is not None:
            severity_icon = get_severity_icon(
                source_check.severity
            )

            display_name = (
                source_check.display_name
                if source_check.display_name
                else source_check.name
            )

        else:
            severity_icon = (
                "KEYTYPE_KEYFRAME_VEC"
            )

            display_name = item.name

        # ---------------------------------------------------------
        # Layout
        # ---------------------------------------------------------

        split = row.split(
            factor=0.88,
            align=True,
        )

        name_column = split.row(
            align=True
        )

        action_column = split.row(
            align=True
        )

        # ---------------------------------------------------------
        # Severity icon
        # ---------------------------------------------------------

        name_column.label(
            text="",
            icon=severity_icon,
        )

        # ---------------------------------------------------------
        # Fail icon
        # ---------------------------------------------------------

        name_column.label(
            text="",
            icon="CANCEL",
        )

        # ---------------------------------------------------------
        # Friendly display name
        # ---------------------------------------------------------

        name_column.label(
            text=display_name,
        )

        # ---------------------------------------------------------
        # Settings / Fix
        # ---------------------------------------------------------

        if item.has_settings and source_check is not None:
            settings_operator = action_column.operator(
                "scriptronaut.qc_check_settings",
                text="",
                icon="GREASEPENCIL",
            )
            settings_operator.check_id = source_check.check_id
            settings_operator.script_path = source_check.script_path

        if item.has_fix:
            operator = (
                action_column.operator(
                    "scriptronaut.qc_fix_object_inline",
                    text="Fix",
                    icon="TOOL_SETTINGS",
                )
            )

            operator.object_check_index = (
                index
            )

        else:
            manual_row = (
                action_column.row(
                    align=True
                )
            )

            manual_row.enabled = False

            manual_row.label(
                text="Manual"
            )


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


class SCRIPTRONAUT_OT_QC_FixAll(Operator):
    """
    Runs fix() for every failed QC check that provides an automatic fix.
    """

    bl_idname = "scriptronaut.qc_fix_all"
    bl_label = "Fix All"
    bl_description = "Fix all failed QC checks that have an automatic fix"

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        fixed_any = False
        skipped_manual = []
        failed_fixes = []

        for item in checks:
            # Only fix failed checks.
            if item.status != "FAIL":
                continue

            # Skip checks without an automatic fix.
            if not item.has_fix:
                skipped_manual.append(
                    item.name
                )
                continue

            if not os.path.isfile(
                item.script_path
            ):
                failed_fixes.append(
                    "{}: script not found".format(
                        item.name
                    )
                )
                continue

            try:
                module = load_module_from_path(
                    "qc_fix_all_{}".format(
                        item.name
                    ),
                    item.script_path,
                )

                fix_function = getattr(
                    module,
                    "fix",
                    None,
                )

                if not callable(
                    fix_function
                ):
                    item.has_fix = False

                    skipped_manual.append(
                        item.name
                    )

                    continue

                result_data = (
                    result_data_from_json(
                        item.result_data
                    )
                )

                call_check_fix(
                    module,
                    get_check_id_for_item(item),
                    result_data=result_data,
                )

                fixed_any = True

                # Re-run this check after fixing so its
                # status/result data are accurate.
                rerun_qc_check_item(
                    item
                )

            except Exception:
                failed_fixes.append(
                    "{}:\n{}".format(
                        item.name,
                        traceback.format_exc(),
                    )
                )

        if fixed_any and settings.last_run_time:
            settings.scene_modified_since_qc = True

        # Refresh both QC views after all fixes.
        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        if failed_fixes:
            for error in failed_fixes:
                print(
                    "QC Fix All error:\n{}".format(
                        error
                    )
                )

            self.report(
                {"WARNING"},
                "Some automatic fixes failed. See system console.",
            )

        elif fixed_any:
            if skipped_manual:

                self.report(
                    {"INFO"},
                    "Automatic fixes completed. {} check(s) require manual fixing.".format(
                        len(skipped_manual)
                    ),
                )

            else:
                self.report(
                    {"INFO"},
                    "All available fixes completed.",
                )

        else:
            self.report(
                {"INFO"},
                "No automatic fixes are currently available.",
            )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_CheckInfo(Operator):
    """
    UI-only operator used to provide a tooltip
    for a QC check in the list.
    """
    bl_idname = "scriptronaut.qc_check_info"
    bl_label = "QC Check"
    tooltip_text: StringProperty(
        default=""
    )

    @classmethod
    def description(
        cls,
        context,
        properties,
    ):
        return (
            properties.tooltip_text
            or
            "No description available."
        )

    def execute(
        self,
        context,
    ):
        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_FixCheckInline(Operator):
    """
    Fixes one specific QC check directly from its UIList row.
    """

    bl_idname = "scriptronaut.qc_fix_check_inline"
    bl_label = "Fix QC Check"
    bl_description = "Fix this QC check"

    check_index: IntProperty(
        name="Check Index",
        default=-1,
    )

    def execute(self, context):
        scene = context.scene
        settings = scene.scriptronaut_qc_settings
        checks = scene.scriptronaut_qc_checks

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            return {"CANCELLED"}

        item = checks[
            self.check_index
        ]

        if (
            item.status != "FAIL"
            or not item.has_fix
        ):
            self.report(
                {"WARNING"},
                "This check has no available automatic fix.",
            )
            return {"CANCELLED"}

        try:
            module = load_module_from_path(
                "qc_inline_fix_{}_{}".format(
                    item.name,
                    self.check_index,
                ),
                item.script_path,
            )

            fix_function = getattr(
                module,
                "fix",
                None,
            )

            if not callable(fix_function):
                item.has_fix = False
                self.report(
                    {"ERROR"},
                    "Missing fix() function.",
                )

                return {"CANCELLED"}

            result_data = result_data_from_json(
                item.result_data
            )

            call_check_fix(
                module,
                get_check_id_for_item(item),
                result_data=result_data,
            )

            # Re-run this specific QC check after the fix.
            rerun_qc_check_item(
                item
            )

            # Make this the currently selected check so the
            # Issues panel immediately displays its new result.
            settings.check_index = (
                self.check_index
            )

            refresh_issues_display(
                context
            )

            rebuild_failed_objects(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = True

        except Exception:
            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                'Could not fix "{}".'.format(
                    item.name
                ),
            )

            return {"CANCELLED"}

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_FixObjectInline(Operator):
    """
    Fixes one specific failed check for the currently selected
    failed object.
    """

    bl_idname = "scriptronaut.qc_fix_object_inline"
    bl_label = "Fix Check On Object"
    bl_description = "Fix this check only on this object"

    object_check_index: IntProperty(
        name="Object Check Index",
        default=-1,
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

        # ---------------------------------------------------------
        # Validate selected object
        # ---------------------------------------------------------

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # ---------------------------------------------------------
        # Validate inline check
        # ---------------------------------------------------------

        if (
            self.object_check_index < 0
            or self.object_check_index
            >= len(object_checks)
        ):
            return {"CANCELLED"}

        object_check = object_checks[
            self.object_check_index
        ]

        if not object_check.has_fix:
            self.report(
                {"WARNING"},
                "This check must be fixed manually.",
            )

            return {"CANCELLED"}

        check_index = (
            object_check.check_index
        )

        if (
            check_index < 0
            or check_index >= len(checks)
        ):
            return {"CANCELLED"}

        check_item = checks[
            check_index
        ]

        try:
            module = load_module_from_path(
                "qc_object_inline_fix_{}_{}".format(
                    check_item.name,
                    self.object_check_index,
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

            # -----------------------------------------------------
            # Filter original result to ONLY this object
            # -----------------------------------------------------

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

            # Object-specific fixes must accept result data so only
            # the selected object can be changed safely.
            try:
                call_check_fix(
                    module,
                    get_check_id_for_item(check_item),
                    result_data=filtered_result,
                    require_result_data=True,
                )
            except TypeError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

            # -----------------------------------------------------
            # Re-run affected check
            # -----------------------------------------------------

            rerun_qc_check_item(
                check_item
            )

            # Rebuild Object mode after result changed.
            rebuild_failed_objects(
                context
            )

            refresh_issues_display(
                context
            )

            if settings.last_run_time:
                settings.scene_modified_since_qc = True

        except Exception:
            print(
                traceback.format_exc()
            )

            self.report(
                {"ERROR"},
                "Could not fix {} on {}.".format(
                    check_item.name,
                    object_name,
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            'Fixed "{}" on "{}".'.format(
                check_item.name,
                object_name,
            ),
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_FixAllObjectChecks(Operator):
    """
    Fixes every automatically fixable failed check for the
    currently selected failed object.
    """

    bl_idname = (
        "scriptronaut.qc_fix_all_object_checks"
    )

    bl_label = (
        "Fix All Checks on This Object"
    )

    bl_description = (
        "Run all available automatic fixes for the "
        "currently selected failed object"
    )

    @classmethod
    def poll(cls, context):
        scene = getattr(
            context,
            "scene",
            None,
        )

        if scene is None:
            return False

        settings = getattr(
            scene,
            "scriptronaut_qc_settings",
            None,
        )

        failed_objects = getattr(
            scene,
            "scriptronaut_qc_failed_objects",
            None,
        )

        object_checks = getattr(
            scene,
            "scriptronaut_qc_object_checks",
            None,
        )

        if (
            settings is None
            or failed_objects is None
            or object_checks is None
        ):
            return False

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            return False

        return any(
            item.has_fix
            for item in object_checks
        )

    def execute(self, context):
        global QC_IS_RUNNING

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
        # Validate selected failed object
        # -----------------------------------------------------

        if (
            settings.failed_object_index < 0
            or settings.failed_object_index
            >= len(failed_objects)
        ):
            self.report(
                {"WARNING"},
                "No failed object selected.",
            )

            return {"CANCELLED"}

        object_name = failed_objects[
            settings.failed_object_index
        ].name

        # -----------------------------------------------------
        # Snapshot check indices
        #
        # Do not iterate the collection while rebuilding it.
        # -----------------------------------------------------

        check_indices = [
            item.check_index
            for item in object_checks
            if (
                item.has_fix
                and item.check_index >= 0
                and item.check_index < len(checks)
            )
        ]

        if not check_indices:
            self.report(
                {"INFO"},
                "No automatic fixes are available for this object.",
            )

            return {"CANCELLED"}

        fixed_checks = []
        failed_fixes = []
        skipped_checks = []

        QC_IS_RUNNING = True

        try:
            for check_index in check_indices:

                check_item = checks[
                    check_index
                ]

                if check_item.status != "FAIL":
                    continue

                if not check_item.has_fix:
                    skipped_checks.append(
                        check_item.display_name
                        or check_item.name
                    )
                    continue

                if not os.path.isfile(
                    check_item.script_path
                ):
                    failed_fixes.append(
                        "{}: script does not exist".format(
                            check_item.display_name
                            or check_item.name
                        )
                    )
                    continue

                try:
                    module = load_module_from_path(
                        "qc_fix_all_object_{}_{}".format(
                            check_item.name,
                            check_index,
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

                        skipped_checks.append(
                            check_item.display_name
                            or check_item.name
                        )

                        continue

                    # -----------------------------------------
                    # Filter this check's result so only the
                    # selected object is passed to fix().
                    # -----------------------------------------

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

                    filtered_objects = (
                        filtered_result.get(
                            "failed_objects",
                            {},
                        )
                    )

                    if not filtered_objects:
                        continue

                    # Object-specific fixing must accept result data.
                    try:
                        call_check_fix(
                            module,
                            get_check_id_for_item(check_item),
                            result_data=filtered_result,
                            require_result_data=True,
                        )
                    except TypeError as error:
                        failed_fixes.append(
                            "{}: {}".format(
                                check_item.display_name or check_item.name,
                                error,
                            )
                        )
                        continue

                    fixed_checks.append(
                        check_item.display_name
                        or check_item.name
                    )

                except Exception:
                    failed_fixes.append(
                        "{}:\n{}".format(
                            check_item.display_name
                            or check_item.name,
                            traceback.format_exc(),
                        )
                    )

            # -------------------------------------------------
            # Re-run affected checks after all fixes
            # -------------------------------------------------

            for check_index in check_indices:
                if (
                    check_index >= 0
                    and check_index < len(checks)
                ):
                    rerun_qc_check_item(
                        checks[check_index]
                    )

        finally:
            QC_IS_RUNNING = False

        # -----------------------------------------------------
        # Refresh both UI modes once
        # -----------------------------------------------------

        refresh_issues_display(
            context
        )

        rebuild_failed_objects(
            context
        )

        if fixed_checks and settings.last_run_time:
            settings.scene_modified_since_qc = True

        # -----------------------------------------------------
        # Report
        # -----------------------------------------------------

        if failed_fixes:
            for error in failed_fixes:
                print(
                    "QC object fix error:\n{}".format(
                        error
                    )
                )

            self.report(
                {"WARNING"},
                (
                    "Fixed {} check(s) on '{}'. "
                    "{} fix(es) failed."
                ).format(
                    len(fixed_checks),
                    object_name,
                    len(failed_fixes),
                ),
            )

        elif fixed_checks:
            self.report(
                {"INFO"},
                "Fixed {} check(s) on '{}'.".format(
                    len(fixed_checks),
                    object_name,
                ),
            )

        else:
            self.report(
                {"INFO"},
                "No checks were fixed on '{}'.".format(
                    object_name
                ),
            )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_SelectCritical(Operator):
    """
    Select only Critical QC checks.
    """
    bl_idname = "scriptronaut.qc_select_critical"
    bl_label = "Select Critical Checks"
    bl_description = "Select only Critical QC checks"

    def execute(self, context):

        checks = context.scene.scriptronaut_qc_checks

        for item in checks:
            item.selected = (
                item.severity == "critical"
            )

        return {"FINISHED"}


class SCRIPTRONAUT_PG_CheckSetting(
        PropertyGroup
    ):

    setting_name: StringProperty()
    label: StringProperty()
    description: StringProperty()
    setting_type: EnumProperty(
        items=(
            ("bool", "Boolean", ""),
            ("int", "Integer", ""),
            ("float", "Float", ""),
            ("string", "Text", ""),
            ("enum", "List", ""),
        ),
        default="string",
    )
    bool_value: BoolProperty()
    int_value: IntProperty()
    float_value: FloatProperty()
    string_value: StringProperty()
    enum_value: StringProperty()
    default_bool: BoolProperty()
    default_int: IntProperty()
    default_float: FloatProperty()
    default_string: StringProperty()

    minimum: FloatProperty(
        default=-1000000000.0,
    )

    maximum: FloatProperty(
        default=1000000000.0,
    )


class SCRIPTRONAUT_OT_QC_CheckSettings(Operator):
    """
    """
    bl_idname = "scriptronaut.qc_check_settings"
    bl_label = "Check Settings"
    bl_description = "Edit configurable values for this QC check"

    check_id: StringProperty()
    category_name: StringProperty()
    module_name: StringProperty()
    script_path: StringProperty(subtype="FILE_PATH")
    settings: CollectionProperty(type=SCRIPTRONAUT_PG_CheckSetting)
    reset_to_defaults: BoolProperty(
        name="Reset Values to Defaults",
        description=(
            "Restore the displayed settings to the defaults "
            "defined by this QC check"
        ),
        default=False,
        update=reset_check_settings_dialog,
    )

    def invoke(
            self,
            context,
            event,
        ):
        self.settings.clear()

        if not self.script_path or not os.path.isfile(self.script_path):
            self.report(
                {"ERROR"},
                "QC check script could not be found.",
            )
            return {"CANCELLED"}

        try:
            module = load_module_from_path(
                "qc_settings_{}".format(
                    abs(hash(self.script_path))
                ),
                self.script_path,
            )
        except Exception:
            print(traceback.format_exc())
            module = None

        if module is None:
            self.report(
                {"ERROR"},
                "Could not load the QC module.",
            )
            return {"CANCELLED"}

        schema = getattr(
            module,
            "SETTINGS",
            {},
        )

        if not isinstance(
            schema,
            dict,
        ) or not schema:
            self.report(
                {"INFO"},
                "This check has no configurable settings.",
            )
            return {"CANCELLED"}

        preferences = get_check_preferences(
            self.check_id,
            module,
        )

        for setting_name, definition in schema.items():
            if not isinstance(
                definition,
                dict,
            ):
                continue

            item = self.settings.add()

            item.setting_name = setting_name

            item.label = definition.get(
                "label",
                setting_name.replace(
                    "_",
                    " ",
                ).title(),
            )

            item.description = definition.get(
                "description",
                "",
            )

            item.setting_type = definition.get(
                "type",
                "string",
            )

            value = preferences.get(
                setting_name,
                definition.get("default"),
            )

            default = definition.get(
                "default"
            )

            if item.setting_type == "bool":
                item.bool_value = bool(
                    value
                )

                item.default_bool = bool(
                    default
                )

            elif item.setting_type == "int":
                item.int_value = int(
                    value
                )

                item.default_int = int(
                    default
                )

                item.minimum = float(
                    definition.get(
                        "min",
                        -1000000000,
                    )
                )

                item.maximum = float(
                    definition.get(
                        "max",
                        1000000000,
                    )
                )

            elif item.setting_type == "float":
                item.float_value = float(
                    value
                )

                item.default_float = float(
                    default
                )

                item.minimum = float(
                    definition.get(
                        "min",
                        -1000000000.0,
                    )
                )

                item.maximum = float(
                    definition.get(
                        "max",
                        1000000000.0,
                    )
                )

            else:
                item.string_value = str(
                    value
                    if value is not None
                    else ""
                )

                item.default_string = str(
                    default
                    if default is not None
                    else ""
                )

        return context.window_manager.invoke_props_dialog(
            self,
            width=500,
        )

    def draw(
            self,
            context,
        ):
        layout = self.layout

        layout.label(
            text="Check Settings",
            icon="GREASEPENCIL",
        )

        layout.label(
            text=self.check_id,
        )

        layout.separator()

        for item in self.settings:
            box = layout.box()
            row = box.row()

            if item.setting_type == "bool":
                row.prop(
                    item,
                    "bool_value",
                    text=item.label,
                )

            elif item.setting_type == "int":
                row.prop(
                    item,
                    "int_value",
                    text=item.label,
                )

            elif item.setting_type == "float":
                row.prop(
                    item,
                    "float_value",
                    text=item.label,
                )

            elif item.setting_type == "enum":
                row.prop(
                    item,
                    "enum_value",
                    text=item.label,
                )

            else:
                row.prop(
                    item,
                    "string_value",
                    text=item.label,
                )

            if item.description:
                description_column = (
                    box.column()
                )

                description_column.scale_y = 0.8

                description_column.label(
                    text=item.description,
                    icon="INFO",
                )

        layout.separator()

        reset_row = layout.row(
            align=True
        )

        reset_row.prop(
            self,
            "reset_to_defaults",
            text="Reset Values to Defaults",
            icon="LOOP_BACK",
            toggle=True,
        )

    def execute(
            self,
            context,
        ):
        all_preferences = (
            load_all_check_preferences()
        )

        check_preferences = {}

        for item in self.settings:

            if item.setting_type == "bool":
                value = item.bool_value

            elif item.setting_type == "int":
                value = int(
                    max(
                        item.minimum,
                        min(
                            item.maximum,
                            item.int_value,
                        ),
                    )
                )

            elif item.setting_type == "float":
                value = float(
                    max(
                        item.minimum,
                        min(
                            item.maximum,
                            item.float_value,
                        ),
                    )
                )

            elif item.setting_type == "enum":
                value = item.enum_value

            else:
                value = item.string_value

            check_preferences[
                item.setting_name
            ] = value

        all_preferences[
            self.check_id
        ] = check_preferences

        try:
            save_all_check_preferences(
                all_preferences
            )

        except OSError as error:
            self.report(
                {"ERROR"},
                "Could not save settings: {}".format(
                    error
                ),
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            "Check settings saved.",
        )

        return {"FINISHED"}


class SCRIPTRONAUT_OT_QC_ObjectDetails(
    Operator
):
    """
    Displays detailed result information for one failed object.
    """

    bl_idname = (
        "scriptronaut.qc_object_details"
    )

    bl_label = (
        "QC Failure Details"
    )

    bl_description = (
        "Display detailed information about this QC failure"
    )

    check_index: IntProperty(
        name="Check Index",
        default=-1,
    )

    object_name: StringProperty(
        name="Object Name",
        default="",
    )

    def invoke(
        self,
        context,
        event,
    ):
        checks = (
            context.scene
            .scriptronaut_qc_checks
        )

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            self.report(
                {"ERROR"},
                "The QC check is no longer available.",
            )

            return {"CANCELLED"}

        check_item = checks[
            self.check_index
        ]

        result_data = (
            result_data_from_json(
                check_item.result_data
            )
        )

        failed_objects = (
            result_data.get(
                "failed_objects",
                {},
            )
        )

        if (
            not isinstance(
                failed_objects,
                dict,
            )
            or self.object_name
            not in failed_objects
        ):
            self.report(
                {"WARNING"},
                (
                    'No stored failure information was found for "{}".'
                ).format(
                    self.object_name
                ),
            )

            return {"CANCELLED"}

        return (
            context.window_manager
            .invoke_props_dialog(
                self,
                width=650,
            )
        )

    def draw(
        self,
        context,
    ):
        layout = self.layout

        checks = (
            context.scene
            .scriptronaut_qc_checks
        )

        if (
            self.check_index < 0
            or self.check_index >= len(checks)
        ):
            layout.label(
                text="The QC check is no longer available.",
                icon="ERROR",
            )
            return

        check_item = checks[
            self.check_index
        ]

        result_data = (
            result_data_from_json(
                check_item.result_data
            )
        )

        failed_objects = (
            result_data.get(
                "failed_objects",
                {},
            )
        )

        object_data = {}

        if isinstance(
            failed_objects,
            dict,
        ):
            object_data = (
                failed_objects.get(
                    self.object_name,
                    {},
                )
            )

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        header_box = layout.box()

        header_box.label(
            text=(
                check_item.display_name
                or check_item.name
            ),
            icon=get_severity_icon(
                check_item.severity
            ),
        )

        header_box.label(
            text=self.object_name,
            icon="OBJECT_DATA",
        )

        # -----------------------------------------------------
        # Issue messages
        # -----------------------------------------------------

        issue_box = layout.box()

        issue_box.label(
            text="Issue Messages",
            icon="ERROR",
        )

        matching_issues = (
            get_matching_object_issues(
                result_data,
                self.object_name,
            )
        )

        # Some checks return only one general issue that does not
        # contain the object name. Show it when only one issue exists.
        if not matching_issues:
            all_issues = (
                get_issues_from_result(
                    result_data
                )
            )

            if len(all_issues) == 1:
                matching_issues = all_issues

        if matching_issues:
            for issue_index, issue in enumerate(
                matching_issues
            ):
                if issue_index:
                    issue_box.separator()

                draw_wrapped_qc_text(
                    issue_box,
                    issue,
                    icon="ERROR",
                    width=85,
                )

        else:
            issue_box.label(
                text=(
                    "No object-specific issue message "
                    "was returned by this check."
                ),
                icon="INFO",
            )

        # -----------------------------------------------------
        # Structured result information
        # -----------------------------------------------------

        result_box = layout.box()

        result_box.label(
            text="Failure Data",
            icon="PROPERTIES",
        )

        if isinstance(object_data, dict):
            draw_qc_result_dictionary(
                result_box,
                object_data,
            )

        else:
            draw_wrapped_qc_text(
                result_box,
                object_data,
            )

    def execute(
        self,
        context,
    ):
        return {"FINISHED"}


# -------------------------------------------------------------------------
# Register
# -------------------------------------------------------------------------

classes = (
    SCRIPTRONAUT_QC_CheckItem,
    SCRIPTRONAUT_QC_EditorItem,
    SCRIPTRONAUT_PG_CheckSetting,
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
    SCRIPTRONAUT_OT_QC_SelectCritical,
    SCRIPTRONAUT_OT_QC_SelectNone,
    SCRIPTRONAUT_OT_QC_RunSelected,
    SCRIPTRONAUT_OT_QC_FixCheckInline,
    SCRIPTRONAUT_OT_QC_SelectObject,
    SCRIPTRONAUT_OT_QC_CheckInfo,
    SCRIPTRONAUT_OT_QC_CheckSettings,
    SCRIPTRONAUT_OT_QC_ObjectDetails,
    SCRIPTRONAUT_PT_QC_Checks,
    SCRIPTRONAUT_QC_FailedObjectItem,
    SCRIPTRONAUT_QC_ObjectCheckItem,
    SCRIPTRONAUT_UL_QC_FailedObjects,
    SCRIPTRONAUT_UL_QC_ObjectChecks,
    SCRIPTRONAUT_OT_QC_SelectCurrentFailedObject,
    SCRIPTRONAUT_OT_QC_FixObjectInline,
    SCRIPTRONAUT_OT_QC_FixAllObjectChecks,
    SCRIPTRONAUT_OT_QC_FixAll,
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

    if (
        mark_scene_modified_after_qc
        not in bpy.app.handlers.depsgraph_update_post
    ):
        bpy.app.handlers.depsgraph_update_post.append(
            mark_scene_modified_after_qc
        )

    if not bpy.app.timers.is_registered(initialize_qc_checks_timer):
        bpy.app.timers.register(
            initialize_qc_checks_timer,
            first_interval=0.1,
        )

    if not bpy.app.timers.is_registered(redraw_qc_status_timer):
        bpy.app.timers.register(
            redraw_qc_status_timer,
            first_interval=30.0,
            persistent=True,
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

    if (
        mark_scene_modified_after_qc
        in bpy.app.handlers.depsgraph_update_post
    ):
        bpy.app.handlers.depsgraph_update_post.remove(
            mark_scene_modified_after_qc
        )

    if bpy.app.timers.is_registered(initialize_qc_checks_timer):
        bpy.app.timers.unregister(initialize_qc_checks_timer)

    if bpy.app.timers.is_registered(redraw_qc_status_timer):
        bpy.app.timers.unregister(redraw_qc_status_timer)

    del bpy.types.Scene.scriptronaut_qc_editor_items
    del bpy.types.Scene.scriptronaut_qc_settings
    del bpy.types.Scene.scriptronaut_qc_checks
    del bpy.types.Scene.scriptronaut_qc_failed_objects
    del bpy.types.Scene.scriptronaut_qc_object_checks

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
