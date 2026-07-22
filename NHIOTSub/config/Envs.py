import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path)


class Envs:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    OWNER = os.getenv("OWNER")
    REPO = os.getenv("REPO")
    WORKFLOW_ID = os.getenv("WORKFLOW_ID")
    BRANCH = os.getenv("BRANCH")
    POLL_INTERVAL = os.getenv("POLL_INTERVAL", "10")
    SUBSCRIBER_ARCHITECTURE = os.getenv("SUBSCRIBER_ARCHITECTURE")
    ARTIFACT_NAME = os.getenv("ARTIFACT_NAME")
