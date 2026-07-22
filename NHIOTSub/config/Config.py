import os


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
