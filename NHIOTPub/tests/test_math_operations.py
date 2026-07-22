from NHIOTPub.NHUnitPub import BaseMQTTTest


class TestMathOperations(BaseMQTTTest):
    def test_basic_operations(self):
        cases = [
            ("add", [1, 2], "3"),
            ("minus", [5, 2], "3"),
        ]

        for fn, params, expected in cases:
            with self.subTest(function=fn, params=params):
                self.run_mqtt_test(fn, params, expected)
