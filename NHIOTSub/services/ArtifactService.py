import hashlib
import io
import os
import struct
import zipfile
from logging import Logger
from typing import List, Optional

import requests

from NHIOTSub.config import Config, Envs
from NHIOTSub.models.dtos import Artifact


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
            self.logger.error(
                f"CRITICAL: SHA-256 Checksum Mismatch! Expected: {expected_hash[:16]}..., Calculated: {calculated_hash[:16]}..."
            )
            return False

    def verify_elf_header(self, binary_path: str, expected_arch: str) -> bool:
        """Inspects Linux ELF magic bytes, 64-bit class, and machine architecture (x86_64 vs aarch64)."""
        if not os.path.exists(binary_path):
            self.logger.error(f"ELF VERIFICATION FAILED: Binary file '{binary_path}' does not exist.")
            return False

        with open(binary_path, "rb") as f:
            header = f.read(64)

        if len(header) < 52:
            self.logger.error(
                f"ELF VERIFICATION FAILED: Binary file '{binary_path}' is truncated ({len(header)} bytes)."
            )
            return False

        # 1. Magic bytes: \x7fELF
        if header[:4] != b"\x7fELF":
            self.logger.error(
                f"ELF VERIFICATION FAILED: Invalid magic bytes {header[:4]} in '{binary_path}' (not a Linux ELF binary)."
            )
            return False

        # 2. ELF Class: 2 = 64-bit
        elf_class = header[4]
        if elf_class != 2:
            self.logger.error(f"ELF VERIFICATION FAILED: Binary is not 64-bit ELF (class {elf_class}).")
            return False

        # 3. Machine Architecture e_machine at offset 18 (2 bytes, little-endian)
        e_machine = struct.unpack("<H", header[18:20])[0]

        # 0x3E (62) = x86_64, 0xB7 (183) = aarch64
        if expected_arch == "x86_64" and e_machine != 0x3E:
            self.logger.error(
                f"ELF VERIFICATION FAILED: Expected x86_64 (e_machine 0x3E), but binary has e_machine {hex(e_machine)}."
            )
            return False
        elif expected_arch in ("aarch64", "arm64") and e_machine != 0xB7:
            self.logger.error(
                f"ELF VERIFICATION FAILED: Expected aarch64 (e_machine 0xB7), but binary has e_machine {hex(e_machine)}."
            )
            return False

        arch_name = "x86_64" if e_machine == 0x3E else "aarch64" if e_machine == 0xB7 else hex(e_machine)
        self.logger.info(
            f"ELF Header Integrity Verified! Format: 64-bit ELF, Target Arch: {arch_name} ({hex(e_machine)})"
        )
        return True

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

        # 1. SHA-256 Checksum Verification
        if not self.verify_checksum(binary_path, checksum_path):
            raise ValueError(f"SHA-256 checksum verification failed for binary '{binary_path}'!")

        # 2. ELF Header & Machine Architecture Integrity Verification
        if not self.verify_elf_header(binary_path, Envs.SUBSCRIBER_ARCHITECTURE):
            raise ValueError(f"ELF header integrity verification failed for binary '{binary_path}'!")

        return binary_path
