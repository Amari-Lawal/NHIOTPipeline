from logging import Logger
import uuid
from awscrt import mqtt
from awsiot import mqtt_connection_builder
from typing import Literal,Any
from concurrent.futures import Future
from NHIOTMQTT.config.Envs import Envs
class NHIOTMQTT:
    def __init__(self, logger :Logger = None):
        # === Configuration ===
        self.ENDPOINT = Envs.ENDPOINT
        self.CA_FILE = Envs.CA_FILE
        self.CERT_FILE = Envs.CERT_FILE
        self.PRIVATE_KEY_FILE = Envs.PRIVATE_KEY_FILE
        self.QOS = mqtt.QoS.AT_LEAST_ONCE
        self.logger = logger

        # Unique client ID
        self.client_id = f"python_v2_client_{uuid.uuid4()}"
        



    def connect(self,verbose=True) -> Future:
        """Create and connect MQTT client"""
        if verbose and self.logger: 
            self.logger.info("Connecting to AWS IoT Core...")
        # === Build MQTT connection ===
        self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=self.ENDPOINT,
            cert_filepath=self.CERT_FILE,
            pri_key_filepath=self.PRIVATE_KEY_FILE,
            ca_filepath=self.CA_FILE,
            client_id=self.client_id,
            clean_session=True,
            keep_alive_secs=30
        )
  
        connection_future = self.mqtt_connection.connect()
        connection_future.result()
        if verbose and self.logger:
            self.logger.info("Connected!")

    def subscribe(self,callback,topic="test/topic",verbose=True) -> Any:
        """Subscribe to a topic"""
        if self.mqtt_connection is None:
            raise RuntimeError("MQTT client not connected")
        if verbose and self.logger:
            self.logger.info(f"Subscribing to topic '{topic}'...")
        subscribe_future, _ = self.mqtt_connection.subscribe(
            topic=topic,
            qos=self.QOS,
            callback=callback
        )
        subscribe_result = subscribe_future.result()
        if verbose and self.logger: 
            self.logger.info(f"Subscribed to topic '{topic}'")
        return subscribe_result
 
    def unsubscribe(self,topic="test/topic",verbose=True) -> Any:
        """Unsubscribe from a topic"""
        if self.mqtt_connection is None:
            raise RuntimeError("MQTT client not connected")
        if verbose and self.logger:
            self.logger.info(f"Unsubscribing from topic '{topic}'...")
        unsubscribe_future, _ = self.mqtt_connection.unsubscribe(topic=topic)
        unsubscribe_result = unsubscribe_future.result()
        if verbose and self.logger:
            self.logger.info(f"Unsubscribed from topic '{topic}'")
        return unsubscribe_result

    def publish(self, message,topic="test/topic",verbose=True):
        """Publish a message to the topic"""
        if self.mqtt_connection is None:
            raise RuntimeError("MQTT client not connected")
        if verbose and self.logger:
            self.logger.info(f"[PUBLISHING] Topic: {topic} — Message: {message}")
        self.mqtt_connection.publish(topic=topic, payload=message, qos=self.QOS)
        if verbose and self.logger: 
            self.logger.info(f"Published message: {message}")

    def disconnect(self,verbose=True):
        """Disconnect the MQTT client"""
        if self.mqtt_connection:
            disconnection_future = self.mqtt_connection.disconnect()
            disconnection_future.result()
            if verbose and self.logger: 
                self.logger.info("Disconnected!")

