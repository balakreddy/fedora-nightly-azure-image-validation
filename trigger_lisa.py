"""Module to trigger LISA tests asynchronously."""

import asyncio
import logging
import subprocess


# pylint: disable=too-few-public-methods
class LisaRunner:
    """Class to run LISA tests asynchronously"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    async def trigger_lisa(
        self, region, community_gallery_image, config):
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
        if not all([region, community_gallery_image,
                     config.get("subscription"), config.get("private_key")]):
            self.logger.error(
                "Missing required parameters: region, "
                "community_gallery_image, subscription, or private_key."
            )
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
                "-v", "test_case_name:verify_dhcp_file_configuration",
            ]
            for var in variables:
                command.extend(["-v", var])

            command.extend([
                "-l", config.get("log_path"),
                "-i", config.get("run_name"),
            ])

            self.logger.info("Starting LISA test with command: %s", " ".join(command))
            process = await asyncio.create_subprocess_exec(
                *command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info(
                    "LISA test completed successfully with output %s.",
                    stdout.decode(),
                )
                if stderr:
                    self.logger.info("LISA test has warnings: %s", stderr.decode())
                return True
            self.logger.error("Triggering LISA tests failed %d", process.returncode)
            if stdout:
                self.logger.error("Standard Output: %s", stdout.decode())
            if stderr:
                self.logger.error("Standard Error: %s", stderr.decode())
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error("An error occurred while running the tests: %s", str(e))
            return False
