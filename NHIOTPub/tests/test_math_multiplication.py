from NHIOTPub.NHUnitPub import BaseMQTTTest


class TestMultiplication(BaseMQTTTest):
    def test_multiply_cases(self):
        cases = [
            ([3, 4], "12"),
            ([8, 7], "56"),
        ]

        for params, expected in cases:
            with self.subTest(params=params):
                self.run_mqtt_test("multiply", params, expected)
