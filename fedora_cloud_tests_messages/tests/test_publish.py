"""
Tests for fedora_cloud_tests.publish module schema validation.

This module tests the message schema definitions and validation
for Azure image test results publishing without requiring full
fedora-messaging registration.
"""

import pytest
import jsonschema
from fedora_cloud_tests_messages.publish import BaseTestResults, AzureTestResults


class TestBaseTestResults:
    """Test cases for BaseTestResults base class."""

    def test_topic_format(self):
        """Test that topic follows expected format."""
        expected_topic = "org.fedoraproject.prod.fedora_cloud_tests.test_results.v1"
        assert BaseTestResults.topic == expected_topic

    def test_app_name_property(self):
        """Test that app_name property returns correct value."""
        # Test the class property directly - it's a property that returns a string
        class_instance = BaseTestResults.__new__(BaseTestResults)
        assert class_instance.app_name == "fedora_cloud_tests"


class TestAzureTestResults:
    """Test cases for AzureTestResults message class."""

    def test_topic_inheritance(self):
        """Test that Azure message inherits and extends base topic."""
        expected_topic = "org.fedoraproject.prod.fedora_cloud_tests.test_results.v1.azure"
        assert AzureTestResults.topic == expected_topic

    def test_schema_validation_missing_required_fields(self):
        """Test schema validation fails with missing required fields."""
        incomplete_body = {
            "architecture": "x86_64",
            # Missing other required fields
        }

        with pytest.raises(jsonschema.ValidationError):
            message = AzureTestResults(body=incomplete_body)
            message.validate()

    def test_schema_validation_wrong_data_types(self):
        """Test schema validation fails with wrong data types."""
        invalid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-Rawhide-20250922.n.0",
            "image_id": "Fedora-Cloud-Rawhide-x64",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery",
            "passed_tests": "not_an_object",  # Should be object with count and tests
            "failed_tests": {
                "count": 1,
                "tests": {"Dhcp.verify_dhcp_client_timeout": "DHCP client timeout configuration issue"}
            },
            "skipped_tests": {
                "count": 1,
                "tests": {"GpuTestSuite.verify_load_gpu_driver": "No available quota found on 'westus3'"}
            }
        }

        with pytest.raises(jsonschema.ValidationError):
            message = AzureTestResults(body=invalid_body)
            message.validate()

    def test_schema_validation_invalid_test_objects(self):
        """Test schema validation fails with invalid test result objects."""
        invalid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-Rawhide-20250922.n.0",
            "image_id": "Fedora-Cloud-Rawhide-x64",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery",
            "passed_tests": {
                "count": 1,
                "tests": {"AzureImageStandard.verify_grub": "Test passed in 5.494 seconds"}
            },
            "failed_tests": {
                "count": "not_a_number",  # Should be integer
                "tests": {"Storage.verify_swap": "Swap configuration from waagent.conf and distro should match"}
            },
            "skipped_tests": {
                "count": 1,
                "tests": {"ACCBasicTest.verify_sgx": "No available quota found on 'westus3'"}
            }
        }

        with pytest.raises(jsonschema.ValidationError):
            message = AzureTestResults(body=invalid_body)
            message.validate()

    def test_message_string_representation(self):
        """Test the __str__ method of AzureTestResults."""
        valid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 0,
                "tests": {}
            },
            "skipped_tests": {
                "count": 0,
                "tests": {}
            },
            "passed_tests": {
                "count": 1,
                "tests": {"Provisioning.smoke_test": "Test passed in 46.198 seconds"}
            }
        }

        message = AzureTestResults(body=valid_body)
        str_repr = str(message)
        assert "Fedora-Cloud-41-x64" in str_repr
        assert "AzureImageTestResults" in str_repr

    def test_message_summary_property(self):
        """Test the summary property of AzureTestResults."""
        # Using realistic test counts from LISA XML data (91 total: 58 passed, 8 failed, 25 skipped)
        valid_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 8,
                "tests": {
                    "Dhcp.verify_dhcp_client_timeout": "DHCP client timeout should be set equal or more than 300 seconds",
                    "AzureDiskEncryption.verify_azure_disk_encryption_provisioned": "Azure authentication token expired",
                    "HvModule.verify_initrd_modules": "Required Hyper-V modules are missing from initrd",
                    "Storage.verify_swap": "Swap configuration from waagent.conf and distro should match",
                    "Provisioning.verify_deployment_provision_premiumv2_disk": "VM size Standard_DS2_v2 not available in WestUS3",
                    "Provisioning.verify_deployment_provision_ultra_datadisk": "VM size Standard_B2als_v2 not available in WestUS3",
                    "VMAccessTests.verify_valid_password_run": "Password not set as intended for user vmaccessuser",
                    "Vdso.verify_vdso": "Current distro Fedora doesn't support vdsotest"
                }
            },
            "skipped_tests": {
                "count": 25,
                "tests": {
                    "ACCBasicTest.verify_sgx": "No available quota found on 'westus3'",
                    "CVMSuite.verify_lsvmbus": "Security profile requirement not supported in capability",
                    "GpuTestSuite.verify_load_gpu_driver": "No available quota found on 'westus3'",
                    "ApplicationHealthExtension.verify_application_health_extension": "Fedora release 41 is not supported"
                }
            },
            "passed_tests": {
                "count": 58,
                "tests": {
                    "LsVmBus.verify_vmbus_devices_channels": "Test passed in 20.126 seconds",
                    "Floppy.verify_floppy_module_is_blacklisted": "Test passed in 3.309 seconds",
                    "Dns.verify_dns_name_resolution": "Test passed in 8.379 seconds",
                    "AzureImageStandard.verify_default_targetpw": "Test passed in 2.992 seconds",
                    "AzureImageStandard.verify_grub": "Test passed in 5.494 seconds"
                }
            }
        }

        message = AzureTestResults(body=valid_body)
        summary = message.summary

        # Check that summary contains test counts matching LISA results
        assert "58 tests passed" in summary
        assert "8 tests failed" in summary
        assert "25 tests skipped" in summary
        assert "Fedora-Cloud-41-x64" in summary


