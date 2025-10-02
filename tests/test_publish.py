"""
Tests for fedora_cloud_tests.publish module schema validation.

This module tests the message schema definitions and validation
for Azure image test results publishing without requiring full
fedora-messaging registration.
"""

import pytest
import jsonschema
from fedora_cloud_tests.publish import BasePublished, AzureImageResultsPublished


class TestBasePublished:
    """Test cases for BasePublished base class."""

    def test_topic_format(self):
        """Test that topic follows expected format."""
        expected_topic = "org.fedoraproject.prod.fedora_cloud_tests.published.v1"
        assert BasePublished.topic == expected_topic

    def test_app_name_property(self):
        """Test that app_name property returns correct value."""
        # Test the class property directly - it's a property that returns a string
        class_instance = BasePublished.__new__(BasePublished)
        assert class_instance.app_name == "fedora_cloud_tests"


class TestAzureImageResultsPublished:
    """Test cases for AzureImageResultsPublished message class."""

    def test_topic_inheritance(self):
        """Test that Azure message inherits and extends base topic."""
        expected_topic = "org.fedoraproject.prod.fedora_cloud_tests.published.v1.azure"
        assert AzureImageResultsPublished.topic == expected_topic

    def test_schema_validation_missing_required_fields(self):
        """Test schema validation fails with missing required fields."""
        incomplete_body = {
            "architecture": "x86_64",
            # Missing other required fields
        }

        schema = AzureImageResultsPublished.body_schema

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(incomplete_body, schema)

    def test_schema_validation_wrong_data_types(self):
        """Test schema validation fails with wrong data types."""
        invalid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-Rawhide-20250922.n.0",
            "image_id": "Fedora-Cloud-Rawhide-x64",
            "image_definition_name": "Fedora-Cloud-Rawhide-x64",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery",
            "total_tests": "not_a_number",  # Should be integer
            "passed_tests": 8,
            "failed_tests": 1,
            "skipped_tests": 1,
            "list_of_failed_tests": ["test_module.test_failed_case"],
            "list_of_skipped_tests": ["test_module.test_skipped_case"],
            "list_of_passed_tests": ["test_module.test_case_1"]
        }

        schema = AzureImageResultsPublished.body_schema

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_body, schema)

    def test_schema_validation_invalid_array_items(self):
        """Test schema validation fails with invalid array items."""
        invalid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-Rawhide-20250922.n.0",
            "image_id": "Fedora-Cloud-Rawhide-x64",
            "image_definition_name": "Fedora-Cloud-Rawhide-x64",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery",
            "total_tests": 10,
            "passed_tests": 8,
            "failed_tests": 1,
            "skipped_tests": 1,
            "list_of_failed_tests": [123],  # Should be strings, not numbers
            "list_of_skipped_tests": ["test_module.test_skipped_case"],
            "list_of_passed_tests": ["test_module.test_case_1"]
        }

        schema = AzureImageResultsPublished.body_schema

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_body, schema)

    def test_schema_properties_types(self):
        """Test that schema properties have correct types."""
        schema = AzureImageResultsPublished.body_schema
        properties = schema["properties"]

        # Test string fields
        string_fields = ["architecture", "compose_id", "image_id", "image_definition_name", "image_resource_id"]
        for field in string_fields:
            assert properties[field]["type"] == "string"

        # Test integer fields
        integer_fields = ["total_tests", "passed_tests", "failed_tests", "skipped_tests"]
        for field in integer_fields:
            assert properties[field]["type"] == "integer"

        # Test array fields
        array_fields = ["list_of_failed_tests", "list_of_skipped_tests", "list_of_passed_tests"]
        for field in array_fields:
            assert properties[field]["type"] == "array"
            assert properties[field]["items"]["type"] == "string"

    def test_empty_test_lists(self):
        """Test schema validation with empty test lists."""
        body_with_empty_lists = {
            "architecture": "aarch64",
            "compose_id": "Fedora-41-20250922.n.0",
            "image_id": "Fedora-Cloud-41-Arm64",
            "image_definition_name": "Fedora-Cloud-41-Arm64",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery",
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": []
        }

        schema = AzureImageResultsPublished.body_schema

        # This should not raise any validation errors
        jsonschema.validate(body_with_empty_lists, schema)

    def test_schema_url_generation(self):
        """Test that schema URL is generated correctly."""
        schema = AzureImageResultsPublished.body_schema
        expected_url = "http://fedoraproject.org/message-schema/v1/org.fedoraproject.prod.fedora_cloud_tests.published.v1.azure.json"
        assert schema["id"] == expected_url

    def test_schema_metadata(self):
        """Test that schema contains correct metadata."""
        schema = AzureImageResultsPublished.body_schema

        # Check required metadata fields
        assert "$schema" in schema
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert "Description" in schema
        assert "Azure" in schema["Description"]


