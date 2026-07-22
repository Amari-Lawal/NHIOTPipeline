import os

from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
load_dotenv(env_path)


class Envs:
    ENDPOINT = os.getenv("ENDPOINT")
    CA_FILE = os.getenv("CA_FILE")
    CERT_FILE = os.getenv("CERT_FILE")
    PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE")
    TOPIC = os.getenv("TOPIC")
