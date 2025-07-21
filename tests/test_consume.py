"""Unit tests for the AzurePublishedConsumer class in consume.py."""

import logging
from unittest.mock import patch, MagicMock, Mock

import pytest
from fedora_image_uploader_messages.publish import AzurePublishedV1

from consume import AzurePublishedConsumer


@pytest.fixture
def consumer():
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
        expected_versions = [
            "Fedora-Cloud-Rawhide-x64",
            "Fedora-Cloud-41-x64",
            "Fedora-Cloud-41-Arm64", 
            "Fedora-Cloud-Rawhide-Arm64",
            "Fedora-Cloud-42-x64",
            "Fedora-Cloud-42-Arm64",
        ]
        assert AzurePublishedConsumer.SUPPORTED_FEDORA_VERSIONS == expected_versions

    def test_consumer_initialization(self, consumer):
        """Test that consumer is properly initialized with logger configuration."""
        assert consumer.logger is not None
        assert len(consumer.logger.handlers) == 2  # File and console handlers
        assert consumer.logger.level == logging.INFO
        assert not consumer.logger.propagate

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

    def test_generate_test_log_path(self, consumer):
        """Test log path and run name generation with different configurations."""
        # Test with custom settings enabled
        with patch('consume.CUSTOM_LOG_PATH', True):
            with patch('consume.CUSTOM_RUN_NAME', True):
                with patch('os.path.expanduser', return_value="/home/user/lisa_results"):
                    with patch('os.makedirs'):
                        log_path, run_name = consumer._generate_test_log_path("Fedora-Cloud-Rawhide-x64")
                        assert log_path == "/home/user/lisa_results/Fedora-Cloud-Rawhide-x64"
                        assert run_name is not None
                        assert isinstance(run_name, str)

        # Test with custom settings disabled
        with patch('consume.CUSTOM_LOG_PATH', False):
            with patch('consume.CUSTOM_RUN_NAME', False):
                log_path, run_name = consumer._generate_test_log_path("Fedora-Cloud-Rawhide-x64")
                assert log_path is None
                assert run_name is None

    def test_generate_test_log_path_error_handling(self, consumer):
        """Test error handling during log path creation and run name generation."""
        # Test log path creation failure
        with patch('consume.CUSTOM_LOG_PATH', True):
            with patch('consume.CUSTOM_RUN_NAME', False):
                with patch('os.makedirs', side_effect=OSError("Permission denied")):
                    log_path, run_name = consumer._generate_test_log_path("test-image")
                    assert log_path is None
                    assert run_name is None

        # Test run name generation failure
        with patch('consume.CUSTOM_LOG_PATH', False):
            with patch('consume.CUSTOM_RUN_NAME', True):
                with patch('consume.datetime') as mock_datetime:
                    mock_datetime.now.side_effect = Exception("Time error")
                    log_path, run_name = consumer._generate_test_log_path("test-image")
                    assert log_path is None
                    assert run_name is None

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

    @patch('consume.asyncio.run')
    @patch('consume.LisaRunner')
    def test_azure_published_callback_success(self, mock_lisa_runner, mock_asyncio_run, consumer, valid_message):
        """Test successful message processing and LISA trigger."""
        mock_runner_instance = MagicMock()
        mock_lisa_runner.return_value = mock_runner_instance

        consumer.azure_published_callback(valid_message)
        mock_lisa_runner.assert_called_once_with(logger=consumer.logger)
        mock_asyncio_run.assert_called_once()

    @patch('consume.asyncio.run')
    @patch('consume.LisaRunner')
    def test_azure_published_callback_unsupported_image(self, mock_lisa_runner, mock_asyncio_run, consumer):
        """Test handling when community gallery image cannot be processed."""
        message = Mock()
        message.topic = "test.topic"
        message.body = {"image_definition_name": "Fedora-Cloud-Unsupported-x64"}

        consumer.azure_published_callback(message)
        mock_lisa_runner.assert_not_called()
        mock_asyncio_run.assert_not_called()

    @patch('consume.asyncio.run', side_effect=Exception("LISA execution failed"))
    @patch('consume.LisaRunner')
    def test_azure_published_callback_lisa_exception(self, mock_lisa_runner, mock_asyncio_run, consumer, valid_message):
        """Test exception handling when LISA execution fails."""
        mock_runner_instance = MagicMock()
        mock_lisa_runner.return_value = mock_runner_instance

        # Should not raise exception, just log it
        consumer.azure_published_callback(valid_message)
        mock_asyncio_run.assert_called_once()

    def test_azure_published_callback_message_validation_exception(self, consumer, valid_message):
        """Test exception handling during message type validation."""
        with patch('consume.isinstance', side_effect=Exception("Validation error")):
            # Should not crash, just log the error and continue processing
            consumer.azure_published_callback(valid_message)

    def test_call_method_delegates_to_callback(self, consumer, valid_message):
        """Test that __call__ method properly delegates to azure_published_callback."""
        with patch.object(consumer, 'azure_published_callback') as mock_callback:
            consumer(valid_message)
            mock_callback.assert_called_once_with(valid_message)
