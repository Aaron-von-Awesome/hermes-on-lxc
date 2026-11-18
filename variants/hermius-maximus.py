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
# One allow-list per surface (platform_toolsets.<name>); a surface left out uses Hermes' broad default.
ENABLED_PLATFORM_TOOLSETS = {
    "cli": [
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
    ],
    "api_server": [
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
    ],
}
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
PLUGINS_ENABLED = [
    "delegation/default",  # bundled, loads anyway; listed to be explicit
]
# Bundled backends and platforms skip plugins.enabled; only this list keeps them off.
PLUGINS_DISABLED = [
    "browser/browser_use",
    "browser/browserbase",
    "browser/firecrawl",
    "dashboard_auth/basic",
    "dashboard_auth/drain",
    "dashboard_auth/nous",
    "dashboard_auth/self_hosted",
    "dashboard_auth/session_token",
    "image_gen/deepinfra",
    "image_gen/fal",
    "image_gen/krea",
    "image_gen/meta-ai",
    "image_gen/openai",
    "image_gen/openai-codex",
    "image_gen/openrouter",
    "image_gen/xai",
    "platforms/a2a",
    "platforms/bluebubbles",
    "platforms/buzz",
    "platforms/dingtalk",
    "platforms/discord",
    "platforms/email",
    "platforms/feishu",
    "platforms/google_chat",
    "platforms/irc",
    "platforms/line",
    "platforms/matrix",
    "platforms/mattermost",
    "platforms/ntfy",
    "platforms/photon",
    "platforms/qqbot",
    "platforms/raft",
    "platforms/signal",
    "platforms/simplex",
    "platforms/slack",
    "platforms/sms",
    "platforms/teams",
    "platforms/telegram",
    "platforms/wecom",
    "platforms/weixin",
    "platforms/whatsapp",
    "platforms/whatsapp_cloud",
    "video_gen/deepinfra",
    "video_gen/fal",
    "video_gen/openrouter",
    "video_gen/xai",
    "web/brave_free",
    "web/ddgs",
    "web/exa",
    "web/firecrawl",
    "web/keenable",
    "web/openai_native",
    "web/parallel",
    "web/perplexity",
    "web/searxng",
    "web/tavily",
    "web/xai",
]
INSTALL_URL = "https://hermes-agent.nousresearch.com/install.sh"
DASHBOARD_PORT = 9119
# Hermes restarts a user unit with exactly this name after `hermes update`.
DASHBOARD_UNIT = "hermes-dashboard.service"
PROXY_DEVICE = "dashboard"