class TestSchemaIntegration:
    """Integration tests for schema functionality."""

    def test_create_valid_message_body_example(self):
        """Example of how to create a properly formatted message body with real LISA test names."""
        valid_message_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 3,
                "tests": {
                    "Dhcp.verify_dhcp_client_timeout": "DHCP client timeout should be set equal or more than 300 seconds",
                    "Storage.verify_swap": "Swap configuration from waagent.conf and distro should match",
                    "VMAccessTests.verify_valid_password_run": "Password not set as intended for user vmaccessuser"
                }
            },
            "skipped_tests": {
                "count": 4,
                "tests": {
                    "ACCBasicTest.verify_sgx": "No available quota found on 'westus3'",
                    "GpuTestSuite.verify_load_gpu_driver": "No available quota found on 'westus3'",
                    "ApplicationHealthExtension.verify_application_health_extension": "Fedora release 41 is not supported",
                    "NetworkWatcherExtension.verify_azure_network_watcher": "Fedora release 41 is not supported"
                }
            },
            "passed_tests": {
                "count": 5,
                "tests": {
                    "LsVmBus.verify_vmbus_devices_channels": "Test passed in 20.126 seconds",
                    "Dns.verify_dns_name_resolution": "Test passed in 8.379 seconds",
                    "AzureImageStandard.verify_grub": "Test passed in 5.494 seconds",
                    "Storage.verify_resource_disk_mounted": "Test passed in 5.923 seconds",
                    "TimeSync.verify_timedrift_corrected": "Test passed in 54.743 seconds"
                }
            }
        }

        # Validate against schema
        message = AzureTestResults(body=valid_message_body)
        message.validate()

        # Verify count consistency
        assert valid_message_body["failed_tests"]["count"] == len(valid_message_body["failed_tests"]["tests"])
        assert valid_message_body["skipped_tests"]["count"] == len(valid_message_body["skipped_tests"]["tests"])
        assert valid_message_body["passed_tests"]["count"] == len(valid_message_body["passed_tests"]["tests"])

        # Test message methods
        assert "Fedora-Cloud-41-x64" in str(message)
        summary = message.summary
        assert "5 tests passed" in summary
        assert "3 tests failed" in summary
        assert "4 tests skipped" in summary

    def test_test_results_object_validation(self):
        """Test validation of test results object structure."""
        # Test missing required fields in test results object
        invalid_body_missing_count = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                # Missing "count" field
                "tests": {"Vdso.verify_vdso": "Current distro Fedora doesn't support vdsotest"}
            },
            "skipped_tests": {
                "count": 0,
                "tests": {}
            },
            "passed_tests": {
                "count": 0,
                "tests": {}
            }
        }

        with pytest.raises(jsonschema.ValidationError):
            message = AzureTestResults(body=invalid_body_missing_count)
            message.validate()

        # Test missing required fields in test results object
        invalid_body_missing_tests = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 1,
                # Missing "tests" field
            },
            "skipped_tests": {
                "count": 0,
                "tests": {}
            },
            "passed_tests": {
                "count": 0,
                "tests": {}
            }
        }

        with pytest.raises(jsonschema.ValidationError):
            message = AzureTestResults(body=invalid_body_missing_tests)
            message.validate()

    def test_valid_edge_cases(self):
        """Test valid edge cases that should pass validation."""
        # Test with only passed tests
        only_passed_body = {
            "architecture": "x86_64",
            "compose_id": "Fedora-41-20241001.n.0",
            "image_id": "Fedora-Cloud-41-x64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 0,
                "tests": {}
            },
            "skipped_tests": {
                "count": 0,
                "tests": {}
            },
            "passed_tests": {
                "count": 3,
                "tests": {
                    "Provisioning.smoke_test": "Test passed in 46.198 seconds",
                    "Dns.verify_dns_name_resolution": "Test passed in 8.379 seconds",
                    "KernelDebug.verify_enable_kprobe": "Test passed in 10.013 seconds"
                }
            }
        }

        message = AzureTestResults(body=only_passed_body)
        message.validate()  # Should not raise

        # Test with only failed tests
        only_failed_body = {
            "architecture": "aarch64",
            "compose_id": "Fedora-Rawhide-20241015.n.0",
            "image_id": "Fedora-Cloud-Rawhide-Arm64",
            "image_resource_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/galleries/test",
            "failed_tests": {
                "count": 2,
                "tests": {
                    "Dhcp.verify_dhcp_client_timeout": "DHCP client timeout should be set equal or more than 300 seconds",
                    "Storage.verify_swap": "Swap configuration from waagent.conf and distro should match"
                }
            },
            "skipped_tests": {
                "count": 0,
                "tests": {}
            },
            "passed_tests": {
                "count": 0,
                "tests": {}
            }
        }

        message = AzureTestResults(body=only_failed_body)
        message.validate()  # Should not raise
