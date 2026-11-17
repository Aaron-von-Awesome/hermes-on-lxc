"""Stage 1: create/start the LXD container and open SSH + dashboard access. Run on the LXD host."""
import os
import subprocess

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.lxd import LxdContainers
from pyinfra.operations import python, server

from helpers import (authorize_key_script, container_ipv4, container_state, ensure_keypair, has_device, lxc_list,
                     port_owner, read_pubkey)
from settings import CONTAINER, DASHBOARD_PORT, IMAGE, PROXY_DEVICE, PUBKEY_PATH, SSH_KEY_PATH, SSH_USER

KNOWN_HOSTS = os.path.expanduser("~/.ssh/known_hosts")
ensure_keypair(SSH_KEY_PATH)
pubkey = read_pubkey(PUBKEY_PATH)
containers = host.get_fact(LxdContainers)
state = container_state(containers, CONTAINER)
LISTEN = f"tcp:127.0.0.1:{DASHBOARD_PORT}"
owner = port_owner(containers, DASHBOARD_PORT, CONTAINER)
if owner is not None:
    raise RuntimeError(f"Port {DASHBOARD_PORT} is already used by container {owner}; pick another DASHBOARD_PORT")


def forget_host_key() -> None:
    # A fresh container gets a new host key; drop any stale entry for the reused IP.
    ip = container_ipv4(lxc_list(), CONTAINER)
    if ip is None:
        raise RuntimeError(f"{CONTAINER} has no global IPv4 address")
    if os.path.exists(KNOWN_HOSTS):
        subprocess.run(["ssh-keygen", "-R", ip], check=True)


launch = None
if state == "absent":
    launch = server.shell(
        name="Launch container",
        commands=[StringCommand(
            "lxc launch", QuoteString(IMAGE), QuoteString(CONTAINER), "< /dev/null",
        )],
    )
elif state == "stopped":
    server.shell(
        name="Start container",
        commands=[StringCommand("lxc start", QuoteString(CONTAINER))],
    )

APT = ("DEBIAN_FRONTEND=noninteractive apt-get -q -y -o DPkg::Lock::Timeout=300"
       " -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold")


def wait_for_cloud_init(name: str) -> None:
    server.shell(
        name=name,
        commands=[StringCommand("lxc exec", QuoteString(CONTAINER), "-- cloud-init status --wait")],
        _success_exit_codes=[0, 2],  # 2 = done with recoverable errors
    )


def in_container(script: str) -> StringCommand:
    return StringCommand("lxc exec", QuoteString(CONTAINER), "-- sh -c", QuoteString(script))


wait_for_cloud_init("Wait for cloud-init")

# Restart only when the upgrade installs something, so a re-run does not bounce the dashboard.
server.shell(
    name="Upgrade packages, restart if any changed",
    commands=[StringCommand(
        in_container(f"{APT} update"),
        "&& if", in_container(f"{APT} -s full-upgrade | grep -q '^Inst'"),
        "; then", in_container(f"{APT} full-upgrade"),
        "&& lxc restart", QuoteString(CONTAINER), "; fi",
    )],
    _timeout=1800,
)

wait_for_cloud_init("Wait for boot after restart")

if launch is not None:
    python.call(
        name="Forget stale SSH host key",
        function=forget_host_key,
        _if=launch.did_change,
    )

server.shell(
    name="Authorize operator SSH key",
    commands=[StringCommand(
        "lxc exec", QuoteString(CONTAINER), "-- su -", QuoteString(SSH_USER), "-c",
        QuoteString(authorize_key_script(pubkey)),
    )],
)

if not has_device(containers, CONTAINER, PROXY_DEVICE):
    server.shell(
        name="Add dashboard proxy device",
        commands=[StringCommand(
            "lxc config device add", QuoteString(CONTAINER), QuoteString(PROXY_DEVICE), "proxy",
            QuoteString(f"listen={LISTEN}"),
            QuoteString(f"connect=tcp:127.0.0.1:{DASHBOARD_PORT}"),
        )],
    )
