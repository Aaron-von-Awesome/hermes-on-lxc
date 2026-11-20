import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from pyinfra.api import StringCommand

import helpers
import settings

KEY = "ssh-ed25519 AAAAC3 test@host"


def test_read_pubkey_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="nokey.pub"):
        helpers.read_pubkey(tmp_path / "nokey.pub")


def test_read_pubkey_strips(tmp_path):
    p = tmp_path / "k.pub"
    p.write_text(KEY + "\n")
    assert helpers.read_pubkey(p) == KEY


def test_authorize_key_script_is_idempotent(tmp_path):
    script = helpers.authorize_key_script(KEY)
    for _ in range(2):
        subprocess.run(
            ["sh", "-c", script], check=True, env={**os.environ, "HOME": str(tmp_path)}
        )
    ak = tmp_path / ".ssh/authorized_keys"
    assert ak.read_text().splitlines().count(KEY) == 1
    assert ak.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".ssh").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "status,expected", [("Stopped", "stopped"), ("Running", "running")]
)
def test_container_state(status, expected):
    assert (
        helpers.container_state(
            [{"name": "hermius-maximus", "status": status}], "hermius-maximus"
        )
        == expected
    )


def test_container_state_absent():
    assert (
        helpers.container_state(
            [{"name": "other", "status": "Running"}], "hermius-maximus"
        )
        == "absent"
    )
    assert helpers.container_state([], "hermius-maximus") == "absent"


def _net(addrs):
    return [{"name": "c", "state": {"network": {"eth0": {"addresses": addrs}}}}]


def test_container_ipv4():
    addrs = [
        {"family": "inet6", "address": "fe80::1", "scope": "link"},
        {"family": "inet", "address": "10.1.2.3", "scope": "global"},
    ]
    assert helpers.container_ipv4(_net(addrs), "c") == "10.1.2.3"


def test_container_ipv4_none_when_no_address():
    assert helpers.container_ipv4([{"name": "c", "state": None}], "c") is None
    assert helpers.container_ipv4(_net([]), "c") is None
    assert helpers.container_ipv4([], "c") is None


def test_has_device():
    assert helpers.has_device(
        [{"name": "c", "devices": {"dashboard": {"type": "proxy"}}}], "c", "dashboard"
    )
    assert not helpers.has_device([{"name": "c", "devices": {}}], "c", "dashboard")
    assert not helpers.has_device([], "c", "dashboard")


def test_proxy_device_commands_are_whole_commands():
    listen = connect = "tcp:127.0.0.1:9119"
    stale = [
        {
            "name": "c",
            "devices": {"dashboard": {"type": "proxy", "listen": "tcp:127.0.0.1:1"}},
        }
    ]
    cmds = helpers.proxy_device_commands(stale, "c", "dashboard", listen, connect)
    assert len(cmds) == 2
    assert all(isinstance(c, StringCommand) for c in cmds)
    assert "remove" in cmds[0].get_raw_value()
    assert "add" in cmds[1].get_raw_value()
    # A missing device only adds; no bare shell operator is ever emitted.
    cmds = helpers.proxy_device_commands([], "c", "dashboard", listen, connect)
    assert len(cmds) == 1
    assert "add" in cmds[0].get_raw_value()
    for c in cmds:
        assert c.get_raw_value().strip() not in {"&&", "||", ";", "|"}


def test_proxy_device_matches():
    listen = connect = "tcp:127.0.0.1:9119"
    dev = {"type": "proxy", "listen": listen, "connect": connect}
    cs = [{"name": "c", "devices": {"dashboard": dev}}]
    assert helpers.proxy_device_matches(cs, "c", "dashboard", listen, connect)
    assert not helpers.proxy_device_matches(
        cs, "c", "dashboard", "tcp:127.0.0.1:9120", connect
    )
    assert not helpers.proxy_device_matches(
        cs, "c", "dashboard", listen, "tcp:127.0.0.1:9120"
    )
    assert not helpers.proxy_device_matches(
        [{"name": "c", "devices": {}}], "c", "dashboard", listen, connect
    )
    assert not helpers.proxy_device_matches(cs, "c", "other", listen, connect)


@pytest.mark.parametrize("bad", ["a'b", "a\nb", "a\rb", ""])
def test_env_line_rejects_quote_and_newline(bad):
    with pytest.raises(ValueError):
        helpers.env_line("KEY", bad)


def test_env_line_keeps_dollar_and_hash():
    assert helpers.env_line("KEY", "ab$c #1") == "KEY='ab$c #1'\n"


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", True])
def test_flag_is_true(value):
    assert helpers.flag_is_true(value)


@pytest.mark.parametrize("value", [None, "", "false", "0", "no", "off", False])
def test_flag_is_false(value):
    assert not helpers.flag_is_true(value)


