import json
from logging import Logger
from typing import Callable, Union

from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Envs, Topics
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.models.payloads import CommandPayload
from NHIOTSub.models.responses import CommandResponse


class MQTTHandler:
    def __init__(self, client: NHIOTMQTT, executor: Executor, logger: Logger):
        self.client = client
        self.executor = executor
        self.logger = logger
        self.branch_change_callback: Callable[[str], None] = None

    def set_branch_change_callback(self, callback: Callable[[str], None]) -> None:
        self.branch_change_callback = callback

    def _publish_response(self, payload_str: str) -> None:
        """Publishes response to clean enterprise topic and legacy topic for compatibility."""
        self.client.publish(payload_str, topic=Topics.RESPONSE_TOPIC)
        self.client.publish(payload_str, topic=Topics.LEGACY_RESPONSE_TOPIC)

    def handle(self, get_file_path: Union[str, Callable[[], str]]) -> Callable:
        def on_message(topic, payload, **kwargs):
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to decode MQTT JSON payload on topic '{topic}': {e}")
                return

            # 1. Branch Switch Command (Option 2 Handshake)
            if isinstance(data, dict) and data.get("command") == "SET_BRANCH":
                target_branch = data.get("branch")
                if target_branch:
                    self.logger.info(f"RECEIVED MQTT BRANCH SWITCH COMMAND -> Target Branch: '{target_branch}'")
                    Envs.BRANCH = target_branch

                    fetched_path = None
                    if callable(self.branch_change_callback):
                        fetched_path = self.branch_change_callback(target_branch)

                    res_data = {
                        "function": "set_branch",
                        "result": "READY",
                        "branch": Envs.BRANCH,
                        "file_path": fetched_path or "",
                        "error": ""
                    }
                    self._publish_response(json.dumps(res_data))
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
                self._publish_response(response.model_dump_json())
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
            self._publish_response(response.model_dump_json())

        return on_message