from defaults import *
from pathlib import Path

# #################################################################################################
# Shared settings come from defaults.py. To change one for this variant only, uncomment and edit:
# #################################################################################################
#
# CLAUDE_CODE = True
# DISABLED_TOOLSETS = [*DISABLED_TOOLSETS, "kanban"]
# ENABLED_PLATFORM_TOOLSETS = {**ENABLED_PLATFORM_TOOLSETS, "api_server": ["clarify", "file", "memory"]}
# MOA_ENABLED = True
# PLUGINS_DISABLED = [p for p in PLUGINS_DISABLED if p != "web/searxng"]
# PLUGINS_ENABLED = [*PLUGINS_ENABLED, "deltachat-platform"]
# PM_EXTRAS = ["anthropic"]

CONTAINER = "hermius-maximus"
IMAGE = "ubuntu:26.04"
SSH_USER = "ubuntu"
SSH_KEY_PATH = (
    Path.home() / ".ssh/pyinfra/id_pyinfrava"
)  # no passphrase: pyinfra cannot prompt for one
PUBKEY_PATH = SSH_KEY_PATH.with_name(SSH_KEY_PATH.name + ".pub")

BASE_URL = "http://172.24.1.121:8080/v1"
MODEL = "ornith15"
CONTEXT_LENGTH = 262144
PROVIDER_KEY = "local-llama"  # never a built-in provider name such as "llamacpp"
PROVIDER_NAME = "Local Llama.cpp"
REASONING_EFFORT = "medium"
MAX_TURNS = 90
INSTALL_URL = "https://hermes-agent.nousresearch.com/install.sh"
DASHBOARD_PORT = 9119
# Hermes restarts a user unit with exactly this name after `hermes update`.
DASHBOARD_UNIT = "hermes-dashboard.service"
PROXY_DEVICE = "dashboard"
