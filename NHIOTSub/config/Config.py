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


class _ConfigMeta(type):
    @property
    def GITHUB_HEADERS(cls) -> dict:
        token = os.getenv("GITHUB_TOKEN", "")
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }


class Config(metaclass=_ConfigMeta):
    BASE_URL = "https://api.github.com/repos/"
