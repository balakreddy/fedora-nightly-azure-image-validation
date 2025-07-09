"""Consumer for AzurePublishedV1 messages and LISA trigger."""

import asyncio
import logging
import os

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging.api import consume

from trigger_lisa import LisaRunner

REGION = "westus3"  # Default region in which the LISA tests will be run
PRIVATE_KEY = ""  # Path to the private key file for Azure authentication
SUBSCRIPTION_ID = ""  # Subscription ID for Azure


class AzurePublishedConsumer:
    """Consumer class for AzurePublishedV1 messages to trigger LISA tests."""

    # Supported Fedora versions for testing
    SUPPORTED_FEDORA_VERSIONS = [
        "Fedora-Cloud-Rawhide-x64",
        "Fedora-Cloud-41-x64",
        "Fedora-Cloud-41-Arm64",
        "Fedora-Cloud-Rawhide-Arm64",
        "Fedora-Cloud-42-x64",
        "Fedora-Cloud-42-Arm64",
        ]

    def __init__(self):
        # Configure the logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers to avoid duplicate logs
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create a new file handler for logging
        log_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "consumer.log"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - [%(name)s] - [%(levelname)s] - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add handler to the logger
        self.logger.addHandler(file_handler)

        # Also add console handler with same formatter
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def __call__(self, message):
        """Callback method to handle incoming messages."""
        self.logger.info("Received message: %s", message)
        self.azure_published_callback(message)

    def get_community_gallery_image(self, message):
        """Extract community gallery image from the messages."""
        self.logger.info(
            "Extracting community gallery image from the message: %s", message.body
        )
        try:
            # Validate message.body is a dict
            if not isinstance(message.body, dict):
                self.logger.error("Message body is not a dictionary.")
                return None

            image_definition_name = message.body.get("image_definition_name")
            # Run tests only for fedora rawhide, 41 and 42,
            # include your Fedora versions below
            if image_definition_name not in self.SUPPORTED_FEDORA_VERSIONS:
                self.logger.info(
                    "image_definition_name '%s' not in supported Fedora"
                    " versions, skipping.",
                    image_definition_name,
                )
                return None
            image_version_name = message.body.get("image_version_name")
            image_resource_id = message.body.get("image_resource_id")

            # Check for missing fields
            if not all([image_definition_name, image_version_name, image_resource_id]):
                self.logger.error("Missing required image fields in message body.")
                return None

            # Defensive split and validation
            parts = image_resource_id.split("/")
            if len(parts) < 3:
                self.logger.error(
                    "image_resource_id format is invalid: %s", image_resource_id
                )
                return None
            resource_id = parts[2]

            community_gallery_image = (
                f"{REGION}/{resource_id}/"
                f"{image_definition_name}/{image_version_name}"
            )
            self.logger.info(
                "Constructed community gallery image: %s", community_gallery_image
            )
            return community_gallery_image

        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(
                "Failed to extract image details from the message: %s", str(e)
            )
            return None

    def azure_published_callback(self, message):
        """Handle Azure published messages"""
        self.logger.info("Received message on topic: %s", message.topic)
        self.logger.info("Message %s", message.body)
        try:
            if isinstance(message, AzurePublishedV1):
                self.logger.info("Message properties match AzurePublishedV1 schema.")
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(
                "Message properties do not match AzurePublishedV1 schema: %s", str(e)
            )

        community_gallery_image = self.get_community_gallery_image(message)

        try:
            if not community_gallery_image:
                self.logger.error(
                    "Unsupported or No community gallery image found in the message."
                )
                return
            runner = LisaRunner(logger=self.logger)
            asyncio.run(
                runner.trigger_lisa(
                    region=REGION,
                    community_gallery_image=community_gallery_image,
                    subscription=SUBSCRIPTION_ID,
                    private_key=PRIVATE_KEY,
                )
            )
            self.logger.info("LISA trigger executed successfully.")
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception("Failed to trigger LISA: %s", str(e))


if __name__ == "__main__":
    # Create an instance of the consumer
    consumer = AzurePublishedConsumer()
    consumer.logger.info("Starting AzurePublishedV1 consumer...")

    bindings = [
        {
            "exchange": "amq.topic",
            "queue": "azure_published_consumer",
            "routing_keys": [
                "org.fedoraproject.prod.fedora_image_uploader.published.v1.azure.*"
            ],
        }
    ]
    consumer.logger.info("Bindings configured: %s", bindings)

    consume(consumer, bindings=bindings)
    consumer.logger.info("Consumer started successfully.")
