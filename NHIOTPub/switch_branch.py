import json
import sys
import threading

from NHIOTPub.NHUnitPub import BaseMQTTTest


class BranchSwitcher(BaseMQTTTest):
    def switch_and_wait(self, branch_name: str, timeout: int = 30) -> bool:
        print(f"[PUBLISHER] Requesting subscriber to switch to branch '{branch_name}' and pull build artifact...")
        success = self.set_subscriber_branch(branch_name)
        if success:
            print(f"[PUBLISHER] Subscriber CONFIRMED: Downloaded & loaded artifact for branch '{branch_name}'!")
            return True
        else:
            print(
                f"[PUBLISHER] WARNING: Subscriber did not send READY confirmation within {timeout}s (proceeding with tests)."
            )
            return False


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
