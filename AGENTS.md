# Hermes on LXC

pyinfra 3.11.1 deploy that builds a Hermes Agent container on an LXD host (Ubuntu LXD snap). Run from this directory on the LXD host.

## Deploy

```bash
uv sync
HERMES_VARIANT=<name> uv run pyinfra @local launch.py                 # stage 1: create/start container, SSH + dashboard proxy
HERMES_VARIANT=<name> uv run pyinfra inventory.py hermes-deploy.py    # stage 2: install/configure Hermes over SSH
```

- `HERMES_VARIANT` names a `variants/*.py` file (no `.py`); `settings.py` loads it at import time. Required.
- Run stage 1 first: `inventory.py` reads the container IP from `lxc list` and fails if it is missing.
- Stage 1 runs on `@local` (the host) via `lxc exec`; stage 2 SSHes into the container.
- Variant `SSH_KEY_PATH` must have no passphrase: pyinfra cannot prompt for one.

## Tests

- `uv run pytest` (no LXD needed).
- `uv run pyright` typechecks (`[tool.pyright]`).
- `tests/conftest.py` defaults `HERMES_VARIANT=hermius-maximus`.

## Gotchas

- Never pass pyinfra `--diff` to `hermes-deploy.py`: it raises rather than print the API-key file. Use `--dry` to preview.
- `--data chat_test=true` forces the chat test; it also auto-runs on a first install.
- API key comes from the prompt or `LLAMA_API_KEY`; it is rejected if it contains `'` or a newline. It is written to the container's `~/.hermes/.env.llama` (0600) and merged into `.env`, never passed on a command line.
- Variant files must have unique `CONTAINER` and `DASHBOARD_PORT` across `variants/`; `settings.py` enforces this and names the conflicting file.
- `CONTEXT_LENGTH` must equal llama-server's per-slot `n_ctx`; `preflight()` also checks `/models`.
- `DASHBOARD_UNIT` is load-bearing: Hermes restarts a user unit with exactly that name after `hermes update`.
