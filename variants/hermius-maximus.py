from pathlib import Path

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
CLI_TOOLSETS = [
    "clarify",
    "code_execution",
    "context_engine",
    "cronjob",
    "delegation",
    "file",
    "kanban",
    "memory",
    "session_search",
    "skills",
    "terminal",
    "todo",
    "vision",
]
DISABLED_TOOLSETS = [
    "a2a",
    "bot_room",
    "browser",
    "catalog",
    "computer_use",
    "connections",
    "desktop_ui",
    "discord",
    "discord_admin",
    "feishu_doc",
    "feishu_drive",
    "image_gen",
    "onboarding",
    "project",
    "stt",
    "tts",
    "video",
    "video_gen",
    "web",
    "x_search",
]
INSTALL_URL = "https://hermes-agent.nousresearch.com/install.sh"
DASHBOARD_PORT = 9119
# Hermes restarts a user unit with exactly this name after `hermes update`.
DASHBOARD_UNIT = "hermes-dashboard.service"
PROXY_DEVICE = "dashboard"
