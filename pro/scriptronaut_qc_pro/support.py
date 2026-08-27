"""Support for the QC Pro check-settings feature."""

from ..scriptronaut_qc.core.categories import load_qc_category
from ..scriptronaut_qc.core.preferences import get_check_preference_id
from ..scriptronaut_qc.core.discovery import (
    discover_check_scripts,
    get_categories,
)
from ..scriptronaut_qc.utils.json_io import load_check_list


def check_settings_enabled(
        context,
    ):
    if (
        context is None
        or context.scene is None
        or not hasattr(
            context.scene,
            "scriptronaut_qc_pro_settings",
        )
    ):
        return False

    return bool(
        context.scene
        .scriptronaut_qc_pro_settings
        .use_check_settings
    )


def update_use_check_settings(
        self,
        context,
    ):
    if (
        context is None
        or context.scene is None
    ):
        return

    scene = context.scene
    core_settings = scene.scriptronaut_qc_settings

    scene.scriptronaut_qc_checks.clear()
    core_settings.issues_display = ""

    categories = get_categories(
        core_settings.folder_path,
        use_json=self.use_check_settings,
    )

    if not categories:
        try:
            core_settings.category = "NONE"
        except TypeError:
            pass

        return

    if core_settings.category not in categories:
        core_settings.category = categories[0]

    else:
        load_qc_category(
            context
        )


def update_editor_category(
        self,
        context,
    ):
    """
    Reloads the Pro editor list whenever the Existing category changes.
    """
    if (
        context is None
        or context.scene is None
    ):
        return

    category = self.editor_category

    if (
        not category
        or category == "NONE"
    ):
        context.scene.scriptronaut_qc_pro_editor_items.clear()
        return

    success, message = populate_qc_editor(
        context,
        category=category,
    )

    if not success:
        print(
            "QC Pro category editor: {}".format(
                message
            )
        )


def qc_editor_category_items(
        self,
        context,
    ):
    if (
        context is None
        or context.scene is None
    ):
        return [
            (
                "NONE",
                "No Categories",
                "",
            )
        ]

    core_settings = (
        context.scene
        .scriptronaut_qc_settings
    )

    check_list = load_check_list(
        core_settings.folder_path
    )

    categories = sorted(
        category
        for category, script_names
        in check_list.items()
        if (
            isinstance(
                category,
                str,
            )
            and isinstance(
                script_names,
                list,
            )
        )
    )

    if not categories:
        return [
            (
                "NONE",
                "No Categories",
                "",
            )
        ]

    return [
        (
            category,
            category.replace(
                "_",
                " ",
            ).title(),
            "",
        )
        for category in categories
    ]


def populate_qc_editor(
        context,
        category=None,
    ):
    scene = context.scene

    core_settings = (
        scene.scriptronaut_qc_settings
    )

    pro_settings = (
        scene.scriptronaut_qc_pro_settings
    )

    editor_items = (
        scene.scriptronaut_qc_pro_editor_items
    )

    editor_items.clear()

    registry, duplicate_names = (
        discover_check_scripts(
            core_settings.folder_path,
            registered=False,
        )
    )

    if duplicate_names:
        lines = []

        for script_name, paths in (
            duplicate_names.items()
        ):
            lines.append(
                "{}: {}".format(
                    script_name,
                    ", ".join(
                        paths
                    ),
                )
            )

        return (
            False,
            "Duplicate script names found:\n{}".format(
                "\n".join(
                    lines
                )
            ),
        )

    check_list = load_check_list(
        core_settings.folder_path
    )

    if category is None:
        category = (
            pro_settings.editor_category
        )

    assigned_names = set(
        check_list.get(
            category,
            [],
        )
        if (
            category
            and category != "NONE"
        )
        else []
    )

    for script_name in sorted(
        registry
    ):
        script_data = registry[
            script_name
        ]

        item = editor_items.add()
        item.name = script_name
        item.script_path = script_data[
            "script_path"
        ]
        item.source_category = script_data[
            "source_category"
        ]
        item.pack_id = script_data.get(
            "pack_id",
            "legacy",
        )
        item.selected = (
            script_name in assigned_names
        )

    pro_settings.editor_index = 0

    return True, ""


