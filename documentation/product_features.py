"""Documentation metadata for non-check QC product features."""

from __future__ import annotations

from typing import Any


PRODUCT_FEATURES: dict[str, list[dict[str, Any]]] = {
    "core": [],

    "pro": [
        {
            "id": "check_settings",
            "label": "Check Settings",
            "description": (
                "Customize which QC checks belong to each category using "
                "the Check Settings Editor."
            ),
            "summary": (
                "Check Settings lets users create and update category "
                "definitions. The editor saves the selected check assignments."
            ),
            "highlights": [
                "Enable or disable the Check Settings workflow from the QC panel.",
                "Select an existing category or create a new category.",
                "Choose which available checks belong to that category.",
                "Update one category and continue editing other categories without closing the dialog.",
                "Changing the Existing category automatically loads its saved check selection.",
            ],
            "workflow": [
                "Enable Use Check Settings in the Settings section.",
                "Open Edit Check Settings.",
                "Choose an Existing category or enter a New category name.",
                "Select the checks that should belong to that category.",
                "Choose Update Category Checks to save and continue editing, or OK to save the current category and close.",
            ],
            "storage": (
                "The category configuration is stored in checks/check_settings.json"
            ),
            "notes": [
                "Check Settings changes category membership, not the "
                "check implementation."
            ],
        },

        {
            "id": "ignored_collections",
            "label": "Ignored Collections",
            "description": (
                "Exclude objects in selected Blender collections from an "
                "entire QC category or from one specific QC check."
            ),
            "summary": (
                "Ignored Collections provides scene-specific QC exclusion "
                "rules. It is useful for reference, proxy, helper, temporary, "
                "or intentionally non-production objects that should remain in "
                "the scene but should not participate in selected QC checks."
            ),
            "highlights": [
                "Rules are stored with the Blender Scene rather than in check_settings.json.",
                "A rule can apply to a complete QC category.",
                "A rule can apply to one specific QC check.",
                "Objects in child collections of an ignored collection are included automatically.",
                "The same exclusion is respected by both check execution and automatic Fix operations.",
            ],
            "workflow": [
                "Open Edit Ignored Collections from the Settings area.",
                "Add a rule.",
                "Choose the Blender Collection to ignore.",
                "Choose whether the rule applies to a Category or a specific Check.",
                "Choose the target category or check.",
                "Run QC normally; matching objects are filtered before the check receives them.",
            ],
            "storage": (
                "Ignored Collection rules are stored as Scene properties in "
                "the .blend file. Collection references use Blender Collection "
                "pointers, so renaming a referenced collection does not break "
                "the rule."
            ),
            "notes": [
                "Ignoring a parent collection also ignores objects contained in its child collections for the matching rule.",
                "Rules are scene-specific, so different scenes in the same .blend can use different QC exclusions.",
            ],
        },
    ],
}


def get_product_features(
        product_id: str,
) -> list[dict[str, Any]]:
    return [
        dict(feature)
        for feature in PRODUCT_FEATURES.get(
            str(product_id).strip().lower(),
            [],
        )
    ]