# pylint: disable=too-few-public-methods
class TestSchemaIntegration:
    """Integration tests for schema functionality."""

    def test_create_valid_message_body_example(self):
        """Example of how to create a properly formatted message body."""
        # Step 1: Define your test results
        failed_tests = ["test_network_connectivity", "test_disk_performance"]
        skipped_tests = ["test_gpu_support"]
        passed_tests = [
            "test_system_boot",
            "test_ssh_connection",
            "test_package_manager",
            "test_basic_commands",
            "test_file_system"
        ]

        # Step 2: Calculate totals (ensure mathematical consistency)
        total_failed = len(failed_tests)
        total_skipped = len(skipped_tests)
        total_passed = len(passed_tests)
        total_tests = total_failed + total_skipped + total_passed

        # Step 3: Create the message body with all required fields
        valid_message_body = {
            # Image identification fields
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/fedora-images/providers/Microsoft.Compute/galleries/fedora-gallery/images/fedora-cloud-41",

            # Test count fields (must match array lengths)
            "total_tests": total_tests,
            "passed_tests": total_passed,
            "failed_tests": total_failed,
            "skipped_tests": total_skipped,

            # Test name arrays (lengths must match counts above)
            "list_of_failed_tests": failed_tests,
            "list_of_skipped_tests": skipped_tests,
            "list_of_passed_tests": passed_tests
        }

        # Step 4: Validate against schema
        schema = AzureImageResultsPublished.body_schema

        # This should pass validation without errors
        jsonschema.validate(valid_message_body, schema)

        # Step 5: Verify mathematical consistency
        assert valid_message_body["total_tests"] == (
            valid_message_body["passed_tests"] +
            valid_message_body["failed_tests"] +
            valid_message_body["skipped_tests"]
        )

        # Step 6: Verify array length consistency
        assert len(valid_message_body["list_of_failed_tests"]) == valid_message_body["failed_tests"]
        assert len(valid_message_body["list_of_skipped_tests"]) == valid_message_body["skipped_tests"]
        assert len(valid_message_body["list_of_passed_tests"]) == valid_message_body["passed_tests"]

        # Step 7: Test message class methods (without full instantiation)
        # We can test the string representation logic by creating a mock body
        test_message = AzureImageResultsPublished.__new__(AzureImageResultsPublished)
        test_message.body = valid_message_body

        # Verify the message methods work correctly
        assert "Fedora-Cloud-41-x64" in str(test_message)
        assert "fedora_cloud_tests published Azure image test results" in test_message.summary

    def test_memory_size_limits(self):
        """Test that memory size limits are enforced by the schema."""
        schema = AzureImageResultsPublished.body_schema

        # Test array length limits
        # This should fail - too many passed tests (over 250 limit)
        oversized_passed_list = [f"test_case_{i}" for i in range(251)]

        invalid_body_too_many_tests = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "total_tests": 250,  # Keep count valid
            "passed_tests": 250,  # Keep count valid
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": oversized_passed_list  # But array is oversized
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_body_too_many_tests, schema)
        # The error could be about maxItems or about inconsistency
        error_msg = str(exc_info.value)
        assert "maxItems" in error_msg or "251" in error_msg

        # Test string length limits
        # This should fail - test name too long (over 200 characters)
        long_test_name = "a" * 201

        invalid_body_long_test_name = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "total_tests": 1,
            "passed_tests": 1,
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": [long_test_name]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_body_long_test_name, schema)
        assert "maxLength" in str(exc_info.value)

        # Test integer limits
        # This should fail - too many total tests (over 750)
        invalid_body_too_many_total = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "total_tests": 751,  # Over the limit
            "passed_tests": 251,  # Over the limit
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": ["test1"]  # Just one test name to avoid array limit
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_body_too_many_total, schema)
        assert "maximum" in str(exc_info.value)

    def test_memory_limits_valid_cases(self):
        """Test that valid cases within memory limits pass validation."""
        schema = AzureImageResultsPublished.body_schema

        # Test near the limits but still valid
        large_but_valid_passed_list = [f"test_{i}" for i in range(250)]  # Exactly at the 250 limit

        valid_body_large = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "total_tests": 250,
            "passed_tests": 250,
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": large_but_valid_passed_list
        }

        # This should not raise any validation errors
        jsonschema.validate(valid_body_large, schema)

        # Test maximum allowed string length (200 characters)
        max_length_test_name = "a" * 200

        valid_body_max_string = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_definition_name": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "total_tests": 1,
            "passed_tests": 1,
            "failed_tests": 0,
            "skipped_tests": 0,
            "list_of_failed_tests": [],
            "list_of_skipped_tests": [],
            "list_of_passed_tests": [max_length_test_name]
        }

        # This should not raise any validation errors
        jsonschema.validate(valid_body_max_string, schema)
