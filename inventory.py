"""Stage 2 inventory: the container's IPv4, reached over SSH. Run on the LXD host."""
from helpers import container_ipv4, lxc_list
from settings import CONTAINER, SSH_KEY_PATH, SSH_USER

ip = container_ipv4(lxc_list(), CONTAINER)
if ip is None:
    raise RuntimeError(f"{CONTAINER} has no IPv4 address; run launch.py first")

hosts = [(ip, {"ssh_user": SSH_USER, "ssh_key": str(SSH_KEY_PATH), "ssh_strict_host_key_checking": "accept-new"})]
