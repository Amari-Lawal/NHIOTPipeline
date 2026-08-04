import unittest
from unittest.mock import MagicMock, patch

from NHIOTSub.models.dtos import Artifact, WorkflowRun
from NHIOTSub.subscriber.NHIOTSubscriber import NHIOTSubscriber


class TestSubscriberRollback(unittest.TestCase):
    def setUp(self):
        self.github = MagicMock()
        self.artifacts = MagicMock()
        self.executor = MagicMock()
        self.mqtt_client = MagicMock()
        self.mqtt_handler = MagicMock()
        self.logger = MagicMock()

        self.subscriber = NHIOTSubscriber(
            github=self.github,
            artifacts=self.artifacts,
            executor=self.executor,
            mqtt_client=self.mqtt_client,
            mqtt_handler=self.mqtt_handler,
            logger=self.logger,
        )

    def test_failed_build_triggers_immediate_rollback(self):
        """Test that a run with no matching artifact sets last_processed_run_id and triggers rollback immediately."""
        failed_run = WorkflowRun(
            id=30948864830,
            name="CI Build",
            head_branch="main",
            status="completed",
            conclusion="failure",
            head_sha="3c57ef6b9b7220c870039924c2a68e4f617242bd",
        )
        self.github.get_latest_run.return_value = failed_run
        self.github.get_artifacts.return_value = []
        self.artifacts.choose.return_value = None

        with patch.object(self.subscriber, "revert_to_previous_github_build") as mock_revert:
            mock_revert.return_value = "/tmp/reverted_binary"
            result = self.subscriber.fetch_artifact_for_branch("main")

            self.assertEqual(self.subscriber.last_processed_run_id, 30948864830)
            mock_revert.assert_called_once_with(30948864830, "main")
            self.assertEqual(result, "/tmp/reverted_binary")

    def test_revert_to_previous_github_build_preserves_failed_run_id(self):
        """Test that reverting to a previous build preserves the failed run ID to avoid infinite re-polling."""
        prev_run = WorkflowRun(
            id=30948860000,
            name="CI Build",
            head_branch="main",
            status="completed",
            conclusion="success",
            head_sha="1111111111111111111111111111111111111111",
        )
        dummy_artifact = Artifact(
            id=123,
            name="hello_x86_64",
            archive_download_url="http://example.com",
            expired=False,
        )

        self.github.get_recent_successful_runs.return_value = [prev_run]
        self.github.get_artifacts.return_value = [dummy_artifact]
        self.artifacts.choose.return_value = dummy_artifact
        self.artifacts.download.return_value = "/tmp/prev_binary"
        self.subscriber.run_unit_tests = MagicMock(return_value=True)

        res = self.subscriber.revert_to_previous_github_build(30948864830, "main")

        self.assertEqual(res, "/tmp/prev_binary")
        self.assertEqual(self.subscriber.current_file_path, "/tmp/prev_binary")
        self.assertEqual(self.subscriber.last_processed_run_id, 30948864830)


if __name__ == "__main__":
    unittest.main()
