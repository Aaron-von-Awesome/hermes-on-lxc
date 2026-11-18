# Hermes on LXC

Deploy Hermes Agent in an LXD container with pyinfra, using the Ubuntu LXD snap. Run on the LXD host, from this folder.

```bash
uv sync
HERMES_VARIANT=hermius-maximus uv run pyinfra @local launch.py
HERMES_VARIANT=hermius-maximus uv run pyinfra inventory.py hermes-deploy.py
```

- `HERMES_VARIANT` names a file in `variants/` (without `.py`). For a new variant, copy a file and change `CONTAINER` and `DASHBOARD_PORT` (both must be unique across variants).
- Stage 1 (`launch.py`) creates/starts the container and opens SSH + dashboard access; stage 2 (`hermes-deploy.py`) installs and configures Hermes over SSH.
- `hermes-deploy.py` asks for the llama.cpp API key, or reads it from `LLAMA_API_KEY`.
- Add `--dry` to preview the changes. Never add `--diff`: the deploy aborts rather than print the API-key file. Add `--data chat_test=true` to force the chat test.
- Tests: `uv run pytest` (no LXD needed).

## Toolsets and plugins

Each variant sets these explicitly; stage 2 writes them to `config.yaml` on every run, so edits made in `hermes tools` or the dashboard are reset.

- `ENABLED_PLATFORM_TOOLSETS`: dict of platform → toolset allow-list, written as `platform_toolsets.<platform>` (today `cli` and `api_server`). A platform left out uses Hermes' broad default. Removing a platform from the dict does not delete its existing `config.yaml` entry.
- `DISABLED_TOOLSETS`: `agent.disabled_toolsets`, removed on every platform, even if a platform list includes them.
- `PLUGINS_ENABLED`: `plugins.enabled`. Third-party plugins load only when listed here.
- `PLUGINS_DISABLED`: `plugins.disabled`. Bundled backend and platform plugins load without being enabled, so this list keeps them off; it wins over `PLUGINS_ENABLED`. Hermes has no wildcard. After `hermes update`, list new bundled ones with:

  ```bash
  cd hermes-agent/plugins && grep -lE '^kind: (backend|platform)' */*/plugin.yaml | xargs -n1 dirname
  ```

## Container can't reach the internet

If the LXC cannot connect to the internet, stage 2 fails like this:

    [10.98.171.146] curl: (28) Failed to connect to hermes-agent.nousresearch.com port 443 after 133407 ms: Could not connect to server
    [10.98.171.146] Error: executed 0 commands

Run these on the host to allow traffic from `lxdbr0` and its replies through Docker's `DOCKER-USER` chain:

```bash
sudo iptables -I DOCKER-USER -i lxdbr0 -j ACCEPT
sudo iptables -I DOCKER-USER -o lxdbr0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
```

The rules don't survive a host reboot. Re-run them, or persist with:

```bash
sudo mkdir -p /etc/iptables
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

Then restore them at boot with `/etc/systemd/system/iptables-restore.service`:

```ini
[Unit]
Description=Restore iptables rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now iptables-restore.service
```
