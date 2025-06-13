"""Consumer for AzurePublishedV1 messages and LISA trigger."""

import asyncio
import logging
import os

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging.api import consume

from trigger_lisa import LisaRunner

REGION = 'westus2'
PRIVATE_KEY = '/path/to/private_key.pem'
SUBSCRIPTION_ID = 'your_subscription_id'

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

def has_matching_keys(azurepublished_properties, message):
    """Check if the received message properties match the AzurePublishedV1 schema."""

    logger.info("Comparing properties: %s with message"
                ": %s", azurepublished_properties, message)
    try:
        azurepublished_properties = set(azurepublished_properties.body_schema['properties'].keys())
        message_properties = set(message.body.keys())
        return azurepublished_properties == message_properties
    except Exception as e: # pylint: disable=broad-except
        logger.error("Invalid properties of the message received %s", str(e))
        return False


def get_community_gallery_image(message):
    """Extract community gallery image from the message."""

    logger.info("Extracting community gallery image from the message: %s", message.body)
    try:
        return message.body.get('image_resource_id', None)
    except AttributeError as e:
        logger.error("Failed to extract community gallery image from the message: %s", str(e))
        return None


def azure_published_callback(message):
    """Handle Azure published messages"""
    logger.info("Received message on topic: %s", message.body)

    if has_matching_keys(AzurePublishedV1, message):
        community_gallery_image = get_community_gallery_image(message)
        try:
            runner = LisaRunner(logger=logger)
            asyncio.run(runner.trigger_lisa(
                region=REGION, community_gallery_image=community_gallery_image,
                subscription=SUBSCRIPTION_ID, private_key=PRIVATE_KEY))
            logger.info("LISA trigger executed successfully.")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Failed to trigger LISA: %s", str(e))
    else:
        logger.warning("Message properties do not match AzurePublishedV1 schema. Skipping message.")


if __name__ == "__main__":
    logger.info("Starting AzurePublishedV1 consumer...")

    bindings = [{
        'exchange': 'amq.topic',
        'queue': 'azure_published_consumer',
        'routing_keys': ['org.fedoraproject.prod.fedora_image_uploader.published.v1.azure.eln.*'],
    }]
    logger.info("Bindings configured: %s", bindings)

    consume(azure_published_callback, bindings=bindings)
    logger.info("Consumer started successfully.")
