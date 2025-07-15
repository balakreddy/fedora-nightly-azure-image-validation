"""Unit tests for the LisaRunner class in trigger_lisa.py."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from trigger_lisa import LisaRunner


@pytest.fixture
def runner():
    """Create a LisaRunner instance for testing."""
    return LisaRunner()


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
    async def test_trigger_lisa_success(self, runner, region, community_gallery_image, config_params):
        """Test successful execution of the trigger_lisa method."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"success output", b""))
            mock_subproc_exec.return_value = mock_process

            result = await runner.trigger_lisa(
                region, community_gallery_image, config_params
            )

            assert result is True
            mock_subproc_exec.assert_called_once()
            mock_process.communicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_lisa_success_with_warnings(self, runner, region, community_gallery_image, config_params):
        """Test successful execution with warnings in stderr."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b"success output", b"warning message")
            )
            mock_subproc_exec.return_value = mock_process

            with patch.object(runner.logger, "info") as mock_logger_info:
                result = await runner.trigger_lisa(
                    region, community_gallery_image, config_params
                )

                assert result is True
                # Check that warning was logged
                mock_logger_info.assert_any_call(
                    "LISA test has warnings: %s", "warning message"
                )

    @pytest.mark.asyncio
    async def test_trigger_lisa_failure_non_zero_return_code(self, runner, region, community_gallery_image, config_params):
        """Test failure when LISA returns non-zero exit code."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(
                return_value=(b"error output", b"error stderr")
            )
            mock_subproc_exec.return_value = mock_process

            with patch.object(runner.logger, "error") as mock_logger_error:
                result = await runner.trigger_lisa(
                    region, community_gallery_image, config_params
                )

                assert result is False
                mock_logger_error.assert_any_call("Triggering LISA tests failed %d", 1)
                mock_logger_error.assert_any_call("Standard Output: %s", "error output")
                mock_logger_error.assert_any_call("Standard Error: %s", "error stderr")

    @pytest.mark.asyncio
    async def test_trigger_lisa_exception_handling(self, runner, region, community_gallery_image, config_params):
        """Test error handling and logging when subprocess execution fails."""
        with patch(
            "asyncio.create_subprocess_exec", side_effect=Exception("Process failed")
        ):
            with patch.object(runner.logger, "error") as mock_logger_error:
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
        with patch.object(runner.logger, "error") as mock_logger_error:
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
        with patch.object(runner.logger, "error") as mock_logger_error:
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

        with patch.object(runner.logger, "error") as mock_logger_error:
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

        with patch.object(runner.logger, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                region, community_gallery_image, config_without_private_key
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Missing required parameter: private_key"
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_command_construction(self, runner, region, community_gallery_image, config_params):
        """Test that the LISA command is constructed correctly."""
        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"success", b""))
            mock_subproc_exec.return_value = mock_process

            await runner.trigger_lisa(
                region, community_gallery_image, config_params
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
                f"region:{region}",
                "-v",
                f"community_gallery_image:{community_gallery_image}",
                "-v",
                f"subscription_id:{config_params['subscription']}",
                "-v",
                f"admin_private_key_file:{config_params['private_key']}",
                "-l",
                config_params["log_path"],
                "-i",
                config_params["run_name"],
            ]

            mock_subproc_exec.assert_called_once_with(
                *expected_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_trigger_lisa_missing_optional_config_parameters(self, runner, region, community_gallery_image):
        """Test successful execution when optional config parameters 
        (log_path, run_name) are missing."""
        minimal_config = {
            "subscription": "test-subscription",
            "private_key": "/path/to/key",
            # log_path and run_name are missing
        }

        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"success", b""))
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
    async def test_trigger_lisa_with_optional_config_parameters(self, runner, region, community_gallery_image):
        """Test successful execution when optional config parameters are provided."""
        config_with_optionals = {
            "subscription": "test-subscription",
            "private_key": "/path/to/key",
            "log_path": "/custom/log/path",
            "run_name": "custom-run-name",
        }

        with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"success", b""))
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
        with patch.object(runner.logger, "error") as mock_logger_error:
            result = await runner.trigger_lisa(
                region, community_gallery_image, "not a dict"  # Invalid type
            )

            assert result is False
            mock_logger_error.assert_called_with(
                "Invalid config parameter: must be a dictionary"
            )

    def test_lisa_runner_init_without_logger(self):
        """Test LisaRunner initialization without custom logger."""
        runner = LisaRunner()
        assert runner.logger is not None
        assert runner.logger.name == "trigger_lisa"
