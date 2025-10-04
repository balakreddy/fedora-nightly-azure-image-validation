"""
Message schema definitions for fedora_cloud_tests Azure image test results.

This module defines fedora-messaging message classes for publishing
Azure image test results after LISA validation.
"""

from fedora_messaging import message

SCHEMA_URL = "http://fedoraproject.org/message-schema/v1"


class BasePublished(message.Message):
    """Base class for fedora_cloud_tests published messages."""

    topic = "org.fedoraproject.prod.fedora_cloud_tests.published.v1"

    @property
    def app_name(self):
        """Return the application name."""
        return "fedora_cloud_tests"


class AzureImageResultsPublished(BasePublished):
    """
    Published when an image is tested with LISA and results are available.
    """
    topic = "".join([BasePublished.topic, ".azure"])

    body_schema = {
        "id": f"{SCHEMA_URL}/{'.'.join([BasePublished.topic, 'azure'])}.json",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "Description": "Schema for Azure image test results published by fedora_cloud_tests against LISA",
        "type": "object",
        "properties": {
            "architecture": {"type": "string"},
            "compose_id": {"type": "string"},
            "image_id": {"type": "string"},
            "image_definition_name": {"type": "string"},
            "image_resource_id": {"type": "string"},
            "total_tests": {"type": "integer", "minimum": 0, "maximum": 750},
            "passed_tests": {"type": "integer", "minimum": 0, "maximum": 250},
            "failed_tests": {"type": "integer", "minimum": 0, "maximum": 250},
            "skipped_tests": {"type": "integer", "minimum": 0, "maximum": 250},
            "list_of_failed_tests": {
                "type": "array",
                "items": {"type": "string", "maxLength": 200},
                "maxItems": 250
            },
            "list_of_skipped_tests": {
                "type": "array", 
                "items": {"type": "string", "maxLength": 200},
                "maxItems": 250
            },
            "list_of_passed_tests": {
                "type": "array",
                "items": {"type": "string", "maxLength": 200},
                "maxItems": 250
            }
        },
        "required": [
            "architecture",
            "compose_id",
            "image_id",
            "image_definition_name",
            "image_resource_id",
            "total_tests",
            "passed_tests",
            "failed_tests",
            "skipped_tests",
            "list_of_failed_tests",
            "list_of_skipped_tests",
            "list_of_passed_tests",
        ],
    }

    @property
    def summary(self):
        return (
            f"{self.app_name} published Azure image test results for {self.body.get('image_id', 'unknown')}"
            f" on {self.body.get('architecture', 'unknown')}"
        )

    def __str__(self):
        """Return string representation of the message."""
        return f"AzureImageResultsPublished for {self.body.get('image_definition_name', 'unknown')}"
