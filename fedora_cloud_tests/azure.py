"""
AMQP consumer that processes messages from fedora-image-uploader when it uploads
a new Cloud image to Azure.

This consumer is responsible for testing the new image via LISA and annotating the
image with the results.
"""

import asyncio
import logging
import os
from datetime import datetime

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging import config

from .trigger_lisa import LisaRunner

PRIVATE_KEY = ""  # Path to the private key file for Azure authentication
CUSTOM_LOG_PATH = True  # Flag to indicate if a custom log path should be used
CUSTOM_RUN_NAME = True  # Flag to indicate if a custom run name should be generated

_log = logging.getLogger(__name__)


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
        try:
            self.conf = config.conf["consumer_config"]["azure"]
        except KeyError:
            _log.error("The Azure consumer requires an 'azure' config section")
            raise

    def __call__(self, message):
        """Callback method to handle incoming messages."""
        _log.info("Received message: %s", message)
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
                _log.error(
                    "image_definition_name is not a string: %s", image_definition_name
                )
                return None
            _log.info("Extracted image_definition_name: %s", image_definition_name)
            return image_definition_name
        except AttributeError:
            _log.error("Message body does not have 'image_definition_name' field.")
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

        log_path, run_name = None, None

        # Generate custom log if CUSTOM_LOG_PATH is set to True
        if CUSTOM_LOG_PATH:
            try:
                base_log_path = os.path.expanduser("~/lisa_results")
                os.makedirs(base_log_path, exist_ok=True)
                _log.info("Base log path created: %s", base_log_path)

                # Create image-specific log directory
                log_path = os.path.join(base_log_path, image_definition_name)
                os.makedirs(log_path, exist_ok=True)
                _log.info("Log path created: %s", log_path)
            except Exception as e: # pylint: disable=broad-except
                _log.error("Failed to create log path: %s", str(e))
                log_path = None
        else:
            _log.info("Using default log path")

        # Generate custom run name if CUSTOM_RUN_NAME is set to True
        if CUSTOM_RUN_NAME:
            try:
                current_date = datetime.now()
                month_day = current_date.strftime("%B%d")
                year = current_date.strftime("%Y")
                time_str = current_date.strftime("%H%M")
                run_name = f"{month_day}-{year}-{time_str}"
                _log.info("Run name generated: %s", run_name)
            except Exception as e:  # pylint: disable=broad-except
                _log.error("Failed to generate run name: %s", str(e))
                run_name = None
        else:
            _log.info("Using default run name")

        return log_path, run_name

    def get_community_gallery_image(self, message):
        """Extract community gallery image from the messages."""
        _log.info(
            "Extracting community gallery image from the message: %s", message.body
        )
        try:
            # Validate message.body is a dict
            if not isinstance(message.body, dict):
                _log.error("Message body is not a dictionary.")
                return None

            image_definition_name = self._get_image_definition_name(message)
            # Run tests only for fedora rawhide, 41 and 42,
            #  include your Fedora versions in SUPPORTED_FEDORA_VERSIONS
            if image_definition_name not in self.SUPPORTED_FEDORA_VERSIONS:
                _log.info(
                    "image_definition_name '%s' not in supported Fedora"
                    " versions, skipping.",
                    image_definition_name,
                )
                return None
            image_version_name = message.body.get("image_version_name")
            image_resource_id = message.body.get("image_resource_id")

            # Check for missing fields
            if not all([image_definition_name, image_version_name, image_resource_id]):
                _log.error("Missing required image fields in message body.")
                return None

            # Defensive split and validation
            parts = image_resource_id.split("/")
            if len(parts) < 3:
                _log.error(
                    "image_resource_id format is invalid: %s", image_resource_id
                )
                return None
            resource_id = parts[2]

            community_gallery_image = (
                f"{self.conf['region']}/{resource_id}/"
                f"{image_definition_name}/{image_version_name}"
            )
            _log.info(
                "Constructed community gallery image: %s", community_gallery_image
            )
            return community_gallery_image

        except Exception as e:  # pylint: disable=broad-except
            _log.error(
                "Failed to extract image details from the message: %s", str(e)
            )
            return None

    def azure_published_callback(self, message):
        """Handle Azure published messages"""
        _log.info("Received message on topic: %s", message.topic)
        _log.info("Message %s", message.body)
        try:
            if isinstance(message, AzurePublishedV1):
                _log.info("Message properties match AzurePublishedV1 schema.")
        except Exception as e:  # pylint: disable=broad-except
            _log.error(
                "Message properties do not match AzurePublishedV1 schema: %s", str(e)
            )

        community_gallery_image = self.get_community_gallery_image(message)

        try:
            if not community_gallery_image:
                _log.error(
                    "Unsupported or No community gallery image found in the message."
                )
                return
            log_path, run_name = self._generate_test_log_path(
                self._get_image_definition_name(message))
            _log.info("Test log path generated: %s", log_path)
            config_params = {
                "subscription": self.conf["subscription_id"],
                "private_key": PRIVATE_KEY,
                "log_path": log_path,
                "run_name": run_name,
            }
            runner = LisaRunner()
            asyncio.run(
                runner.trigger_lisa(
                    region=self.conf["region"],
                    community_gallery_image=community_gallery_image,
                    config=config_params
                )
            )
            _log.info("LISA trigger executed successfully.")
        except Exception as e:  # pylint: disable=broad-except
            _log.exception("Failed to trigger LISA: %s", str(e))

