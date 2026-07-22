from pydantic import BaseModel


class Artifact(BaseModel):
    id: int
    name: str
    archive_download_url: str
    expired: bool
