import threading
import json
import time
import unittest
from NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics


class BaseMQTTTest(unittest.TestCase):
    publish_topic = Topics.COMMAND_TOPIC
    subscribe_topic = Topics.RESPONSE_TOPIC
    timeout = 10

    @classmethod
    def setUpClass(cls):
        cls.client = NHIOTMQTT()
        cls.client.connect(verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.disconnect(verbose=False)

    def set_subscriber_branch(self, target_branch: str) -> bool:
        """Publishes a SET_BRANCH control payload and waits for subscriber READY response."""
        event = threading.Event()
        result_holder = {"ready": False}

        def on_ready_callback(topic, payload):
            try:
                msg = json.loads(payload.decode("utf-8"))
                if isinstance(msg, dict) and msg.get("function") == "set_branch" and msg.get("result") == "READY":
                    result_holder["ready"] = True
                    event.set()
            except Exception:
                pass

        self.client.subscribe(on_ready_callback, topic=self.subscribe_topic, verbose=False)
        
        switch_payload = json.dumps({"command": "SET_BRANCH", "branch": target_branch})
        self.client.publish(switch_payload, topic=self.publish_topic, verbose=False)

        received = event.wait(timeout=15)
        return received and result_holder["ready"]

    def _make_callback(self, event, expected_result, parameters, expected_function):
        def callback(topic, payload):
            try:
                result_json = json.loads(payload.decode("utf-8"))
                
                # Filter out set_branch handshakes
                if isinstance(result_json, dict) and result_json.get("function") == "set_branch":
                    return

                if expected_function is not None:
                    actual_fn = result_json.get("function")
                    if actual_fn != expected_function:
                        return

                actual_stdout = result_json.get("stdout", "").strip()

                if expected_result is not None:
                    actual_clean = actual_stdout.replace(" ", "")
                    exp_clean = expected_result.replace(" ", "")
                    if exp_clean != actual_clean:
                        return

                self.received_result = actual_stdout
                event.set()
            except Exception as e:
                self.error = str(e)
                event.set()

        return callback

    def send_command(self, function: str, parameters: list, expected_result: str = None):
        self.received_result = None
        self.error = None
        event = threading.Event()

        cb = self._make_callback(event, expected_result, parameters, expected_function=function)
        
        self.client.subscribe(cb, topic=self.subscribe_topic, verbose=False)

        payload = json.dumps({"function": function, "parameters": parameters})
        self.client.publish(payload, topic=self.publish_topic, verbose=False)

        received = event.wait(timeout=self.timeout)

        self.assertTrue(
            received,
            f"Timed out waiting for response for '{function}({parameters})' on '{self.subscribe_topic}'"
        )
        if self.error:
            self.fail(f"Error during execution of '{function}': {self.error}")

        if expected_result is not None:
            self.assertEqual(
                self.received_result.replace(" ", ""),
                expected_result.replace(" ", ""),
                f"Expected '{expected_result}', got '{self.received_result}'"
            )

        return self.received_result
