from NHIOTMQTT import NHIOTMQTT
from NHIOTSub.executors import Executor
from NHIOTSub.models.payloads import CommandPayload
from NHIOTSub.models.responses import CommandResponse
from logging import Logger

class MQTTHandler:
    def __init__(self, client: NHIOTMQTT, executor: Executor,logger : Logger):
        self.client = client
        self.executor = executor
        self.logger = logger

    def handle(self, file_path: str):
        def on_message(topic, payload, **kwargs):
            try:
                cmd = CommandPayload.model_validate_json(payload.decode())
            except Exception as e:
                self.logger.error(f"Invalid payload: {e}")
                return

            self.logger.info(f"Executing dynamic target binary: {cmd.function}({cmd.parameters})")

            stdout, stderr = self.executor.run(
                file_path,
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