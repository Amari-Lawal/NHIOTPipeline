import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
candidates = [
    os.path.abspath(os.path.join(current_dir, "..", ".env")),
    os.path.abspath(os.path.join(current_dir, "..", "..", ".env")),
    ".env",
    "NHIOTSub/.env",
]
for path in candidates:
    if os.path.exists(path):
        load_dotenv(path)


class Envs:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    OWNER = os.getenv("OWNER")
    REPO = os.getenv("REPO")
    WORKFLOW_ID = os.getenv("WORKFLOW_ID")
    BRANCH = os.getenv("BRANCH")
    POLL_INTERVAL = os.getenv("POLL_INTERVAL", "10")
    SUBSCRIBER_ARCHITECTURE = os.getenv("SUBSCRIBER_ARCHITECTURE")
    ARTIFACT_NAME = os.getenv("ARTIFACT_NAME")
