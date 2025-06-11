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


def azure_published_callback(message):
    """Handle Azure published messages"""
    logger.info("Received message on topic: %s", message.topic)

    if message.topic == AzurePublishedV1.topic:
        body = message.body
        headers = message.headers

        logger.debug("Message body: %s", body)
        logger.debug("Message headers: %s", headers)

        required_headers = [
            "fedora_messaging_schema",
            "fedora_messaging_schema_package",
            "sent-at",
        ]
        for header in required_headers:
            if header not in headers:
                logger.error("Missing required header: %s", header)
                raise KeyError(f"Missing required header: {header}")

        required_body_fields = [
            "architecture",
            "compose_id",
            "image_definition_name",
            "image_resource_id",
            "image_version_name",
            "release",
        ]
        for field in required_body_fields:
            if field not in body:
                logger.error("Missing required body field: %s", field)
                raise KeyError(f"Missing required body field: {field}")

        community_gallery_image = body["image_resource_id"]
        logger.info("Image architecture: %s", body["architecture"])
        logger.info("Community Gallery Image ID: %s", community_gallery_image)

        try:
            runner = LisaRunner(logger=logger)
            asyncio.run(runner.trigger_lisa(
                region=REGION, community_gallery_image=community_gallery_image,
                subscription=SUBSCRIPTION_ID, private_key=PRIVATE_KEY))
            logger.info("LISA trigger executed successfully.")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Failed to trigger LISA: %s", str(e))
    else:
        logger.warning("Ignoring message %s with unrecognized topic: %s", message, message.topic)


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
