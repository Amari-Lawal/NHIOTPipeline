import json
import sys
import threading

from NHIOTPub.NHUnitPub import BaseMQTTTest


class BranchSwitcher(BaseMQTTTest):
    def switch_and_wait(self, branch_name: str, timeout: int = 30) -> bool:
        event = threading.Event()
        success = False

        def callback(topic, payload):
            nonlocal success
            try:
                msg = json.loads(payload.decode("utf-8"))
                if msg.get("function") == "set_branch" and msg.get("result") == "READY":
                    print(
                        f"[PUBLISHER] Subscriber CONFIRMED: Downloaded & loaded artifact for branch '{msg.get('branch')}'!"
                    )
                    success = True
                    event.set()
            except Exception as e:
                print(f"[PUBLISHER] Error parsing response: {e}")

        self.client.subscribe(callback, topic=self.subscribe_topic, verbose=False)

        try:
            print(f"[PUBLISHER] Requesting subscriber to switch to branch '{branch_name}' and pull build artifact...")
            self.set_subscriber_branch(branch_name)

            if event.wait(timeout):
                return success
            else:
                print(
                    f"[PUBLISHER] WARNING: Subscriber did not send READY confirmation within {timeout}s (proceeding with tests)."
                )
                return False
        finally:
            try:
                self.client.unsubscribe(self.subscribe_topic, verbose=False)
            except Exception:
                pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m NHIOTPub.switch_branch <branch_name> (e.g. dev, main, staging, test)")
        sys.exit(1)

    branch = sys.argv[1]
    switcher = BranchSwitcher()
    switcher.setUpClass()
    try:
        switcher.switch_and_wait(branch, timeout=20)
    finally:
        switcher.tearDownClass()


if __name__ == "__main__":
    main()
