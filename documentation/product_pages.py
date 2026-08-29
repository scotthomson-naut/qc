"""Editable product-page content for Scriptronaut QC Checker products.

This file intentionally contains marketing/product copy rather than technical
check metadata. Technical documentation continues to be generated from the
actual check modules.
"""
from __future__ import annotations

from typing import Any


PRODUCT_PAGE_CONTENT: dict[str, dict[str, Any]] = {
    "core": {
        "name": "QC Checker Core",
        "eyebrow": "QC Checker",
        "primary_outcome": (
            "Catch common Blender scene and asset problems before they reach "
            "render, export, review, or publishing."
        ),
        "hero_label": "60 second QC Checker Core overview",
        "hero_youtube_id": "FlJaF2XkR6k",
        "hero_video_title": "NASA 4K Views from Space",
        "problem": (
            "Production problems are often discovered late, after they have "
            "already interrupted another artist, a render, or an export."
        ),
        "before_after": (
            "Before QC Checker, artists manually inspect many scene details. "
            "With QC Checker Core, the same production rules can be checked "
            "consistently from one Blender panel."
        ),
        "benefits": [
            {
                "feature": "Production QC checks",
                "benefit": "Catch modeling, material, naming, rendering, scene, animation, and UV issues earlier.",
            },
            {
                "feature": "Automatic fixes where safe",
                "benefit": "Correct repeatable issues without turning every QC failure into a manual cleanup task.",
            },
            {
                "feature": "Object and check views",
                "benefit": "Review failures from the perspective that best fits the current cleanup task.",
            },
        ],
        "who_for": (
            "Blender artists, technical artists, small teams, and productions "
            "that want repeatable scene-quality checks without building an "
            "internal QC system from scratch."
        ),
        "requirements": "Blender. Exact supported versions should be kept in the product release notes.",
        "buy_url": "",
    },

    "pro": {
        "name": "QC Checker Pro",
        "eyebrow": "QC Checker",
        "primary_outcome": (
            "Use the complete QC Checker workflow plus Pro configuration and "
            "production-control features."
        ),
        "hero_label": "60 second QC Checker Pro overview",
        "hero_youtube_id": "FlJaF2XkR6k",
        "hero_video_title": "NASA 4K Views from Space",
        "problem": (
            "Different teams and projects rarely use exactly the same QC "
            "rules. A fixed check list can become restrictive as production "
            "requirements grow."
        ),
        "before_after": (
            "QC Checker Pro keeps the Core checks while adding configurable "
            "category membership and scene-specific collection exclusions, "
            "giving teams more control over how QC is applied."
        ),
        "benefits": [
            {
                "feature": "Everything in Core",
                "benefit": "Keep the standard QC foundation while adding Pro-only workflow controls.",
            },
            {
                "feature": "Check Settings",
                "benefit": "Customize which checks belong to each QC category without editing JSON by hand.",
            },
            {
                "feature": "Ignored Collections",
                "benefit": "Exclude intentional helper, reference, or temporary collections from selected checks or categories.",
            },
        ],
        "who_for": (
            "Studios, teams, technical artists, and advanced Blender users who "
            "need project-specific QC configuration beyond the standard Core workflow."
        ),
        "requirements": "Blender. Exact supported versions should be kept in the product release notes.",
        "buy_url": "",
    },
}


DEFAULT_PACK_CONTENT: dict[str, Any] = {
    "eyebrow": "QC Checker Pack",
    "primary_outcome": (
        "Add focused production checks to QC Checker for this specialist workflow."
    ),
    "hero_label": "60 second pack overview",
        "hero_youtube_id": "FlJaF2XkR6k",
        "hero_video_title": "NASA 4K Views from Space",
    "problem": (
        "Specialist departments have validation needs that go beyond the "
        "general-purpose checks included with QC Checker Core and Pro."
    ),
    "before_after": (
        "Install the pack and its checks appear inside QC Checker as additional "
        "categories and checks, while keeping the existing Core or Pro workflow."
    ),
    "benefits": [],
    "who_for": "Artists and teams working in this specialist Blender workflow.",
    "requirements": "Requires QC Checker Core or Pro.",
    "buy_url": "",
}


PACK_PAGE_CONTENT: dict[str, dict[str, Any]] = {
    "rigging": {
        "primary_outcome": (
            "Catch common rigging, weighting, IK, driver, constraint, and naming "
            "problems before animation or export."
        ),
        "hero_label": "60 second Rigging Pack overview",
        "hero_youtube_id": "FlJaF2XkR6k",
        "hero_video_title": "NASA 4K Views from Space",
        "problem": (
            "Rig problems can remain hidden until controls are animated, a rig "
            "is exported, or another artist starts working with the asset."
        ),
        "before_after": (
            "Instead of manually reviewing each rig subsystem, the Rigging Pack "
            "adds focused validation directly to the existing QC Checker workflow."
        ),
        "benefits": [
            {
                "feature": "Weight validation",
                "benefit": "Surface unweighted, non-normalized, and over-influenced vertices before deformation problems spread downstream.",
            },
            {
                "feature": "IK and driver validation",
                "benefit": "Find missing targets, invalid paths, and broken control relationships earlier.",
            },
            {
                "feature": "Rig structure checks",
                "benefit": "Review deform bones, duplicate constraints, and naming consistency from the same QC panel.",
            },
        ],
        "who_for": "Rigging artists, technical animators, character TDs, and Blender production teams.",
    },
}


def get_product_page_content(
        product_id: str,
        product_name: str,
        tier: str,
) -> dict[str, Any]:
    """Return editable page content with sensible defaults."""
    product_id = str(product_id).strip().lower()
    tier = str(tier).strip().lower()

    if tier == "pack":
        content = dict(DEFAULT_PACK_CONTENT)
        content.update(PACK_PAGE_CONTENT.get(product_id, {}))
        content["name"] = product_name
        return content

    content = dict(PRODUCT_PAGE_CONTENT.get(product_id, {}))
    content.setdefault("name", product_name)
    content.setdefault("eyebrow", "QC Checker")
    content.setdefault("primary_outcome", "Production-focused Blender quality control.")
    content.setdefault("hero_label", "60 second product overview")
    content.setdefault("problem", "Production quality problems are expensive when discovered late.")
    content.setdefault("before_after", "Use QC Checker to move validation earlier in the workflow.")
    content.setdefault("benefits", [])
    content.setdefault("who_for", "Blender artists and production teams.")
    content.setdefault("requirements", "Blender")
    content.setdefault("buy_url", "")
    return content
