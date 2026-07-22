import json
from logging import Logger
from typing import Callable, Optional
from NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Envs
from NHIOTSub.executors import Executor
from NHIOTSub.models.payloads import CommandPayload
from NHIOTSub.models.responses import CommandResponse


class MQTTHandler:
    def __init__(self, client: NHIOTMQTT, executor: Executor, logger: Logger):
        self.client = client
        self.executor = executor
        self.logger = logger
        self.on_branch_changed: Optional[Callable[[str], Optional[str]]] = None

    def set_branch_change_callback(self, callback: Callable[[str], Optional[str]]):
        """Register a callback to notify subscriber when branch is updated via MQTT."""
        self.on_branch_changed = callback

    def handle(self, get_file_path: Callable[[], Optional[str]]):
        def on_message(topic, payload, **kwargs):
            try:
                raw_str = payload.decode("utf-8")
                data = json.loads(raw_str)
            except Exception as e:
                self.logger.error(f"Invalid JSON payload: {e}")
                return

            # 1. Check for Branch Switch Commands
            cmd_name = str(data.get("command") or data.get("function") or "").lower()
            target_branch = data.get("branch") or data.get("target_branch")

            if not target_branch and data.get("parameters") and isinstance(data["parameters"], list) and len(data["parameters"]) > 0:
                if cmd_name in ("set_branch", "setbranch", "change_branch", "switch_branch"):
                    target_branch = str(data["parameters"][0])

            if cmd_name in ("set_branch", "setbranch", "change_branch", "switch_branch") or data.get("command") == "SET_BRANCH":
                if target_branch:
                    old_branch = Envs.BRANCH
                    Envs.BRANCH = str(target_branch)
                    self.logger.info(f"MQTT CONTROL MSG: Branch switch requested via MQTT! '{old_branch}' -> '{Envs.BRANCH}'")
                    
                    fetched_path = None
                    if self.on_branch_changed:
                        fetched_path = self.on_branch_changed(Envs.BRANCH)
                        
                    res_data = {
                        "function": "set_branch",
                        "result": "READY",
                        "branch": Envs.BRANCH,
                        "file_path": fetched_path or "",
                        "error": ""
                    }
                    self.client.publish(json.dumps(res_data), topic="machineA/recv")
                    return

            # 2. Target Binary Execution Command
            try:
                cmd = CommandPayload.model_validate(data)
            except Exception as e:
                self.logger.error(f"Invalid command payload format: {e}")
                return

            current_file_path = get_file_path() if callable(get_file_path) else get_file_path

            if not current_file_path:
                self.logger.warning(f"Received function command '{cmd.function}', but no target binary has been downloaded yet for branch '{Envs.BRANCH}'.")
                response = CommandResponse.from_stdout(stdout="", stderr=f"No binary available yet for branch '{Envs.BRANCH}'")
                self.client.publish(response.model_dump_json(), topic="machineA/recv")
                return

            self.logger.info(f"Executing dynamic target binary: {cmd.function}({cmd.parameters})")

            stdout, stderr = self.executor.run(
                current_file_path,
                cmd.function,
                cmd.parameters
            )

            if stderr:
                self.logger.error(f"Isolated process exited with crash standard error:\n{stderr.strip()}")
            else:
                self.logger.info(f"Isolated process execution completed successfully. stdout: {stdout.strip()}")

            response = CommandResponse.from_stdout(stdout=stdout, stderr=stderr)
            self.client.publish(response.model_dump_json(), topic="machineA/recv")

        return on_message