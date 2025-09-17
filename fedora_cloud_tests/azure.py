"""
AMQP consumer that processes messages from fedora-image-uploader when it uploads
a new Cloud image to Azure.

This consumer is responsible for testing the new image via LISA and annotating the
image with the results.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging import config

from .trigger_lisa import LisaRunner

PRIVATE_KEY = ""  # Path to the private key file for Azure authentication

_log = logging.getLogger(__name__)


class AzurePublishedConsumer:
    """Consumer class for AzurePublishedV1 messages to trigger LISA tests."""

    # Supported Fedora versions for testing
    SUPPORTED_FEDORA_VERSIONS = [
        "Fedora-Cloud-Rawhide-x64",
        "Fedora-Cloud-41-x64",
        "Fedora-Cloud-41-Arm64",
        "Fedora-Cloud-Rawhide-Arm64",
        "Fedora-Cloud-42-x64",
        "Fedora-Cloud-42-Arm64",
        ]

    def __init__(self):
        try:
            self.conf = config.conf["consumer_config"]["azure"]
        except KeyError:
            _log.error("The Azure consumer requires an 'azure' config section")
            raise

    def __call__(self, message):
        """Callback method to handle incoming messages."""
        _log.info("Received message: %s", message)
        self.azure_published_callback(message)

    def _get_image_definition_name(self, message):
        """ Get image definition name from the message body.

        Args:
            message (AzurePublishedV1): The message containing image details.

        Returns:
            str: The image definition name if found, else None.
            Eg: "Fedora-Cloud-Rawhide-x64", "Fedora-Cloud-41-x64", etc.
        """
        try:
            image_definition_name = message.body.get("image_definition_name")
            if not isinstance(image_definition_name, str):
                _log.error(
                    "image_definition_name is not a string: %s", image_definition_name
                )
                return None
            _log.info("Extracted image_definition_name: %s", image_definition_name)
            return image_definition_name
        except AttributeError:
            _log.error("Message body does not have 'image_definition_name' field.")
            return None

    def get_community_gallery_image(self, message):
        """Extract community gallery image from the messages."""
        _log.info(
            "Extracting community gallery image from the message: %s", message.body
        )
        try:
            # Validate message.body is a dict
            if not isinstance(message.body, dict):
                _log.error("Message body is not a dictionary.")
                return None

            image_definition_name = self._get_image_definition_name(message)
            # Run tests only for fedora rawhide, 41 and 42,
            #  include your Fedora versions in SUPPORTED_FEDORA_VERSIONS
            if image_definition_name not in self.SUPPORTED_FEDORA_VERSIONS:
                _log.info(
                    "image_definition_name '%s' not in supported Fedora"
                    " versions, skipping.",
                    image_definition_name,
                )
                return None
            image_version_name = message.body.get("image_version_name")
            image_resource_id = message.body.get("image_resource_id")

            # Check for missing fields
            if not all([image_definition_name, image_version_name, image_resource_id]):
                _log.error("Missing required image fields in message body.")
                return None

            # Defensive split and validation
            parts = image_resource_id.split("/")
            if len(parts) < 3:
                _log.error(
                    "image_resource_id format is invalid: %s", image_resource_id
                )
                return None
            resource_id = parts[2]

            community_gallery_image = (
                f"{self.conf['region']}/{resource_id}/"
                f"{image_definition_name}/{image_version_name}"
            )
            _log.info(
                "Constructed community gallery image: %s", community_gallery_image
            )
            return community_gallery_image

        except AttributeError as e:
            _log.error(
                "Failed to extract image details from the message: %s", str(e)
            )
            return None

    def azure_published_callback(self, message):
        """Handle Azure published messages"""
        _log.info("Received message on topic: %s", message.topic)
        _log.info("Message %s", message.body)
        try:
            if isinstance(message, AzurePublishedV1):
                _log.info("Message properties match AzurePublishedV1 schema.")
        except TypeError as e:
            _log.error(
                "Message properties do not match AzurePublishedV1 schema: %s", str(e)
            )

        community_gallery_image = self.get_community_gallery_image(message)

        if not community_gallery_image:
            _log.error(
                "Unsupported or No community gallery image found in the message.")
            return

        image_definition_name = self._get_image_definition_name(message)

        # Generate run name with UTC format
        run_name = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        _log.info("Run name generated: %s", run_name)

        try:
            # Use TemporaryDirectory context manager for auto cleanup at the end of
            # the test run
            with TemporaryDirectory(
                prefix=f"lisa_results_{image_definition_name}_",
                suffix="_logs"
            ) as log_path:
                _log.info("Temporary log path created: %s", log_path)

                config_params = {
                    "subscription": self.conf["subscription_id"],
                    "private_key": PRIVATE_KEY,
                    "log_path": log_path,
                    "run_name": run_name,
                }
                _log.info("LISA config parameters: %s", config_params)
                _log.info("Triggering tests for image: %s", community_gallery_image)
                runner = LisaRunner()
                ret = asyncio.run(
                    runner.trigger_lisa(
                        region=self.conf["region"],
                        community_gallery_image=community_gallery_image,
                        config=config_params
                    )
                )
                _log.info("LISA trigger completed with return code: %d", ret)
                if ret == 0:
                    _log.info("LISA trigger executed successfully.")
                    test_results = self._parse_test_results(log_path, run_name)
                    if test_results is not None:
                        _log.info("Test execution completed with results: %s", test_results)
                        # To Do: Implement sending the results using publisher
                    else:
                        _log.error("Failed to parse test results, skipping image")
                else:
                    _log.error("LISA trigger failed with return code: %d", ret)
                # TemporaryDirectory automatically cleans up when exiting the context

        except OSError as e:
            _log.exception("Failed to trigger LISA: %s", str(e))

    def _parse_test_results(self, log_path, run_name):
        """
        Parse the test results from the LISA runner output.
        1. Find the xml file in the log_path
        2. Read the xml file and extract number of tests run, tests passed, failed and skipped

        Returns:
            dict: Dictionary containing test results with keys:
                  'total_tests', 'passed', 'failed', 'skipped', 'errors'
            None: If parsing fails and results cannot be determined
        """
        # Find and validate XML file
        xml_file = self._find_xml_file(log_path, run_name)
        if not xml_file or not os.path.exists(xml_file):
            _log.error("No XML file found in the log path: %s", log_path)
            return None

        _log.info("Found XML file: %s", xml_file)

        # Parse the XML file
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            _log.info("Parsing xml root element: %s", root.tag)

            counters = self._extract_test_counters(root)
            if counters is None:
                return None

            return self._calculate_final_results(counters)

        except ET.ParseError as e:
            _log.error("Failed to parse XML file %s: %s", xml_file, str(e))
            return None

    def _extract_test_counters(self, root):
        """
        Extract test counters from XML root element.
        
        Args:
            root: XML root element (either 'testsuites' or 'testsuite')
            
        Returns:
            dict: Test counters or None if extraction fails
        """
        if root.tag not in ("testsuite", "testsuites"):
            _log.error("Unexpected XML root element: %s", root.tag)
            return None

        counters = {'total_tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}

        # Extract counters from root element
        for key, attr in [('total_tests', 'tests'), ('failures', 'failures'),
                         ('errors', 'errors'), ('skipped', 'skipped')]:
            attr_value = root.attrib.get(attr, '0')
            counters[key] = int(attr_value) if attr_value.isdigit() else 0

        # If root doesn't have values and it's testsuites, sum from individual test suites
        if counters['total_tests'] == 0 and root.tag != 'testsuite':
            for suite in root.findall("testsuite"):
                for key, attr in [('total_tests', 'tests'), ('failures', 'failures'),
                                 ('errors', 'errors'), ('skipped', 'skipped')]:
                    attr_value = suite.attrib.get(attr, '0')
                    counters[key] += int(attr_value) if attr_value.isdigit() else 0

        return counters

    def _calculate_final_results(self, counters):
        """
        Calculate final test results from counters.
        
        Args:
            counters (dict): Dictionary with test count data
            
        Returns:
            dict: Final test results with calculated passed tests
        """
        failed_total = counters['failures'] + counters['errors']
        passed_tests = max(0, counters['total_tests'] - failed_total - counters['skipped'])

        _log.info("Parsed test results - Total: %d, Passed: %d, Failed: %d, Errors: %d, Skipped: %d",
                  counters['total_tests'], passed_tests, counters['failures'],
                  counters['errors'], counters['skipped'])

        return {
            'total_tests': counters['total_tests'],
            'passed': passed_tests,
            'failed': counters['failures'],
            'skipped': counters['skipped'],
            'errors': counters['errors']
        }

    def _find_xml_file(self, log_path, run_name):
        """
        Find the XML file in the directory with the run name.
        
        Args:
            log_path (str): Base log directory path
            run_name (str): Specific run name subdirectory

        Returns:
            str: Path to the XML file if found, None otherwise
        """
        xml_path = os.path.join(log_path, run_name)

        if not os.path.exists(xml_path):
            _log.error("XML path does not exist: %s", xml_path)
            return None

        try:
            for root, _, files in os.walk(xml_path):
                for filename in files:
                    if filename.endswith("lisa.junit.xml"):
                        xml_file_path = os.path.join(root, filename)
                        _log.info("Found XML file at: %s", xml_file_path)
                        return xml_file_path
        except OSError as e:
            _log.error("Error while searching for XML file in %s: %s ", xml_path, str(e))

        _log.warning("No XML file with suffix 'lisa.junit.xml' found in %s", xml_path)
        return None
