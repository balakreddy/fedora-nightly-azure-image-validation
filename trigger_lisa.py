import asyncio
import logging
import subprocess
import os

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

            self.logger.info("Starting LISA test with command: {' '.join(command)}")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            self.logger.info("LISA test completed with output:\n{stdout.decode()}")
            if stderr:
                self.logger.error("LISA test encountered errors:\n{stderr.decode()}")
        except Exception as e:
            self.logger.error("An error occurred: {e}")

if __name__ == "__main__":
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lisa_runner.log')
    logger = logging.getLogger("LisaRunnerLogger")
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
    runner = LisaRunner(logger)
    region = ""
    community_gallery_image = ""
    subscription = ""
    private_key = ""
    asyncio.run(runner.trigger_lisa(region, community_gallery_image, subscription, private_key))