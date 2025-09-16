"""Module to trigger LISA tests asynchronously."""

import asyncio
import logging
import subprocess

_log = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class LisaRunner:
    """Class to run LISA tests asynchronously"""

    def __init__(self):
        pass

    async def trigger_lisa(
        self, region, community_gallery_image, config):
        # pylint: disable=too-many-return-statements,too-many-branches
        """Trigger LISA tier 1 tests with the provided parameters.

        Args:
            region (str): The Azure region to run the tests in.
            community_gallery_image (str): The community gallery image to use for testing.
            config (dict): A dictionary containing the configuration parameters.
                - subscription (str): The Azure subscription ID.
                - private_key (str): The path to the private key file for authentication.
                - log_path (str): The path to the log file for the LISA tests.
                - run_name (str): The name of the test run.

        Returns:
            bool: True if the LISA test completed successfully (return code 0),
                  False if the test failed, had errors, or if required parameters are missing.
        """
        # Validate the input parameters
        if not region or not isinstance(region, str):
            _log.error("Invalid region parameter: must be a non-empty string")
            return False

        if not community_gallery_image or not isinstance(community_gallery_image, str):
            _log.error(
                "Invalid community_gallery_image parameter: must be a non-empty string"
            )
            return False

        if not isinstance(config, dict):
            _log.error("Invalid config parameter: must be a dictionary")
            return False

        if not config.get("subscription"):
            _log.error("Missing required parameter: subscription")
            return False

        if not config.get("private_key"):
            _log.error("Missing required parameter: private_key")
            return False

        try:
            variables = [
                f"region:{region}",
                f"community_gallery_image:{community_gallery_image}",
                f"subscription_id:{config.get('subscription')}",
                f"admin_private_key_file:{config.get('private_key')}",
            ]
            command = [
                "lisa",
                "-r", "microsoft/runbook/azure_fedora.yml",
                "-v", "tier:1",
                "-v", "test_case_name:verify_boot_error_fail_warnings",
            ]
            for var in variables:
                command.extend(["-v", var])

            # Add optional parameters only if they are provided
            log_path = config.get("log_path")
            if log_path:
                command.extend(["-l", log_path])
                _log.debug("Added log path: %s", log_path)
            else:
                _log.debug("No log path provided, using LISA default")

            run_name = config.get("run_name")
            if run_name:
                command.extend(["-i", run_name])
                _log.debug("Added run name: %s", run_name)
            else:
                _log.debug("No run name provided, using LISA default")

            _log.info("Starting LISA test with command: %s", " ".join(command))
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            async for line in process.stdout:
                line_content = line.decode().strip()
                if line_content:  # Only log non-empty lines
                    _log.info("LISA OUTPUT: %s ", line_content)

            await process.wait()
            # stderr = await process.communicate()

            if process.returncode == 0:
                _log.info("LISA test completed successfully")
                return True
            _log.error("LISA test failed with return code: %d", process.returncode)
            return False
        except Exception as e:  # pylint: disable=broad-except
            _log.error("An error occurred while running the tests: %s", str(e))
            return False
