"""Consumer for AzurePublishedV1 messages and LISA trigger."""

import asyncio
import logging
import os
from datetime import datetime

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging.api import consume

from trigger_lisa import LisaRunner

REGION = "westus3"  # Default region in which the LISA tests will be run
PRIVATE_KEY = ""  # Path to the private key file for Azure authentication
SUBSCRIPTION_ID = ""  # Subscription ID for Azure
LOG_PATH = "/home/lisa_results" # Default path for LISA test logs


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

    def _get_image_definition_name(self, message):
        """ Get image definition name from the message body.

        Args:
            message (AzurePublishedV1): The message containing image details.

        Returns:
            str: The image definition name if found, else None.
            Eg: "Fedora-Cloud-Rawhide-x64", "Fedora-Cloud-41-x64", etc.
        """
        try:
            image_definition_name = message.body.get("image_definition_name")
            if not isinstance(image_definition_name, str):
                self.logger.error(
                    "image_definition_name is not a string: %s", image_definition_name
                )
                return None
            self.logger.info("Extracted image_definition_name: %s", image_definition_name)
            return image_definition_name
        except AttributeError:
            self.logger.error("Message body does not have 'image_definition_name' field.")
            return None

    def _generate_test_log_path(self, image_definition_name):
        """
        Generate test log path and run time name for the lisa tests.

        Args:
            image_definition_name (str): The name of the image definition.

        Returns:
            str: The generated log path.
            str: The run time name for the LISA tests.
        """

        os.makedirs(LOG_PATH, exist_ok=True)
        self.logger.info("Ensure log path exists: %s", LOG_PATH)

        # Generate log path and run name based on image name
        #  and date to store the results of the LISA tests
        try:
            log_path = os.path.join(LOG_PATH, image_definition_name)
            os.makedirs(log_path, exist_ok=True)
            self.logger.info("Generated log path: %s", log_path)
        except Exception as e: # pylint: disable=broad-except
            self.logger.error("Failed to generate log path: %s", str(e))
            log_path = None

        # Generate run name in the format MonthDay-Year-Time
        # Example: "July25-2023-14:30"
        try:
            current_date = datetime.now()
            month_day = current_date.strftime("%B%d")
            year = current_date.strftime("%Y")
            time_str = current_date.strftime("%H:%M")
            run_name = f"{month_day}-{year}-{time_str}"
            self.logger.info("Generated run name: %s", run_name)
        except Exception as e: # pylint: disable=broad-except
            self.logger.error("Failed to generate run name: %s", str(e))
            # Fallback to a default run name
            run_name = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.logger.info("Using fallback run name: %s", run_name)

        return log_path, run_name


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

            image_definition_name = self._get_image_definition_name(message)
            # Run tests only for fedora rawhide, 41 and 42,
            #  include your Fedora versions in SUPPORTED_FEDORA_VERSIONS
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
            log_path, run_name = self._generate_test_log_path(
                self._get_image_definition_name(message))
            self.logger.info("Test log path generated: %s", log_path)
            config_params = {
                "subscription": SUBSCRIPTION_ID,
                "private_key": PRIVATE_KEY,
                "log_path": log_path,
                "run_name": run_name,
            }
            runner = LisaRunner(logger=self.logger)
            asyncio.run(
                runner.trigger_lisa(
                    region=REGION,
                    community_gallery_image=community_gallery_image,
                    config=config_params
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
