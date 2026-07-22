import hashlib
import io
from logging import Logger
import os
from typing import List, Optional
import zipfile

import requests

from NHIOTSub.models.dtos import Artifact
from NHIOTSub.config import Config


class ArtifactService:
    def __init__(self, logger: Logger):
        self.logger = logger

    def choose(self, artifacts: List[Artifact], target_name: str) -> Optional[Artifact]:
        return next((a for a in artifacts if a.name == target_name), None)

    def verify_checksum(self, binary_path: str, checksum_path: str) -> bool:
        if not os.path.exists(checksum_path):
            self.logger.info(f"No SHA-256 file found at '{checksum_path}' — proceeding.")
            return True

        with open(binary_path, "rb") as f:
            calculated_hash = hashlib.sha256(f.read()).hexdigest()

        with open(checksum_path, "r") as f:
            expected_hash = f.read().split()[0].strip()

        if calculated_hash.lower() == expected_hash.lower():
            self.logger.info(f"SHA-256 Integrity Verified! Hash: {calculated_hash[:16]}...")
            return True
        else:
            self.logger.error(f"CRITICAL: SHA-256 Checksum Mismatch! Expected: {expected_hash[:16]}..., Calculated: {calculated_hash[:16]}...")
            return False

    def download(self, artifact: Artifact) -> str:
        self.logger.info(f"Downloading {artifact.name}")

        response = requests.get(artifact.archive_download_url, headers=Config.GITHUB_HEADERS)
        response.raise_for_status()

        extract_path = f"./Executables/{artifact.name}"
        os.makedirs(extract_path, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(extract_path)

        binary_path = f"{extract_path}/{artifact.name}"
        checksum_path = f"{extract_path}/{artifact.name}.sha256"

        if not self.verify_checksum(binary_path, checksum_path):
            raise ValueError(f"SHA-256 checksum verification failed for binary '{binary_path}'!")

        return binary_path