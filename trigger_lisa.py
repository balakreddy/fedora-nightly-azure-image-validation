"""Module to trigger LISA tests asynchronously."""

import asyncio
import logging
import subprocess

# pylint: disable=too-few-public-methods
class LisaRunner:
    """ Class to run LISA tests asynchronously"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    async def trigger_lisa(self, region, community_gallery_image, subscription, private_key):
        """ Trigger LISA tier 0 tests with the provided parameters."""
        try:
            variables = [
                f"region:{region}",
                f"community_gallery_image:{community_gallery_image}",
                f"subscription_id:{subscription}",
                f"admin_private_key_file:{private_key}"
            ]
            command = [
                "lisa",
                "-r", "microsoft/runbook/azure.yml",
                "-v", "tier:0"
                # "-v", "case:verify_dhcp_file_configuration"
            ]
            for var in variables:
                command.extend(["-v", var])

            self.logger.info("Starting LISA test with command: %s", ' '.join(command))
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            self.logger.info("LISA test completed with output: %s ", stdout.decode())
            if stderr:
                self.logger.error("LISA test encountered errors: %s ", stderr.decode())
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error("An error occurred while running the tests: %s", str(e))
