import os
import subprocess
from typing import Any, List


class Executor:
    def run(self, file_path: str, function: str, parameters: List[Any]):
        os.chmod(file_path, 0o755)

        result = subprocess.run(
            [file_path, function] + list(map(str, parameters)),
            capture_output=True,
            text=True,
        )

        stdout = result.stdout
        stderr = result.stderr

        if result.returncode != 0 and not stderr:
            stderr = f"Process terminated abnormally with exit code {result.returncode} (Signal/Crash trapped by isolation boundary)."

        return stdout, stderr
