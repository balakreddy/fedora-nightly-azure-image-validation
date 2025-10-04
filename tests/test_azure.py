"""Unit tests for the AzurePublishedConsumer class in azure.py."""

import os
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock, Mock

import pytest
from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging import config as fm_config

from fedora_cloud_tests.azure import AzurePublishedConsumer

@pytest.fixture(scope="module")
def azure_conf():
    """Provide a minimal config for Azure in the fedora-messaging configuration dictionary."""
    with patch.dict(
        fm_config.conf["consumer_config"],
        {
            "azure": {
                "region": "westus3",
                "subscription_id": "00000000-0000-0000-0000-000000000000",
            }
        },
    ):
        yield

@pytest.fixture
def consumer(azure_conf):  # pylint: disable=unused-argument
    """Create an AzurePublishedConsumer instance for testing."""
    return AzurePublishedConsumer()


@pytest.fixture
def valid_message():
    """Create a valid mock AzurePublishedV1 message."""
    message = Mock(spec=AzurePublishedV1)
    message.topic = "org.fedoraproject.prod.fedora_image_uploader.published.v1.azure.test"
    message.body = {
        "image_definition_name": "Fedora-Cloud-Rawhide-x64",
        "image_version_name": "20250101.0",
        "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery"
    }
    return message


