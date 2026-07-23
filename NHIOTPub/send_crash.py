import json
import threading

from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics


def main():
    print("[PUBLISHER] Sending crash execution payload to topic 'nhiot/fleet/command'...")
    client = NHIOTMQTT()
    client.connect(verbose=False)

    event = threading.Event()
    received_error = None

    def on_response(topic, payload, **kwargs):
        nonlocal received_error
        try:
            data = json.loads(payload.decode("utf-8"))
            stderr = data.get("error") if data.get("error") is not None else data.get("stderr", "")
            stdout = data.get("result") if data.get("result") is not None else data.get("stdout", "")
            print(f"\n[PUBLISHER] Received Execution Response on '{topic}':")
            if stderr:
                print(f"  CRASH / FAILURE TRAPPED (stderr):\n{stderr.strip()}")
            else:
                print(f"  Output (stdout): {stdout.strip()}")
            received_error = stderr
            event.set()
        except Exception as e:
            print(f"Error parsing response: {e}")

    client.subscribe(on_response, topic=Topics.RESPONSE_TOPIC, verbose=False)

    crash_payload = json.dumps({"function": "crash", "parameters": []})
    client.publish(crash_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if event.wait(timeout=10):
        print("\n[PUBLISHER SUCCESS] Critical failure payload was trapped and returned over MQTT.")
    else:
        print("\n[PUBLISHER TIMEOUT] No response received within 10 seconds.")

    client.disconnect(verbose=False)


if __name__ == "__main__":
    main()
