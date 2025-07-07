# Fedora Nightly Cloud Image Testing on Azure
This repository automates the validation of Fedora nightly cloud images on Azure, initially focusing specifically on executing Tier 0 test cases using [LISA](https://github.com/microsoft/lisa) framework.

The workflow begins by consuming image publish messages using the fedora-messaging API. Once a message is received, the system automatically triggers the trigger_lisa module, which initializes and executes LISA tests on Azure infrastructure.

All dependencies required to run LISA and the associated tooling are installed using the install_dependencies.sh



## Pre-requisites:

1. Clone [LISA](https://github.com/microsoft/lisa) framework on the latest fedora and install it.
2. Use install_dependencies.sh to install all the dependent pacakges needed.
3. Login to azure using azure-cli
   `az login `

## How to Run Tests

### 1. Install Required Dependencies

First, install fedora-messaging using dnf:
```bash
sudo dnf install fedora-messaging
```

### 2. Clone and Setup LISA Repository

Clone the LISA repository:
```bash
git clone https://github.com/microsoft/lisa
cd lisa
```

Note: LISA must be run from within its own directory after cloning. You cannot run LISA from any other directory after installation.

### 3. Setup Fedora Messaging Configuration

Create the required configuration files and certificates following the [Fedora Messaging Quick Start Guide](https://fedora-messaging.readthedocs.io/en/stable/user-guide/quick-start.html):

1. Create the fedora.toml configuration file at `/etc/fedora-messaging/fedora.toml`
2. Obtain and configure your key certificate
3. Obtain and configure your CA certificate

### 4. Run the Test Consumer

From within the `lisa` directory, run the fedora-messaging consumer with the proper Python path:

```bash
cd lisa
PYTHONPATH=/home/user/fedora-nightly-azure-image-validation fedora-messaging --conf /etc/fedora-messaging/fedora.toml consume --callback="consume:AzurePublishedConsumer"
```

To reconsume messages (for testing/debugging):
```bash
cd lisa
PYTHONPATH=/home/user/fedora-nightly-azure-image-validation fedora-messaging --conf /etc/fedora-messaging/fedora.toml reconsume --callback="consume:AzurePublishedConsumer" "<message-id>"
```

### 5. Monitor Test Execution

The system will:
- Listen for Fedora nightly image publish messages
- Automatically trigger LISA tests when valid messages are received
- Execute Tier 0 test cases on Azure infrastructure
- Generate HTML output reports with test results
