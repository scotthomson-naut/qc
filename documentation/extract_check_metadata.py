"""Extract QC check metadata without importing Blender or executing checks."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

IGNORED_FILENAMES = {"__init__.py"}
VALID_SEVERITIES = {"critical", "warning", "info"}


def literal_value(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def module_assignments(tree: ast.Module) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = literal_value(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values[node.target.id] = literal_value(node.value)
    return values


def top_level_functions(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def ast_dict_mapping(node: ast.Dict) -> dict[str, ast.AST]:
    result: dict[str, ast.AST] = {}
    for key_node, value_node in zip(node.keys, node.values):
        key = literal_value(key_node)
        if isinstance(key, str):
            result[key] = value_node
    return result


def detect_selection(tree: ast.Module) -> str:
    modes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        mapping = ast_dict_mapping(node)
        selection_node = mapping.get("selection")
        if not isinstance(selection_node, ast.Dict):
            continue
        selection_mapping = ast_dict_mapping(selection_node)
        mode = literal_value(selection_mapping.get("mode"))
        if isinstance(mode, str):
            modes.add(mode.upper())

    labels = {
        "VERT": "Vertices",
        "VERTEX": "Vertices",
        "EDGE": "Edges",
        "FACE": "Faces",
        "MIXED": "Vertices, edges and faces",
        "OBJECT": "Object",
    }
    if not modes:
        return "Object"
    return " / ".join(labels.get(mode, title_from_identifier(mode)) for mode in sorted(modes))


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip()).strip("_").lower()


def title_from_identifier(value: str) -> str:
    special = {
        "ascii": "ASCII",
        "nla": "NLA",
        "qc": "QC",
        "uv": "UV",
        "uvs": "UVs",
        "ngons": "N-Gons",
        "cycles": "Cycles",
    }
    words = re.sub(r"[_\-]+", " ", str(value).strip()).split()
    return " ".join(special.get(word.lower(), word.capitalize()) for word in words)


def normalize_settings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    settings: list[dict[str, Any]] = []
    for name, definition in value.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            continue
        item: dict[str, Any] = {
            "id": name,
            "label": str(definition.get("label") or title_from_identifier(name)),
            "description": str(definition.get("description") or ""),
            "type": str(definition.get("type") or "string").lower(),
            "default": definition.get("default"),
        }
        for key in ("min", "max", "soft_min", "soft_max", "step", "precision", "items"):
            if key in definition:
                item[key] = definition[key]
        settings.append(item)
    return settings


def parse_check(script_path: Path, category: str, root: Path) -> dict[str, Any]:
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))
    assigned = module_assignments(tree)
    functions = top_level_functions(tree)

    check_id = script_path.stem
    severity = str(assigned.get("SEVERITY") or "warning").lower()
    if severity not in VALID_SEVERITIES:
        severity = "warning"

    settings = normalize_settings(assigned.get("SETTINGS"))
    explicit_fix = assigned.get("has_fix")
    has_fix = "fix" in functions
    if isinstance(explicit_fix, bool):
        has_fix = explicit_fix and has_fix

    docs = assigned.get("DOCS") if isinstance(assigned.get("DOCS"), dict) else {}

    return {
        "category": title_from_identifier(category),
        "categoryId": normalize_identifier(category),
        "id": check_id,
        "label": str(assigned.get("LABEL") or title_from_identifier(check_id)),
        "description": str(assigned.get("DESCRIPTION") or ""),
        "why": str(assigned.get("WHY") or docs.get("why") or ""),
        "fixDescription": str(docs.get("fix_description") or ""),
        "notes": docs.get("notes") if isinstance(docs.get("notes"), list) else [],
        "severity": severity,
        "hasFix": has_fix,
        "hasSettings": bool(settings),
        "settings": settings,
        "selection": detect_selection(tree),
        "source": script_path.relative_to(root).as_posix(),
    }


def generate_metadata(
    checks_dir: str | Path,
    output_json: str | Path,
    output_js: str | Path | None = None,
    categories: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    root = Path(checks_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"QC checks directory does not exist: {root}")

    category_names = (
        sorted(normalize_identifier(name) for name in categories)
        if categories
        else sorted(
            path.name
            for path in root.iterdir()
            if path.is_dir() and path.name != "__pycache__" and not path.name.startswith(".")
        )
    )

    records: list[dict[str, Any]] = []
    for category in category_names:
        category_dir = root / category
        if not category_dir.is_dir():
            print(f"Warning: category folder not found: {category_dir}")
            continue
        for script_path in sorted(category_dir.glob("*.py"), key=lambda p: p.name.lower()):
            if script_path.name in IGNORED_FILENAMES:
                continue
            try:
                records.append(parse_check(script_path, category, root))
            except Exception as error:
                print(f"Warning: could not parse {script_path}: {error}")

    records.sort(key=lambda record: (record["categoryId"], record["label"].lower()))

    json_path = Path(output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(records, indent=4, ensure_ascii=False) + "\n"
    json_path.write_text(json_text, encoding="utf-8")

    if output_js:
        js_path = Path(output_js)
        js_path.parent.mkdir(parents=True, exist_ok=True)
        js_path.write_text(
            "/* Auto-generated. Do not edit manually. */\n\n"
            f"window.QC_CHECKS = {json.dumps(records, indent=4, ensure_ascii=False)};\n",
            encoding="utf-8",
        )

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract QC metadata from check modules.")
    parser.add_argument("checks_dir")
    parser.add_argument("output_json")
    parser.add_argument("--js", dest="output_js")
    parser.add_argument("--categories", nargs="*")
    args = parser.parse_args()

    records = generate_metadata(
        args.checks_dir,
        args.output_json,
        output_js=args.output_js,
        categories=args.categories,
    )
    print(f"Extracted {len(records)} QC checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
