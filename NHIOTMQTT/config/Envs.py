import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path)


class Envs:
    ENDPOINT = os.getenv("ENDPOINT", "a3b83988gnh54t-ats.iot.eu-west-2.amazonaws.com")
    CA_FILE = os.getenv("CA_FILE", "")
    CERT_FILE = os.getenv("CERT_FILE", "")
    PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE", "")
    TOPIC = os.getenv("TOPIC", "nhiot/fleet/command")
    MQTT_BROKER = os.getenv("MQTT_BROKER", "")
    MQTT_HOST = os.getenv("MQTT_HOST", "")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    USE_LOCAL_BROKER = os.getenv("USE_LOCAL_BROKER", "false").lower() == "true"
