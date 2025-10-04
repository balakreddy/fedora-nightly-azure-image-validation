"""Unit tests for the LisaRunner class in trigger_lisa.py."""

import subprocess
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fedora_cloud_tests import trigger_lisa

# pylint: disable=protected-access
@pytest.fixture
def runner():
    """Create a LisaRunner instance for testing."""
    return trigger_lisa.LisaRunner()


@pytest.fixture
def test_setup(runner, region, community_gallery_image, config_params):
    """Create a test setup object combining common fixtures."""
    return {
        'runner': runner,
        'region': region,
        'community_gallery_image': community_gallery_image,
        'config_params': config_params
    }


@pytest.fixture
def mock_process():
    """Create a properly mocked async subprocess for testing."""
    process = MagicMock()
    process.returncode = 0
    process.wait = AsyncMock()

    # Mock stdout as an async iterator
    async def mock_stdout_lines():
        lines = [b"LISA test output line 1\n", b"LISA test output line 2\n"]
        for line in lines:
            yield line

    process.stdout = mock_stdout_lines()
    return process


@pytest.fixture
def config_params():
    """Create test configuration parameters."""
    return {
        "subscription": "test-subscription-id",
        "private_key": "/path/to/private/key",
        "log_path": "/tmp/test_logs",
        "run_name": "test-run-name",
    }


@pytest.fixture
def region():
    """Create test region."""
    return "westus2"


@pytest.fixture
def community_gallery_image():
    """Create test community gallery image."""
    return "test/gallery/image"


