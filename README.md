# Fedora Nightly Cloud Image Testing on Azure

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

This repository automates the validation of Fedora nightly cloud images on Azure infrastructure, executing Tier 1 test cases using the [LISA](https://github.com/microsoft/lisa) (Linux Integration Services Automation) framework.

## Table of Contents

- [Overview](#overview)
- [Supported Fedora Versions](#supported-fedora-versions)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Results](#results)
- [Troubleshooting](#troubleshooting)

## Overview

1. Consumes Fedora nightly image publish messages via fedora-messaging API
2. Automatically triggers LISA tests when valid messages are received
3. Executes Tier 1 test suites on Azure infrastructure
4. Generates HTML reports with test results and artifacts

```
fedora-messaging → AzurePublishedConsumer → LISA Tests → Test Reports
```

The workflow components:
- **Message Consumer**: Listens for `AzurePublishedV1` messages from Fedora's message bus
- **Image Validation**: Validates messages for supported Fedora versions and architectures
- **Test Orchestration**: Triggers LISA framework with Azure configurations
- **Result Collection**: Aggregates test results and generates reports

## Supported Fedora Versions

- **Fedora Cloud Rawhide** (x86_64, ARM64)
- **Fedora Cloud 41** (x86_64, ARM64)
- **Fedora Cloud 42** (x86_64, ARM64)


## Container

A Containerfile is provided. To run this application from a container, you must first build it:

```bash
podman build -t fedora-cloud-tests:latest .
```

Next, we need to configure authentication for our application in Azure.

1. Create a new key pair to authenticate to Azure:
   ```bash
   openssl req -x509 -new -nodes -sha256 -days 365 \
     -addext "extendedKeyUsage = clientAuth" \
     -subj "/CN=fedora-cloud-tests" \
     -newkey rsa:4096 \
     -keyout fedora-cloud-testing.key.pem \
     -out fedora-cloud-testing.cert.pem
   ```
2. Create an app registration in Azure:
   ```bash
   # Make note of the 'Id' and 'AppId' fields in the output as you'll need these later.
   az ad app create --display-name fedora-cloud-tests
   # Add our certificate to use when authenticating
   az ad app credential reset --id $APP_ID --append \
     --display-name "Fedora Cloud Test Certificate" \
     --cert "@./fedora-cloud-testing.cert.pem"
   az ad sp create --id $APP_ID
   # Note that this is an absurdly broad permission set; don't do this for production
   az role assignment create --assignee $APP_ID --role "Contributor" --scope "/subscriptions/<your sub>"
   ```
3. Add the key pair to podman/docker secrets
   ```bash
   cat fedora-cloud-testing.key.pem fedora-cloud-testing.cert.pem > fedora-cloud-testing.pem
   podman secret create fedora-cloud-testing-cert fedora-cloud-testing.pem
   ```

Finally, we're ready to run it. You'll need your Azure Directory (tenant) ID, as well as the 'AppId' from earlier.

```bash
podman run --rm -it -v "$(pwd)"/fedora-messaging.toml.example:/etc/fedora-messaging/config.toml:ro,Z \
  --secret source=fedora-cloud-testing-cert,type=mount \
  --env 'AZURE_CLIENT_CERTIFICATE_PATH=/run/secrets/fedora-cloud-testing-cert' \
  --env 'AZURE_TENANT_ID=<your tenant ID>' \
  --env 'AZURE_CLIENT_ID=<your AppId>' \
  fedora-cloud-tests:latest
```

## Prerequisites

### System Requirements
- **Operating System**: Latest Fedora Linux
- **Python**: 3.8 or higher
- **Architecture**: x86_64

### Required Accounts and Access
- Azure subscription with appropriate permissions
- Azure CLI installed and configured

### Dependencies
System dependencies are installed using the provided script.

## Installation

### 1. Install Dependencies

#### System Dependencies

```bash
chmod +x install_system_dependencies.sh
./install_system_dependencies.sh
```

This installs Git, GCC, Python 3, Azure CLI, QEMU/libvirt libraries, and fedora-messaging.

#### Python Dependencies

```bash
pip install fedora-messaging fedora-image-uploader-messages
```

**Note**: If not using a virtual environment, you may need to use `pip3` or `sudo pip3` depending on your system configuration.

### 2. Clone and Setup Repositories

#### Clone and Setup LISA Repository

```bash
git clone https://github.com/microsoft/lisa
cd lisa
pip install -e .
cd ..
```

**Important**: LISA tests must be executed from within the LISA repository directory.

#### Clone This Repository

```bash
git clone https://github.com/balakreddy/fedora-nightly-azure-image-validation
cd fedora-nightly-azure-image-validation
```

## Configuration

### Azure Authentication

1. **Login to Azure CLI**:
   ```bash
   az login
   ```

2. **Set Default Subscription** (if you have multiple):
   ```bash
   az account set --subscription "your-subscription-id"
   ```

3. **Verify Access**:
   ```bash
   az account show
   ```

### Fedora Messaging Setup

1. **Create Configuration Directory**:
   ```bash
   sudo mkdir -p /etc/fedora-messaging
   ```

2. **Download Required Certificates and Configuration**:
   ```bash
   # Download public certificates and configuration files
   sudo wget -O /etc/fedora-messaging/fedora-key.pem \
     https://raw.githubusercontent.com/fedora-infra/fedora-messaging/stable/configs/fedora-key.pem
   
   sudo wget -O /etc/fedora-messaging/fedora-cert.pem \
     https://raw.githubusercontent.com/fedora-infra/fedora-messaging/stable/configs/fedora-cert.pem
   
   sudo wget -O /etc/fedora-messaging/cacert.pem \
     https://raw.githubusercontent.com/fedora-infra/fedora-messaging/stable/configs/cacert.pem
   
   sudo wget -O /etc/fedora-messaging/fedora.toml \
     https://raw.githubusercontent.com/fedora-infra/fedora-messaging/stable/configs/fedora.toml
   ```

3. **Create Custom Configuration with Unique Queue**:
   ```bash
   # Generate unique queue name to avoid message conflicts
   sed -e "s/[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}/$(uuidgen)/g" \
       /etc/fedora-messaging/fedora.toml > my_config.toml
   ```

4. **Test Connection**:
   ```bash
   fedora-messaging --conf my_config.toml consume --help
   ```

### Application Configuration

Configuration parameters in `azure.py`:

```python
REGION = "westus3"  # Azure region for test execution
PRIVATE_KEY = "/path/to/your/ssh/private/key"  # SSH key for VM access
SUBSCRIPTION_ID = "your-azure-subscription-id"  # Your Azure subscription
```

**Security Note**: Store sensitive information securely using environment variables or Azure Key Vault.

## Usage

### Running the Consumer

1. **Navigate to LISA Directory**:
   ```bash
   cd lisa
   ```

2. **Start the Message Consumer**:
   ```bash
   PYTHONPATH=/path/to/fedora-nightly-azure-image-validation \
   fedora-messaging --conf my_config.toml consume
   ```

3. **For Testing/Debugging** - Reconsume Specific Messages:
   ```bash
   PYTHONPATH=/path/to/fedora-nightly-azure-image-validation \
   fedora-messaging --conf my_config.toml reconsume "<message-id>"
   ```

### Environment Variables

```bash
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_REGION="westus3"
export SSH_PRIVATE_KEY_PATH="/path/to/key"
export PYTHONPATH="/path/to/fedora-nightly-azure-image-validation"
```

## Results

Test results are stored in the LISA runtime directory as HTML reports. Logs are available in `consumer.log` and LISA's runtime directory.

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   ```
   Error: Failed to authenticate with Azure
   ```
   **Solution**: Run `az login` and verify your subscription access

2. **LISA Import Errors**
   ```
   ModuleNotFoundError: No module named 'lisa'
   ```
   **Solution**: Ensure you're running from within the LISA directory and PYTHONPATH is correctly set

3. **fedora-messaging Connection Issues**
   ```
   Connection refused to message broker
   ```
   **Solution**: Verify your `my_config.toml` configuration and certificates

4. **Permission Denied Errors**
   ```
   Permission denied: '/etc/fedora-messaging/fedora.toml'
   ```
   **Solution**: Check file permissions and ensure proper certificate setup

### Debug Mode

Enable debug logging:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Validation Steps

1. **Test fedora-messaging connection**:
   ```bash
   fedora-messaging --conf my_config.toml consume --help
   ```

2. **Verify LISA installation**:
   ```bash
   cd lisa && python -m lisa --help
   ```

3. **Check Azure connectivity**:
   ```bash
   az vm list --output table
   ```
