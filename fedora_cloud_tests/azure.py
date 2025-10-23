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
import subprocess
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from fedora_image_uploader_messages.publish import AzurePublishedV1
from fedora_messaging import config, api
from fedora_messaging.exceptions import ValidationError, PublishTimeout, ConnectionException

from fedora_cloud_tests_messages.publish import AzureTestResults

from .trigger_lisa import LisaRunner

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

                # Generate SSH key pair for authentication
                private_key = self._generate_ssh_key_pair(log_path)

                config_params = {
                    "subscription": self.conf["subscription_id"],
                    "private_key": private_key,
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
                        self.publish_test_results(message, test_results)
                    else:
                        _log.error("Failed to parse test results, skipping image")
                else:
                    _log.error("LISA trigger failed with return code: %d", ret)
                # TemporaryDirectory automatically cleans up when exiting the context

        except OSError as e:
            _log.exception("Failed to trigger LISA: %s", str(e))

    def publish_test_results(self, message, test_results):
        """
        Publish the test results using AzureTestResults publisher.
        
        Following fedora-image-uploader patterns for message publishing.
        """
        try:
            # Extract metadata from original message
            body = self._build_result_message_body(message, test_results)

            # Create message instance with body (following fedora-messaging patterns)
            result_message = AzureTestResults(body=body)

            _log.info("Publishing test results for image: %s", body["image_id"])
            _log.debug("Full message body: %s", body)

            # Publish message using fedora-messaging API
            api.publish(result_message)

            _log.info("Successfully published test results for %s",
                     body["image_id"])

        except ValidationError as e:
            _log.error("Message validation failed: %s", str(e))
            _log.error("Invalid message body: %s", body)
        except (PublishTimeout, ConnectionException) as e:
            _log.error("Failed to publish test results due to connectivity: %s", str(e))
        except (OSError, KeyError, TypeError) as e:
            _log.error("Unexpected error during publishing: %s", str(e))

    def _build_result_message_body(self, original_message, test_results):
        """
        Build the message body for test results publication.
        
        Args:
            original_message: The original AzurePublishedV1 message
            test_results: Parsed test results dictionary
            
        Returns:
            dict: Message body for AzureTestResults
        """
        # Extract image metadata from original message
        body = original_message.body

        # Build the result message body following the schema
        result_body = {
            # Image identification
            "architecture": body["architecture"],
            "compose_id": body["compose_id"],
            "image_id": body["image_definition_name"],  # Use definition name as image ID
            "image_resource_id": body["image_resource_id"],

            # Detailed test lists
            "failed_tests": test_results.get("failed_tests", {"count": 0, "tests": {}}),
            "skipped_tests": test_results.get("skipped_tests", {"count": 0, "tests": {}}),
            "passed_tests": test_results.get("passed_tests", {"count": 0, "tests": {}})
        }

        return result_body

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

            # Extract individual test details
            test_details = self._extract_test_details(root)
            results = self._format_for_schema(test_details)

            return results

        except ET.ParseError as e:
            _log.error("Failed to parse XML file %s: %s", xml_file, str(e))
            return None

    def _extract_test_details(self, root):
        """
        Extract individual test case details from XML.
        
        Args:
            root: XML root element (either 'testsuites' or 'testsuite')
            
        Returns:
            dict: Dictionary with lists of test names categorized by status:
                  {'passed': [...], 'failed': [...], 'skipped': [...]}
        """
        test_details = {
            'passed': [],
            'failed': [],
            'skipped': []
        }

        test_suites = root.findall("testsuite") if root.tag == "testsuites" else [root]

        # Iterate through test suites and test cases
        for suite in test_suites:
            suite_name = suite.attrib.get('name')

            for testcase in suite.findall('testcase'):
                test_name = testcase.attrib.get('name')

                # Create a descriptive test identifier
                test_identifier = f"{suite_name}.{test_name}"
                test_time = testcase.attrib.get('time', '0.000')

                # Check test status and extract the message if available
                failure_elem = testcase.find('failure')
                error_elem = testcase.find('error')
                skipped_elem = testcase.find('skipped')

                # Log test details for failed, skipped and errored tests
                if failure_elem is not None:
                    failure_msg = failure_elem.attrib.get('message', 'Test case failed')
                    failure_msg = self._remove_html_tags(failure_msg)
                    traceback_msg = failure_elem.text or ''

                    # Combine failure_message and traceback if available
                    if traceback_msg.strip():
                        failure_msg = f"Summary: {failure_msg}\n\ Traceback: \n{traceback_msg.strip()}"
                    test_details['failed'].append((test_identifier, failure_msg))

                elif error_elem is not None:
                    error_msg = error_elem.attrib.get('message', 'Test error')
                    error_msg = self._remove_html_tags(error_msg)
                    traceback_msg = error_elem.text or ''
                    if traceback_msg.strip():
                        error_msg = f"Summary: {error_msg}\n\ Traceback: \n{traceback_msg.strip()}"
                    test_details['failed'].append((test_identifier, error_msg))

                elif skipped_elem is not None:
                    skip_msg = skipped_elem.attrib.get('message', 'Test skipped')
                    skip_msg = self._remove_html_tags(skip_msg)

                    # As there won't be any traceback will return the entire message
                    test_details['skipped'].append((test_identifier, skip_msg))

                else:
                    passed_msg = f"Test passed in {test_time} seconds."
                    test_details['passed'].append((test_identifier, passed_msg))

        _log.info("Extracted test details - Passed: %d, Failed: %d, Skipped: %d",
                  len(test_details['passed']),
                  len(test_details['failed']),
                  len(test_details['skipped']))

        return test_details

    def _remove_html_tags(self, msg):
        "Remove HTML tags from the message."
        return msg.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    def _format_for_schema(self, test_details=None):
        """
        Format the test details into the schema required for publishing.
        Args:
            test_details (dict): Dictionary with test name lists
            
        Returns:
            dict: Formatted test results for schema compliance
        """
        results = {}
        if test_details:
            for each_category in ['passed', 'failed', 'skipped']:
                test_list = test_details.get(each_category, [])
                tests_dict = {}
                for test_name, message in test_list:
                    tests_dict[test_name] = message

                results[f"{each_category}_tests"] = {
                    'count': len(test_list),
                    'tests': tests_dict
                }

        return results

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

    def _generate_ssh_key_pair(self, temp_dir):
        """
        Generate an SSH key pair for authentication.

        Args:
            temp_dir (str): Directory to store the generated key pair.

        Returns:
            str: Path to the private key file. or None if generation fails.
        """

        private_key_path = os.path.join(temp_dir, "id_ed25519")
        public_key_path = os.path.join(temp_dir, "id_ed25519.pub")

        try:
            # Generate SSH key pair using ssh-keygen
            cmd = ["ssh-keygen", "-t", "ed25519", "-f", private_key_path, "-N", ""]
            ret = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            _log.info("SSH key pair generated at: %s and %s", private_key_path, public_key_path)
            _log.debug("ssh-keygen output: %s", ret.stdout)

            # Verify the private key file is created
            if not os.path.exists(private_key_path):
                _log.error("SSH key generation succeeded but private key file was not found at: %s", private_key_path)
                return None

            # Set the permissions for the file
            os.chmod(private_key_path, 0o600)
            return private_key_path
        except (subprocess.CalledProcessError, OSError) as e:
            _log.error("Failed to generate SSH key pair: %s", str(e))
            return None
