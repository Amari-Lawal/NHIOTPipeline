import json
import sys
import threading
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics


def main():
    print("[PUBLISHER] Requesting remote IoT Subscriber to trigger GitHub Actions Version Rollback...")
    client = NHIOTMQTT()
    client.connect(verbose=False)

    event = threading.Event()
    received_data = {}

    def on_response(topic, payload, **kwargs):
        nonlocal received_data
        try:
            data = json.loads(payload.decode("utf-8"))
            if isinstance(data, dict) and data.get("function") == "trigger_revert":
                received_data = data
                event.set()
        except Exception as e:
            print(f"Error parsing response: {e}")

    client.subscribe(on_response, topic=Topics.RESPONSE_TOPIC, verbose=False)

    revert_payload = json.dumps({"command": "TRIGGER_REVERT"})
    client.publish(revert_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if event.wait(timeout=15):
        result = received_data.get("result", "UNKNOWN")
        file_path = received_data.get("file_path", "")
        print(f"\n[PUBLISHER SUCCESS] Subscriber CONFIRMED Rollback Result: '{result}' | Active Path: '{file_path}'!")
    else:
        print("\n[PUBLISHER TIMEOUT] No rollback confirmation received from subscriber within 15 seconds.")

    client.disconnect(verbose=False)


if __name__ == "__main__":
    main()