def test_config_settings_order_and_encoding():
    s = helpers.config_settings()
    assert [k for k, _ in s[:2]] == ["model.provider", "model.base_url"]
    d = dict(s)
    assert ("compression.enabled", "true") in s
    assert ("terminal.backend", "local") in s
    assert d["model.api_key"] == "${" + settings.KEY_ENV + "}"
    prov = json.loads(d["providers"])["local-llama"]
    assert prov["models"] == {"ornith15": {"context_length": 262144}}
    assert json.loads(d["agent.max_turns"]) == 90
    assert json.loads(d["plugins.enabled"]) == ["delegation/default"]
    assert "terminal" in json.loads(d["platform_toolsets.cli"])
    assert "terminal" in json.loads(d["platform_toolsets.api_server"])
    disabled = json.loads(d["plugins.disabled"])
    assert {"web/keenable", "platforms/telegram", "dashboard_auth/nous"} <= set(
        disabled
    )
    assert "delegation/default" not in disabled
    moa = json.loads(d["moa.presets.default"])
    slot = {"provider": "local-llama", "model": "ornith15"}
    assert moa == {"enabled": False, "reference_models": [slot], "aggregator": slot}


def test_dashboard_unit():
    u = helpers.dashboard_unit(9119)
    assert (
        "ExecStart=%h/.local/bin/hermes dashboard --host 127.0.0.1 --port 9119 --no-open"
        in u
    )
    assert "RestartPreventExitStatus=78" in u
    assert "WantedBy=default.target" in u


def _serve(models, n_ctx):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer k"
            if self.path == "/v1/models":
                body = {"data": [{"id": m} for m in models]}
            elif self.path == "/props":
                body = {"default_generation_settings": {"n_ctx": n_ctx}}
            else:
                self.send_error(404)
                return
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args, **kwargs):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/v1"


@pytest.fixture
def serve():
    servers = []

    def make(models, n_ctx):
        srv, url = _serve(models, n_ctx)
        servers.append(srv)
        return url

    yield make
    for s in servers:
        s.shutdown()


def test_preflight_ok(serve):
    helpers.preflight(serve(["m"], 100), "m", 100, "k")


def test_preflight_trailing_slash(serve):
    helpers.preflight(serve(["m"], 100) + "/", "m", 100, "k")


def test_preflight_model_missing(serve):
    with pytest.raises(RuntimeError, match="not served"):
        helpers.preflight(serve(["x"], 100), "m", 100, "k")


def test_preflight_wrong_ctx(serve):
    with pytest.raises(RuntimeError, match="per-slot context is 50"):
        helpers.preflight(serve(["m"], 50), "m", 100, "k")


def test_preflight_unreachable():
    srv = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = srv.server_port
    srv.server_close()
    with pytest.raises(RuntimeError, match="GET /models failed"):
        helpers.preflight(f"http://127.0.0.1:{port}/v1", "m", 100, "k")


def test_merge_env_command(tmp_path):
    env, llama = tmp_path / ".env", tmp_path / ".env.llama"
    env.write_text("A=1\nK='old'\nB=2")  # no final newline
    llama.write_text("K='new'\n")
    cmd = helpers.merge_env_command(str(env), str(llama), "K").get_raw_value()
    for _ in range(2):
        subprocess.run(["bash", "-c", cmd], check=True)
        assert env.read_text() == "A=1\nB=2\nK='new'\n"
    assert oct(env.stat().st_mode & 0o777) == "0o600"


def test_merge_env_command_creates_env(tmp_path):
    env, llama = tmp_path / ".env", tmp_path / ".env.llama"
    llama.write_text("K='new'\n")
    subprocess.run(
        [
            "bash",
            "-c",
            helpers.merge_env_command(str(env), str(llama), "K").get_raw_value(),
        ],
        check=True,
    )
    assert env.read_text() == "K='new'\n"


def test_ensure_keypair(tmp_path):
    key = tmp_path / "pyinfra/id_test"
    helpers.ensure_keypair(key)
    pub = key.with_name("id_test.pub").read_text()
    assert pub.startswith("ssh-ed25519 ")
    assert key.stat().st_mode & 0o777 == 0o600
    assert key.parent.stat().st_mode & 0o777 == 0o700
    helpers.ensure_keypair(key)  # existing key is kept
    assert key.with_name("id_test.pub").read_text() == pub


def test_port_owner_finds_other():
    for listen in ("tcp:127.0.0.1:9119", "tcp:0.0.0.0:9119", "tcp:localhost:9119"):
        cs = [
            {"name": "a", "devices": {"dashboard": {"type": "proxy", "listen": listen}}}
        ]
        assert helpers.port_owner(cs, 9119, "b") == "a"


def test_port_owner_finds_profile_device():
    cs = [
        {
            "name": "a",
            "devices": {},
            "expanded_devices": {
                "p": {"type": "proxy", "listen": "tcp:127.0.0.1:9119"}
            },
        }
    ]
    assert helpers.port_owner(cs, 9119, "b") == "a"


def test_port_owner_ignores_own_container():
    cs = [
        {
            "name": "a",
            "devices": {"dashboard": {"type": "proxy", "listen": "tcp:127.0.0.1:9119"}},
        }
    ]
    assert helpers.port_owner(cs, 9119, "a") is None


def test_port_owner_none():
    cs = [
        {
            "name": "a",
            "devices": {
                "x": {"type": "disk"},
                "y": {"type": "proxy", "listen": "tcp:127.0.0.1:19119"},
            },
        },
        {"name": "b", "devices": None},
    ]
    assert helpers.port_owner(cs, 9119, "c") is None
