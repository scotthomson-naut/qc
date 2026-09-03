"""Documentation metadata for notes shown on QC product index pages."""

from __future__ import annotations

from typing import Any


# Notes in "all" appear on every Core, Pro, and Pack index page.
# Add a product ID key to show notes only for that product. Pack-specific
# notes use the discovered pack ID, for example "rigging".
PRODUCT_NOTES: dict[str, list[dict[str, Any]]] = {
    "all": [
        {
            "title": "Linked Library Objects",
            "description": (
                "Directly linked library objects are ignored by all checks."
            ),
        },
    ],

    "core": [],
    "pro": [],
}


def get_product_notes(
        product_id: str,
    ) -> list[dict[str, Any]]:
    """Return independent copies of global and product-specific notes."""
    normalized_id = str(
        product_id
    ).strip().lower()

    return [
        dict(note)
        for note in (
            PRODUCT_NOTES.get("all", [])
            + PRODUCT_NOTES.get(normalized_id, [])
        )
    ]
