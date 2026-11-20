"""Stage 2: install and configure Hermes Agent in the container. Run on the LXD host."""

import io
import os
from getpass import getpass

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.files import File
from pyinfra.operations import files, server, snap, systemd

from helpers import (
    config_settings,
    dashboard_unit,
    env_line,
    merge_env_command,
    preflight,
)
from settings import (
    BASE_URL,
    CLAUDE_CODE,
    CLAUDE_CODE_INSTALL_URL,
    CONTEXT_LENGTH,
    DASHBOARD_PORT,
    DASHBOARD_UNIT,
    INSTALL_URL,
    KEY_ENV,
    MODEL,
    PM_EXTRAS,
    SSH_USER,
)

HOME = f"/home/{SSH_USER}"
HERMES = f"{HOME}/.local/bin/hermes"
ENV = f"{HOME}/.hermes/.env"
ENV_LLAMA = f"{HOME}/.hermes/.env.llama"

if host.state.config.DIFF:
    raise RuntimeError(
        "--diff would print the API key file contents; re-run without --diff"
    )
api_key = (os.environ.get("LLAMA_API_KEY") or getpass("llama.cpp API key: ")).strip()
line = env_line(KEY_ENV, api_key)
preflight(BASE_URL, MODEL, CONTEXT_LENGTH, api_key)

snap.package(
    name="Install Helix Editor Snap",
    packages=["helix"],
    classic=True,
    _sudo=True,
)

files.directory(name="Create ~/.hermes", path=f"{HOME}/.hermes", mode="700")
# Seeds only the essential hermes-agent skill instead of all bundled skills.
files.file(name="Skip bundled skills", path=f"{HOME}/.hermes/.no-bundled-skills")

install = None
if host.get_fact(File, path=HERMES) is None:
    install = server.shell(
        name="Run the Hermes installer",
        commands=[
            StringCommand(
                "curl -fsSL",
                QuoteString(INSTALL_URL),
                "| bash -s -- --skip-setup && test -x",
                QuoteString(HERMES),
            )
        ],
    )

if CLAUDE_CODE and host.get_fact(File, path=f"{HOME}/.local/bin/claude") is None:
    server.shell(
        name="Run the Claude Code installer",
        commands=[
            StringCommand("curl -fsSL", QuoteString(CLAUDE_CODE_INSTALL_URL), "| bash")
        ],
    )

if PM_EXTRAS:
    server.shell(
        name="Install Hermes Python extras",
        commands=[
            StringCommand(
                HERMES,
                "pm install",
                *[a for e in PM_EXTRAS for a in ("--extra", QuoteString(e))],
            )
        ],
    )

files.put(
    name="Write API key file",
    src=io.StringIO(line),
    dest=ENV_LLAMA,
    mode="600",
)

server.shell(
    name="Merge API key into .env",
    commands=[merge_env_command(ENV, ENV_LLAMA, KEY_ENV)],
)

server.shell(
    name="Apply config.yaml settings",
    commands=[
        StringCommand(HERMES, "config set", QuoteString(k), QuoteString(v))
        for k, v in config_settings()
    ],
)

files.directory(name="Create systemd user dir", path=f"{HOME}/.config/systemd/user")
unit = files.put(
    name="Install dashboard unit",
    src=io.StringIO(dashboard_unit(DASHBOARD_PORT)),
    dest=f"{HOME}/.config/systemd/user/{DASHBOARD_UNIT}",
)

# Linger starts the user manager at boot, so the dashboard runs without a login.
if host.get_fact(File, path=f"/var/lib/systemd/linger/{SSH_USER}") is None:
    server.shell(
        name="Enable linger",
        commands=[StringCommand("loginctl enable-linger", QuoteString(SSH_USER))],
        _sudo=True,
    )

# try-restart only acts on a running service, so a first install is unaffected.
server.shell(
    name="Restart dashboard after unit change",
    commands=[
        "systemctl --user daemon-reload",
        StringCommand("systemctl --user try-restart", QuoteString(DASHBOARD_UNIT)),
    ],
    _if=unit.did_change,
)

systemd.service(
    name="Enable and start dashboard",
    service=DASHBOARD_UNIT,
    running=True,
    enabled=True,
    user_mode=True,
)

server.shell(
    name="Check hermes doctor",
    # shortcut: allows doctor's "missing API keys" issue, which it also raises for web while web is disabled
    # (hermes_cli/doctor_tools.py:503). Drop the grep -v once Hermes filters web rows to CLI toolsets.
    commands=[
        StringCommand(
            "out=$(",
            HERMES,
            "doctor 2>&1); printf '%s\\n' \"$out\" >&2;",
            "printf '%s\\n' \"$out\" | grep -qE 'All checks passed|issue\\(s\\) to address' &&",
            "! printf '%s\\n' \"$out\" | grep -E '^ +[0-9]+\\. ' | grep -vF 'configure missing API keys for full tool access'",
        )
    ],
)
server.shell(
    name="Check hermes-agent skill",
    commands=[
        StringCommand(HERMES, "skills list | tee /dev/stderr | grep -q hermes-agent")
    ],
)
server.shell(
    name="Wait for dashboard",
    commands=[
        StringCommand(
            "for i in $(seq 100); do",
            "curl -sf",
            QuoteString(f"http://127.0.0.1:{DASHBOARD_PORT}/api/status"),
            "> /dev/null && exit 0;",
            "sleep 3; done; exit 1",
        )
    ],
)


def chat_test_wanted() -> bool:
    return (install is not None and install.did_change()) or bool(
        host.data.get("chat_test")
    )


server.shell(
    name="Chat tool-call test",
    commands=[
        StringCommand(
            HERMES,
            "chat --oneshot -q",
            QuoteString(
                "Run uname -a in the terminal and reply with its exact output."
            ),
            '< /dev/null | tee /dev/stderr | grep -qF "$(uname -r)"',
        )
    ],
    _if=chat_test_wanted,
    _timeout=600,
)
