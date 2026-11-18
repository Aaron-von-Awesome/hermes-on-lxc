import json
import shlex
import subprocess
import urllib.request
from pathlib import Path
from typing import Literal

from pyinfra.api import QuoteString, StringCommand

import settings


def lxc_list() -> list[dict]:
    out = subprocess.run(
        ["lxc", "list", "--format", "json"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return json.loads(out.stdout)


def ensure_keypair(key: Path) -> None:
    if key.exists():
        return
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # No passphrase: pyinfra cannot prompt for one.
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True
    )


def read_pubkey(path: Path) -> str:
    try:
        return path.read_text().strip()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"SSH public key not found: {path}") from e


def authorize_key_script(pubkey: str) -> str:
    return f"""set -eu
key={shlex.quote(pubkey)}
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
grep -qxF "$key" "$HOME/.ssh/authorized_keys" || printf '%s\\n' "$key" >> "$HOME/.ssh/authorized_keys"
"""


def _find(containers: list[dict], name: str) -> dict | None:
    return next((c for c in containers if c.get("name") == name), None)


def container_state(
    containers: list[dict], name: str
) -> Literal["absent", "stopped", "running"]:
    c = _find(containers, name)
    if c is None:
        return "absent"
    return "running" if c.get("status") == "Running" else "stopped"


def container_ipv4(containers: list[dict], name: str) -> str | None:
    c = _find(containers, name) or {}
    addrs = (((c.get("state") or {}).get("network") or {}).get("eth0") or {}).get(
        "addresses"
    ) or []
    return next(
        (
            a["address"]
            for a in addrs
            if a.get("family") == "inet" and a.get("scope") == "global"
        ),
        None,
    )


def has_device(containers: list[dict], name: str, device: str) -> bool:
    return device in ((_find(containers, name) or {}).get("devices") or {})


def proxy_device_matches(
    containers: list[dict], name: str, device: str, listen: str, connect: str
) -> bool:
    d = ((_find(containers, name) or {}).get("devices") or {}).get(device) or {}
    return (
        d.get("type") == "proxy"
        and d.get("listen") == listen
        and d.get("connect") == connect
    )


def proxy_device_commands(
    containers: list[dict], name: str, device: str, listen: str, connect: str
) -> list[StringCommand]:
    # Whole commands only: pyinfra runs each list item as its own shell command.
    commands: list[StringCommand] = []
    if has_device(containers, name, device):
        commands.append(
            StringCommand(
                "lxc config device remove",
                QuoteString(name),
                QuoteString(device),
            )
        )
    commands.append(
        StringCommand(
            "lxc config device add",
            QuoteString(name),
            QuoteString(device),
            "proxy",
            QuoteString(f"listen={listen}"),
            QuoteString(f"connect={connect}"),
        )
    )
    return commands


def port_owner(containers: list[dict], port: int, exclude: str) -> str | None:
    # Any listen address counts, and profile devices show only in expanded_devices.
    return next(
        (
            c["name"]
            for c in containers
            if c["name"] != exclude
            for d in {
                **(c.get("expanded_devices") or {}),
                **(c.get("devices") or {}),
            }.values()
            if d.get("type") == "proxy"
            and d.get("listen", "").rsplit(":", 1)[-1] == str(port)
        ),
        None,
    )


def env_line(key_env: str, api_key: str) -> str:
    if not api_key or "'" in api_key or "\n" in api_key or "\r" in api_key:
        raise ValueError(
            "API key is empty or contains a single quote, newline, or carriage return; .env cannot store it safely."
        )
    # Single quotes: python-dotenv would expand `$` and strip ` #...` in an unquoted value.
    return f"{key_env}='{api_key}'\n"


def merge_env_command(env: str, env_llama: str, key_env: str) -> StringCommand:
    # Reads the key from env_llama, so it never appears on a command line.
    return StringCommand(
        "touch",
        QuoteString(env),
        "&& { grep -qxFf",
        QuoteString(env_llama),
        QuoteString(env),
        "|| {",
        "sed -i",
        QuoteString(f"/^{key_env}=/d"),
        QuoteString(env),
        "&& sed -i -e",
        QuoteString("$a\\"),
        QuoteString(env),
        "&& cat",
        QuoteString(env_llama),
        ">>",
        QuoteString(env),
        "; } ; }",
        "&& chmod 600",
        QuoteString(env),
    )


def config_settings() -> list[tuple[str, str]]:
    s = settings
    values = {
        # provider before base_url: a provider switch clears the old route's base_url
        "model.provider": "custom",
        "model.base_url": s.BASE_URL,
        "model.default": s.MODEL,
        "model.api_key": "${" + s.KEY_ENV + "}",
        "providers": {
            s.PROVIDER_KEY: {
                "name": s.PROVIDER_NAME,
                "base_url": s.BASE_URL,
                "key_env": s.KEY_ENV,
                "default_model": s.MODEL,
                "models": {s.MODEL: {"context_length": s.CONTEXT_LENGTH}},
            }
        },
        "terminal.backend": "local",
        "agent.max_turns": s.MAX_TURNS,
        "agent.reasoning_effort": s.REASONING_EFFORT,
        "agent.disabled_toolsets": s.DISABLED_TOOLSETS,
        **{f"platform_toolsets.{p}": t for p, t in s.ENABLED_PLATFORM_TOOLSETS.items()},
        "plugins.enabled": s.PLUGINS_ENABLED,
        "plugins.disabled": s.PLUGINS_DISABLED,
        "compression.enabled": True,
        "memory.memory_enabled": True,
        "memory.user_profile_enabled": True,
        "checkpoints.enabled": False,
        "smart_model_routing.enabled": False,
    }
    return [(k, v if isinstance(v, str) else json.dumps(v)) for k, v in values.items()]


def dashboard_unit(port: int) -> str:
    return f"""[Unit]
Description=Hermes Agent web dashboard
After=network-online.target

[Service]
ExecStart=%h/.local/bin/hermes dashboard --host 127.0.0.1 --port {port} --no-open
Restart=always
RestartSec=10
# Exit 78: Hermes refuses because another dashboard already serves this host.
RestartPreventExitStatus=78

[Install]
WantedBy=default.target
"""


def _http_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def preflight(base_url: str, model: str, context_length: int, api_key: str) -> None:
    base_url = base_url.rstrip("/")
    try:
        models = [
            m.get("id")
            for m in _http_json(f"{base_url}/models", api_key).get("data", [])
        ]
    except Exception as e:  # noqa: BLE001 - any failure means "server not usable"
        raise RuntimeError(f"GET /models failed: {e}") from e
    if model not in models:
        raise RuntimeError(f"model {model!r} not served; server lists {models}")
    root = base_url.removesuffix("/v1")
    try:
        n_ctx = (
            _http_json(f"{root}/props", api_key)
            .get("default_generation_settings", {})
            .get("n_ctx")
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"GET /props failed: {e}") from e
    if n_ctx != context_length:
        raise RuntimeError(
            f"per-slot context is {n_ctx}, expected {context_length} (check llama-server -c / -np)"
        )
