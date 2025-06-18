"""Consumer for AzurePublishedV1 messages and LISA trigger."""

import asyncio
import logging
import os

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging.api import consume

from trigger_lisa import LisaRunner

REGION = 'westus3' # Default region in which the LISA tests will be run
PRIVATE_KEY = '' # Path to the private key file for Azure authentication
SUBSCRIPTION_ID = '' # Subscription ID for Azure

# Set up logger
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'consumer.log')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add handlers
if not logger.hasHandlers():
    logger.addHandler(file_handler)

logger.info("Logger initialized for AzurePublishedV1 consumer.")

def get_community_gallery_image(message):
    """Extract community gallery image from the message with safety checks."""

    logger.info("Extracting community gallery image from the message: %s", message.body)

    try:
        # Validate message.body is a dict
        if not isinstance(message.body, dict):
            logger.error("Message body is not a dictionary.")
            return None

        image_definition_name = message.body.get('image_definition_name')
        image_version_name = message.body.get('image_version_name')
        image_resource_id = message.body.get('image_resource_id')

        # Check for missing fields
        if not all([image_definition_name, image_version_name, image_resource_id]):
            logger.error("Missing required image fields in message body.")
            return None

        # Defensive split and validation
        parts = image_resource_id.split('/')
        if len(parts) < 3:
            logger.error("image_resource_id format is invalid: %s", image_resource_id)
            return None
        resource_id = parts[2]

        community_gallery_image = (
            f"{REGION}/{resource_id}/"
            f"{image_definition_name}/{image_version_name}"
        )
        logger.info("Constructed community gallery image: %s", community_gallery_image)
        return community_gallery_image

    except Exception as e: # pylint: disable=broad-except
        logger.error("Failed to extract image details from the message: %s", str(e))
        return None


def azure_published_callback(message):
    """Handle Azure published messages"""
    logger.info("Received message on topic: %s", message.topic)
    logger.info("Message %s", message.body)
    try:
        isinstance(message, AzurePublishedV1)
        logger.info("Message properties match AzurePublishedV1 schema.")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Message properties do not match AzurePublishedV1 schema: %s", str(e))

    community_gallery_image = get_community_gallery_image(message)

    try:
        if not community_gallery_image:
            logger.error("No community gallery image found in the message.")
            return
        runner = LisaRunner(logger=logger)
        asyncio.run(runner.trigger_lisa(
            region=REGION, community_gallery_image=community_gallery_image,
            subscription=SUBSCRIPTION_ID, private_key=PRIVATE_KEY))
        logger.info("LISA trigger executed successfully.")
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("Failed to trigger LISA: %s", str(e))


if __name__ == "__main__":
    logger.info("Starting AzurePublishedV1 consumer...")

    bindings = [{
        'exchange': 'amq.topic',
        'queue': 'azure_published_consumer',
        'routing_keys': ['org.fedoraproject.prod.fedora_image_uploader.published.v1.azure.*'],
    }]
    logger.info("Bindings configured: %s", bindings)

    consume(azure_published_callback, bindings=bindings)
    logger.info("Consumer started successfully.")