class TestAzurePublishedConsumer:
    # pylint: disable=protected-access
    """Test class for AzurePublishedConsumer."""

    def test_supported_fedora_versions_constant(self):
        """Test that SUPPORTED_FEDORA_VERSIONS contains expected versions."""
        # Test that the constant is defined and is a list
        assert hasattr(AzurePublishedConsumer, 'SUPPORTED_FEDORA_VERSIONS')
        assert isinstance(AzurePublishedConsumer.SUPPORTED_FEDORA_VERSIONS, list)
        assert len(AzurePublishedConsumer.SUPPORTED_FEDORA_VERSIONS) > 0

        # Test that all versions follow expected naming pattern
        for version in AzurePublishedConsumer.SUPPORTED_FEDORA_VERSIONS:
            assert isinstance(version, str)
            assert version.startswith("Fedora-Cloud-")
            assert version.endswith(("-x64", "-Arm64"))

    def test_get_image_definition_name_success(self, consumer, valid_message):
        """Test successful extraction of image definition name."""
        result = consumer._get_image_definition_name(valid_message)
        assert result == "Fedora-Cloud-Rawhide-x64"

    def test_get_image_definition_name_invalid_data(self, consumer):
        """Test handling of invalid image definition name data."""
        # Test missing field
        message = Mock()
        message.body = {}
        assert consumer._get_image_definition_name(message) is None

        # Test non-string value
        message.body = {"image_definition_name": 123}
        assert consumer._get_image_definition_name(message) is None

        # Test missing body attribute
        del message.body
        assert consumer._get_image_definition_name(message) is None

    @patch('fedora_cloud_tests.azure.subprocess.run')
    @patch('os.chmod')
    def test_generate_ssh_key_pair_success(self, mock_chmod, mock_subprocess, consumer):
        """Test successful SSH key pair generation."""
        # Mock subprocess.run to simulate successful ssh-keygen
        mock_subprocess.return_value = MagicMock(stdout="Key generated successfully")

        with TemporaryDirectory() as temp_dir:
            with patch('os.path.exists', return_value=True):
                result = consumer._generate_ssh_key_pair(temp_dir)

                # Verify the method returns the expected private key path
                expected_path = os.path.join(temp_dir, "id_rsa")
                assert result == expected_path

                # Verify ssh-keygen was called with correct parameters
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "ssh-keygen" in call_args
                assert "-t" in call_args and "rsa" in call_args
                assert "-f" in call_args

                # Verify file permissions were set
                mock_chmod.assert_called_once_with(expected_path, 0o600)

    @patch('fedora_cloud_tests.azure.subprocess.run')
    def test_generate_ssh_key_pair_failures(self, mock_subprocess, consumer):
        """Test SSH key pair generation failure cases."""
        with TemporaryDirectory() as temp_dir:
            # Test subprocess failure
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'ssh-keygen')
            result = consumer._generate_ssh_key_pair(temp_dir)
            assert result is None

            # Reset mock for next test
            mock_subprocess.side_effect = None
            mock_subprocess.return_value = MagicMock(stdout="Key generated")

            # Test file not created scenario
            with patch('os.path.exists', return_value=False):
                result = consumer._generate_ssh_key_pair(temp_dir)
                assert result is None

    def test_get_community_gallery_image_success(self, consumer, valid_message):
        """Test successful community gallery image construction."""
        result = consumer.get_community_gallery_image(valid_message)
        expected = "westus3/test-sub/Fedora-Cloud-Rawhide-x64/20250101.0"
        assert result == expected

    def test_get_community_gallery_image_invalid_cases(self, consumer):
        """Test community gallery image extraction with invalid inputs."""
        # Test unsupported Fedora version
        message = Mock()
        message.body = {
            "image_definition_name": "Fedora-Cloud-Unsupported-x64",
            "image_version_name": "20250101.0",
            "image_resource_id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/galleries/test-gallery"
        }
        assert consumer.get_community_gallery_image(message) is None

        # Test invalid message body type
        message.body = "not_a_dict"
        assert consumer.get_community_gallery_image(message) is None

        # Test missing required fields
        message.body = {"image_definition_name": "Fedora-Cloud-Rawhide-x64"}
        assert consumer.get_community_gallery_image(message) is None

        # Test invalid resource ID format
        message.body = {
            "image_definition_name": "Fedora-Cloud-Rawhide-x64",
            "image_version_name": "20250101.0",
            "image_resource_id": "invalid/format"
        }
        assert consumer.get_community_gallery_image(message) is None

        # Test resource_id with insufficient parts (code allows empty parts[2])
        message.body = {
            "image_definition_name": "Fedora-Cloud-Rawhide-x64",
            "image_version_name": "20250101.0",
            "image_resource_id": "//"  # Results in empty parts[2] but still valid per current logic
        }
        result = consumer.get_community_gallery_image(message)
        # The current code allows this and creates: "westus3//Fedora-Cloud-Rawhide-x64/20250101.0"
        assert result == "westus3//Fedora-Cloud-Rawhide-x64/20250101.0"

    @patch('fedora_cloud_tests.azure.asyncio.run')
    @patch('fedora_cloud_tests.azure.LisaRunner')
    @patch.object(AzurePublishedConsumer, '_generate_ssh_key_pair')
    def test_azure_published_callback_success(self, mock_ssh_keygen, mock_lisa_runner, mock_asyncio_run, consumer, valid_message):  # pylint: disable=R0913,R0917
        """Test successful message processing and LISA trigger."""
        mock_runner_instance = MagicMock()
        mock_lisa_runner.return_value = mock_runner_instance
        mock_ssh_keygen.return_value = "/tmp/test_key"

        consumer.azure_published_callback(valid_message)
        mock_lisa_runner.assert_called_once_with()
        mock_asyncio_run.assert_called_once()

    @patch('fedora_cloud_tests.azure.asyncio.run')
    @patch('fedora_cloud_tests.azure.LisaRunner')
    def test_azure_published_callback_unsupported_image(self, mock_lisa_runner, mock_asyncio_run, consumer):
        """Test handling when community gallery image cannot be processed."""
        message = Mock()
        message.topic = "test.topic"
        message.body = {"image_definition_name": "Fedora-Cloud-Unsupported-x64"}

        consumer.azure_published_callback(message)
        mock_lisa_runner.assert_not_called()
        mock_asyncio_run.assert_not_called()

    @patch('fedora_cloud_tests.azure.asyncio.run', side_effect=OSError("LISA execution failed"))
    @patch('fedora_cloud_tests.azure.LisaRunner')
    @patch.object(AzurePublishedConsumer, '_generate_ssh_key_pair')
    def test_azure_published_callback_lisa_exception(self, mock_ssh_keygen, mock_lisa_runner, mock_asyncio_run, consumer, valid_message):  # pylint: disable=R0913,R0917
        """Test exception handling when LISA execution fails."""
        mock_runner_instance = MagicMock()
        mock_lisa_runner.return_value = mock_runner_instance
        mock_ssh_keygen.return_value = "/tmp/test_key"

        # Should not raise exception, just log it
        consumer.azure_published_callback(valid_message)
        mock_asyncio_run.assert_called_once()

    def test_azure_published_callback_message_validation_exception(self, consumer):
        """Test exception handling during message type validation."""
        # Create a message that will cause a TypeError during isinstance check
        # by making it not a proper message type
        invalid_message = Mock()
        invalid_message.topic = "test.topic"
        invalid_message.body = "not_a_dict"  # This will cause isinstance issues

        # This should not crash but should log errors and return early
        consumer.azure_published_callback(invalid_message)

    def test_call_method_delegates_to_callback(self, consumer, valid_message):
        """Test that __call__ method properly delegates to azure_published_callback."""
        with patch.object(consumer, 'azure_published_callback') as mock_callback:
            consumer(valid_message)
            mock_callback.assert_called_once_with(valid_message)
