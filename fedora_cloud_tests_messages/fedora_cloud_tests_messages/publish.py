"""
Message schema definitions for fedora_cloud_tests Azure image test results.

This module defines fedora-messaging message classes for publishing
Azure image test results after LISA validation.
"""

from fedora_messaging import message

SCHEMA_URL = "http://fedoraproject.org/message-schema/v1"


class BaseTestResults(message.Message):
    """Base class for fedora_cloud_tests published messages."""

    topic = "fedora_cloud_tests.test_results.v1"

    @property
    def app_name(self):
        """Return the application name."""
        return "fedora_cloud_tests"


class AzureTestResults(BaseTestResults):
    """
    Published when an image is tested with LISA and results are available.
    """
    topic = ".".join([BaseTestResults.topic, "azure"])

    body_schema = {
        "id": f"{SCHEMA_URL}/{topic}.json",
        "$schema": "http://json-schema.org/draft-07/schema#",

        # Using $defs and $ref for reusability of test results(passed, failed, skipped)
        "$defs": {
            "testResults": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of tests in this category",
                    },
                    "tests": {
                        "type": "object",
                        "patternProperties": {
                            ".*": {
                                "type": "string",
                                "description": "Name of the test"
                            }
                        },
                        "additionalProperties": False,
                        "description": "Explanation for the test result (e.g., reason for skip or failure)"
                    }
                },
                "required": ["count", "tests"],
                "additionalProperties": False
            }
        },
        "description": "Schema for Azure image test results published by fedora_cloud_tests against LISA",
        "type": "object",
        "properties": {
            "architecture": {"type": "string"},
            "compose_id": {"type": "string"},
            "image_id": {"type": "string"},
            "image_resource_id": {"type": "string"},
            # References to reusable test results schema
            "failed_tests": {"$ref": "#/$defs/testResults"},
            "skipped_tests": {"$ref": "#/$defs/testResults"},
            "passed_tests": {"$ref": "#/$defs/testResults"}
        },
        "required": [
            "architecture",
            "compose_id",
            "image_id",
            "image_resource_id",
            "failed_tests",
            "skipped_tests",
            "passed_tests",
        ],
    }

    @property
    def summary(self):
        return (
            f"Azure Cloud image {self.body['image_id']} tested successfully"
            f" ({self.body['passed_tests']['count']} tests passed, "
            f"{self.body['failed_tests']['count']} tests failed, "
            f"{self.body['skipped_tests']['count']} tests skipped)"
        )

    def __str__(self):
        """Return string representation of the message."""
        return f"AzureImageTestResults for {self.body.get('image_id')}"
