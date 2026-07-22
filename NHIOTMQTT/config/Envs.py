import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
if os.path.exists(env_path):
    load_dotenv(env_path)


class Envs:
    ENDPOINT = os.getenv("ENDPOINT")
    CA_FILE = os.getenv("CA_FILE")
    CERT_FILE = os.getenv("CERT_FILE")
    PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE")
    TOPIC = os.getenv("TOPIC")
    MQTT_BROKER = os.getenv("MQTT_BROKER")
    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_PORT = int(os.getenv("MQTT_PORT")) if os.getenv("MQTT_PORT") else 1883
    USE_LOCAL_BROKER = os.getenv("USE_LOCAL_BROKER", "").lower() == "true"