# -------------------------------------------------------------------------
# Ignored Collections
# -------------------------------------------------------------------------


def ignored_rule_category_items(
        self,
        context,
    ):
    """
    Categories available to ignored-collection rules.
    """
    if (
        context is None
        or context.scene is None
    ):
        return [
            (
                "NONE",
                "No Categories",
                "",
            )
        ]

    core_settings = (
        context.scene
        .scriptronaut_qc_settings
    )

    categories = get_categories(
        core_settings.folder_path,
        use_json=check_settings_enabled(
            context
        ),
    )

    if not categories:
        return [
            (
                "NONE",
                "No Categories",
                "",
            )
        ]

    return [
        (
            category,
            category.replace(
                "_",
                " ",
            ).title(),
            "",
        )
        for category in categories
    ]


def ignored_rule_check_items(
        self,
        context,
    ):
    """
    All available checks, displayed as Category / Check.
    """
    if (
        context is None
        or context.scene is None
    ):
        return [
            (
                "NONE",
                "No Checks",
                "",
            )
        ]

    core_settings = (
        context.scene
        .scriptronaut_qc_settings
    )

    registry, duplicate_names = (
        discover_check_scripts(
            core_settings.folder_path,
        )
    )

    if duplicate_names:
        return [
            (
                "NONE",
                "Duplicate Check Names",
                "",
            )
        ]

    items = []

    for script_name, script_data in sorted(
        registry.items(),
        key=lambda item: (
            item[1].get(
                "source_category",
                "",
            ),
            item[0],
        ),
    ):
        category = script_data.get(
            "source_category",
            "",
        )

        if category == "common":
            continue

        check_id = get_check_preference_id(
            category,
            script_name,
        )

        label = "{} / {}".format(
            category.replace(
                "_",
                " ",
            ).title(),
            script_name.replace(
                "_",
                " ",
            ).title(),
        )

        items.append(
            (
                check_id,
                label,
                "",
            )
        )

    if not items:
        return [
            (
                "NONE",
                "No Checks",
                "",
            )
        ]

    return items


def _collection_tree_contains_object(
        collection,
        obj,
    ):
    """
    Returns True when obj belongs to collection or any child collection.
    """
    if (
        collection is None
        or obj is None
    ):
        return False

    object_collections = set(
        getattr(
            obj,
            "users_collection",
            (),
        )
    )

    stack = [
        collection
    ]

    visited = set()

    while stack:
        current = stack.pop()

        pointer = current.as_pointer()

        if pointer in visited:
            continue

        visited.add(
            pointer
        )

        if current in object_collections:
            return True

        stack.extend(
            current.children
        )

    return False


def ignored_collections_object_filter(
        *,
        obj,
        context,
        category,
        check_id,
    ):
    """
    Pro object filter registered with the shared QC framework.

    A matching rule returns False, excluding the object from the check.
    """
    if (
        context is None
        or context.scene is None
        or not hasattr(
            context.scene,
            "scriptronaut_qc_pro_ignored_collections",
        )
    ):
        return True

    rules = (
        context.scene
        .scriptronaut_qc_pro_ignored_collections
    )

    for rule in rules:
        collection = rule.collection

        if collection is None:
            continue

        applies = False

        if rule.scope == "CATEGORY":
            applies = (
                bool(
                    category
                )
                and rule.category == category
            )

        elif rule.scope == "CHECK":
            applies = (
                bool(
                    check_id
                )
                and rule.check_id == check_id
            )

        if not applies:
            continue

        if _collection_tree_contains_object(
            collection,
            obj,
        ):
            return False

    return True
