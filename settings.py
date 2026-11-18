"""Loads variants/<HERMES_VARIANT>.py into this module, plus KEY_ENV computed from BASE_URL."""

import ast
import os
import re
import runpy
from pathlib import Path
from urllib.parse import urlparse

VARIANTS_DIR = Path(__file__).parent / "variants"


def key_env_for(base_url: str) -> str:
    # Same rule as Hermes custom_endpoint_key_env (hermes_cli/config.py), keyed on host:port.
    slug = re.sub(
        r"[^A-Z0-9]+", "_", urlparse(base_url).netloc.rpartition("@")[2].upper()
    ).strip("_")
    return f"HERMES_CUSTOM_{slug}_API_KEY" if slug else "HERMES_CUSTOM_API_KEY"


def _variant_literals(path: Path) -> dict[str, object]:
    # Read only literals: another variant with a broken import must not break this one.
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, ValueError):
        return {}
    out = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("CONTAINER", "DASHBOARD_PORT")
        ):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def load_variant(name: str | None, folder: Path) -> dict[str, object]:
    names = sorted(p.stem for p in folder.glob("*.py"))
    if name not in names:
        raise RuntimeError(
            f"Set HERMES_VARIANT to one of: {', '.join(names)} (got {name!r})"
        )
    values = {
        k: v
        for k, v in runpy.run_path(str(folder / f"{name}.py")).items()
        if k.isupper()
    }
    for other in names:
        if other == name:
            continue
        theirs = _variant_literals(folder / f"{other}.py")
        for key in ("CONTAINER", "DASHBOARD_PORT"):
            if key in values and theirs.get(key) == values[key]:
                raise RuntimeError(
                    f"{key} {values[key]!r} is also set in {other}.py; each variant needs its own"
                )
    values["KEY_ENV"] = key_env_for(values.get("BASE_URL", ""))
    return values


globals().update(load_variant(os.environ.get("HERMES_VARIANT"), VARIANTS_DIR))
