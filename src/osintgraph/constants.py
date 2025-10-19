import os
from platformdirs import user_config_dir

GIT_REPO = "https://api.github.com/repos/XD-MHLOO/Osintgraph/releases/latest"
TREE_TOP_API = "https://api.github.com/repos/XD-MHLOO/osintgraph-templates/git/trees/main"
CONTENTS_API = "https://api.github.com/repos/XD-MHLOO/osintgraph-templates/contents/templates"

USEFUL_FIELDS = {
    "Person": ["username", "fullname", "bio", "account_analysis"],
    "Post": ["caption", "title" , "image_analysis", "post_analysis"],
    "Comment": ["text"]
}

SERVICE_MAP = {
    "instagram": ["INSTAGRAM_ACCOUNTS", "DEFAULT_INSTAGRAM_ACCOUNT"],
    "neo4j": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"],
    "gemini": ["GEMINI_API_KEY"],
    "user-agent": ["INSTAGRAM_USER_AGENT"],
    "all": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD",
            "INSTAGRAM_ACCOUNTS", "DEFAULT_INSTAGRAM_ACCOUNT", "INSTAGRAM_USER_AGENT", "GEMINI_API_KEY"]
}

MAX_RETRIES = 5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES_DIR = os.path.join(
    user_config_dir(appname="osintgraph", appauthor=False, ensure_exists=True),
    "templates"
)

os.makedirs(TEMPLATES_DIR, exist_ok=True)

SESSIONS_DIR = os.path.join(
    user_config_dir(appname="osintgraph", appauthor=False, ensure_exists=True),
    "sessions"
)

os.makedirs(SESSIONS_DIR, exist_ok=True)

DEBUG_LOGS_DIR = os.path.join(
    user_config_dir(appname="osintgraph", appauthor=False, ensure_exists=True),
    "debug_logs"
)

os.makedirs(DEBUG_LOGS_DIR, exist_ok=True)

TRACK_FILE = os.path.join(BASE_DIR, "templates_sync.json")
NEO4J_SYNC_QUEUE_FILE = os.path.join(os.path.dirname(TEMPLATES_DIR), "neo4j_sync_queue.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
