"""Loads deploy/variants/<HERMES_VARIANT>.py into this module, plus KEY_ENV computed from BASE_URL."""
import os
import re
import runpy
from pathlib import Path
from urllib.parse import urlparse

VARIANTS_DIR = Path(__file__).parent / "variants"


def key_env_for(base_url: str) -> str:
    # Same rule as Hermes custom_endpoint_key_env (hermes_cli/config.py), keyed on host:port.
    slug = re.sub(r"[^A-Z0-9]+", "_", urlparse(base_url).netloc.rpartition("@")[2].upper()).strip("_")
    return f"HERMES_CUSTOM_{slug}_API_KEY" if slug else "HERMES_CUSTOM_API_KEY"


def load_variant(name: str | None, folder: Path) -> dict[str, object]:
    names = sorted(p.stem for p in folder.glob("*.py"))
    if name not in names:
        raise RuntimeError(f"Set HERMES_VARIANT to one of: {', '.join(names)} (got {name!r})")
    values = {k: v for k, v in runpy.run_path(str(folder / f"{name}.py")).items() if k.isupper()}
    for other in names:
        if other == name:
            continue
        theirs = runpy.run_path(str(folder / f"{other}.py"))
        for key in ("CONTAINER", "DASHBOARD_PORT"):
            if key in values and theirs.get(key) == values[key]:
                raise RuntimeError(f"{key} {values[key]!r} is also set in {other}.py; each variant needs its own")
    values["KEY_ENV"] = key_env_for(values.get("BASE_URL", ""))
    return values


globals().update(load_variant(os.environ.get("HERMES_VARIANT"), VARIANTS_DIR))
