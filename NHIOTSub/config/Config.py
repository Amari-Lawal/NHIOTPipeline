from NHIOTSub.config import Envs


class Config:
    BASE_URL = "https://api.github.com/repos/"
    GITHUB_HEADERS = {
        "Authorization": f"token {Envs.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
