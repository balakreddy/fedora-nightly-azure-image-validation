# Fedora Nightly Cloud Image Testing on Azure
This repository automates the validation of Fedora nightly cloud images on Azure, initially focusing specifically on executing Tier 0 test cases using [LISA](https://github.com/microsoft/lisa) framework.

The workflow begins by consuming image publish messages using the fedora-messaging API. Once a message is received, the system automatically triggers the trigger_lisa module, which initializes and executes LISA tests on Azure infrastructure.

All dependencies required to run LISA and the associated tooling are installed using the install_dependencies.sh



## Pre-requisites:

1. Clone [LISA](https://github.com/microsoft/lisa) framework on the latest fedora.
2. Use install_dependencies.sh to install all the dependent pacakges needed.
3. Login to azure using azure-cli
   `az login `

## Workflow overview

#### Consume Fedora Messaging
- Uses fedora-messaging API to listen for new Fedora nightly image notifications.
- Triggers test execution once a valid message is received.

#### Trigger LISA tests
- Initializes and executes LISA using:
   - Image reference from the received message
   - Azure subscription details
- Current plan is to run only Tier 0 test cases

#### Results 
- Share the output of lisa execution from html file as is.
