# Fedora Nightly Cloud Image Testing on Azure
This repository automates the validation of Fedora nightly cloud images on Azure, initially focusing specifically on executing Tier 0 test cases using [LISA](https://github.com/microsoft/lisa) framework.

The workflow begins by consuming image publish messages using the fedora-messaging API. Once a message is received, the system automatically triggers the trigger_lisa module, which initializes and executes LISA tests on Azure infrastructure.

All dependencies required to run LISA and the associated tooling are installed using the install_dependencies.sh



## Pre-requisites:

1. Clone [LISA](https://github.com/microsoft/lisa) framework on the latest fedora.
2. Use install_dependencies.sh to install all the dependent pacakges needed.
3. Login to azure using azure-cli
   `az login `

