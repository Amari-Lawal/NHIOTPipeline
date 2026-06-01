import threading
import json
import threading
import unittest
from NHIOTMQTT import NHIOTMQTT


class BaseMQTTTest(unittest.TestCase):
    publish_topic = "machineB/recv"
    subscribe_topic = "machineA/recv"
    timeout = 5

    @classmethod
    def setUpClass(cls):
        cls.client = NHIOTMQTT()
        cls.client.connect(verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.disconnect(verbose=False)

    def _make_callback(self, event, expected_result, parameters, expected_function):
        def callback(topic, payload):
            try:
                result_json = json.loads(payload.decode("utf-8"))
                error = result_json.get("error", "")
                device_function = result_json.get("function", "unknown")

                if device_function != expected_function:
                    # Ignore duplicate/stray messages from previous runs or tests
                    return

                if error:
                    raise AssertionError(f"[{device_function}({parameters})] FAILED — {error}")

                result = result_json.get("result", "")
                if str(result) != str(expected_result):
                    # Ignore duplicate/stray messages from previous runs of the same function
                    return
                
                print(f"[{device_function}({parameters})] PASSED — result: {result}")
                self._callback_exception = None
                event.set()
            except Exception as e:
                self._callback_exception = e
                event.set()
        return callback

    def run_mqtt_test(self, function_name, parameters, expected_result):
        event = threading.Event()
        self._callback_exception = None

        callback = self._make_callback(event, expected_result, parameters, function_name)

        self.client.subscribe(
            callback,
            topic=self.subscribe_topic,
            verbose=False
        )

        try:
            self.client.publish(
                json.dumps({
                    "function": function_name,
                    "parameters": parameters
                }),
                topic=self.publish_topic,
                verbose=False
            )

            # Wait for the event to be set
            self.assertTrue(
                event.wait(self.timeout),
                f"No MQTT response within {self.timeout} seconds"
            )

            # Propagate background callback exceptions if they occurred
            if self._callback_exception is not None:
                raise self._callback_exception
        finally:
            try:
                self.client.unsubscribe(self.subscribe_topic, verbose=False)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
