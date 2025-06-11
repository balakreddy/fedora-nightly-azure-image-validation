"""Unit tests for the LisaRunner class in trigger_lisa.py."""

from unittest.mock import patch, MagicMock
import pytest
from trigger_lisa import LisaRunner

@pytest.mark.asyncio
async def test_trigger_lisa_success():
    """Test successful execution of the trigger_lisa method."""
    runner = LisaRunner()
    with patch("asyncio.create_subprocess_exec") as mock_subproc_exec:
        mock_process = MagicMock()
        mock_process.communicate = MagicMock(return_value=(b"success", b""))
        mock_subproc_exec.return_value = mock_process
        await runner.trigger_lisa("westus2", "image", "sub", "key")
        mock_subproc_exec.assert_called()
        mock_process.communicate.assert_called()

@pytest.mark.asyncio
async def test_trigger_lisa_error_logs():
    """Test error handling and logging in the trigger_lisa method."""
    runner = LisaRunner()
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("fail")):
        with patch.object(runner.logger, "error") as mock_logger_error:
            await runner.trigger_lisa("eastus", "image", "sub", "key")
            mock_logger_error.assert_called()