class TestLisaRunner:
    """Test class for LisaRunner."""

    @pytest.mark.asyncio
    async def test_trigger_lisa_success(self, test_setup, mock_process):
        """Test successful execution of the trigger_lisa method."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_subproc_exec.return_value = mock_process

            result = await test_setup['runner'].trigger_lisa(
                test_setup['region'], test_setup['community_gallery_image'], test_setup['config_params']
            )

            assert result is True
            mock_subproc_exec.assert_called_once()
            mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_lisa_success_with_warnings(self, test_setup, mock_process):
        """Test successful execution with output."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_subproc_exec.return_value = mock_process

            with patch.object(trigger_lisa._log, "info") as mock_logger_info:
                result = await test_setup['runner'].trigger_lisa(
                    test_setup['region'], test_setup['community_gallery_image'], test_setup['config_params']
                )

                assert result is True
                # Check that LISA output was logged
                mock_logger_info.assert_any_call("LISA OUTPUT: %s ", "LISA test output line 1")

    @pytest.mark.asyncio
    async def test_trigger_lisa_failure_non_zero_return_code(self, runner, region, community_gallery_image, config_params):
        """Test failure when LISA returns non-zero exit code."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.wait = AsyncMock()

            # Mock stdout as an async iterator with error output
            async def mock_stdout_lines():
                lines = [b"Error: LISA test failed\n", b"Additional error details\n"]
                for line in lines:
                    yield line

            mock_process.stdout = mock_stdout_lines()
            mock_subproc_exec.return_value = mock_process

            with patch.object(trigger_lisa._log, "error") as mock_logger_error:
                result = await runner.trigger_lisa(
                    region, community_gallery_image, config_params
                )

                assert result is False
                mock_logger_error.assert_any_call("LISA test failed with return code: %d", 1)

    @pytest.mark.asyncio
    async def test_trigger_lisa_exception_handling(self, runner, region, community_gallery_image, config_params):
        """Test error handling and logging when subprocess execution fails."""
        with patch(
            "asyncio.create_subprocess_exec", side_effect=Exception("Process failed")
        ):
            with patch.object(trigger_lisa._log, "error") as mock_logger_error:
                result = await runner.trigger_lisa(
                    region, community_gallery_image, config_params
                )

                assert result is False
                mock_logger_error.assert_called_with(
                    "An error occurred while running the tests: %s", "Process failed"
                )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_region(self, runner, community_gallery_image, config_params):
        """Test validation failure when region is missing."""
        with patch.object(trigger_lisa._log, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                "", community_gallery_image, config_params
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Invalid region parameter: must be a non-empty string"
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_community_gallery_image(self, runner, region, config_params):
        """Test validation failure when community_gallery_image is missing."""
        with patch.object(trigger_lisa._log, "error") as mock_logger_error:
            result = await runner.trigger_lisa(region, "", config_params)

            assert result is False
            mock_logger_error.assert_called_with(
                "Invalid community_gallery_image parameter: must be a non-empty string"
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_subscription(self, runner, region, community_gallery_image, config_params):
        """Test validation failure when subscription is missing."""
        config_without_subscription = config_params.copy()
        del config_without_subscription["subscription"]

        with patch.object(trigger_lisa._log, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                region, community_gallery_image, config_without_subscription
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Missing required parameter: subscription"
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_private_key(self, runner, region, community_gallery_image, config_params):
        """Test validation failure when private_key is missing."""
        config_without_private_key = config_params.copy()
        del config_without_private_key["private_key"]

        with patch.object(trigger_lisa._log, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                region, community_gallery_image, config_without_private_key
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Missing required parameter: private_key"
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_command_construction(self, test_setup, mock_process):
        """Test that the LISA command is constructed correctly."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_subproc_exec.return_value = mock_process

            await test_setup['runner'].trigger_lisa(
                test_setup['region'], test_setup['community_gallery_image'], test_setup['config_params']
            )

            # Verify the command was called with correct arguments
            expected_command = [
                "lisa",
                "-r",
                "microsoft/runbook/azure_fedora.yml",
                "-v",
                "tier:1",
                "-v",
                "test_case_name:verify_dhcp_file_configuration",
                "-v",
                f"region:{test_setup['region']}",
                "-v",
                f"community_gallery_image:{test_setup['community_gallery_image']}",
                "-v",
                f"subscription_id:{test_setup['config_params']['subscription']}",
                "-v",
                f"admin_private_key_file:{test_setup['config_params']['private_key']}",
                "-l",
                test_setup['config_params']["log_path"],
                "-i",
                test_setup['config_params']["run_name"],
            ]

            mock_subproc_exec.assert_called_once_with(
                *expected_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_optional_config_parameters(self, runner, region, community_gallery_image, mock_process):
        """Test successful execution when optional config parameters 
        (log_path, run_name) are missing."""
        minimal_config = {
            "subscription": "test-subscription",
            "private_key": "/path/to/key",
            # log_path and run_name are missing
        }

        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_subproc_exec.return_value = mock_process

            result = await runner.trigger_lisa(
                region, community_gallery_image, minimal_config
            )

            # Now the implementation should handle missing optional parameters gracefully
            assert result is True

            # Verify command is called but without the optional -l and -i flags
            args, _ = mock_subproc_exec.call_args
            command_list = list(args)
            assert "-l" not in command_list
            assert "-i" not in command_list
            # But should still have the required arguments
            assert "lisa" in command_list
            assert "-r" in command_list
            assert "microsoft/runbook/azure_fedora.yml" in command_list

    @pytest.mark.asyncio
    async def test_trigger_lisa_with_optional_config_parameters(self, runner, region, community_gallery_image, mock_process):
        """Test successful execution when optional config parameters are provided."""
        config_with_optionals = {
            "subscription": "test-subscription",
            "private_key": "/path/to/key",
            "log_path": "/custom/log/path",
            "run_name": "custom-run-name",
        }

        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_subproc_exec.return_value = mock_process

            result = await runner.trigger_lisa(
                region, community_gallery_image, config_with_optionals
            )

            assert result is True
            # Verify command includes the provided optional parameters
            args, _ = mock_subproc_exec.call_args
            command_list = list(args)
            assert "-l" in command_list
            assert "/custom/log/path" in command_list
            assert "-i" in command_list
            assert "custom-run-name" in command_list

    @pytest.mark.asyncio
    async def test_trigger_lisa_invalid_config_type(self, runner, region, community_gallery_image):
        """Test validation failure when config is not a dictionary."""
        with patch.object(trigger_lisa._log, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                region, community_gallery_image, "not a dict"  # Invalid type
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Invalid config parameter: must be a dictionary"
            )
