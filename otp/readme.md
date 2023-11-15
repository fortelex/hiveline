# Routing

This package contains the OTP server and the OTP client. The OTP server is a Java application that can be run from the
command line. The OTP client is a Python package that can be used to communicate with the OTP server.

We also include a `otp_builder.py` file that downloads OTP and resource files and builds the OTP graph.
The `vc_router.py`
contains code to pull virtual commuter jobs from the database, route them, and store the results in the database.

## Pre-requisites

- Java 11 or higher
- Python 3.10 or higher
- Upper database setup (TODO add database setup guide)
- Database credentials as environment variables. See [here](../mongo/readme.md) for more information.

## Installation

Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

For usage of the `otp.py` client, see [here](otp.md).

To use the VC Router, you need to add the root of the repository to your PYTHONPATH. For example, if this repository
is located in `C:\Users\user\Documents\upper-codagon`, you can add it to your PYTHONPATH by running this in powershell:

```bash
$env:PYTHONPATH += ";C:\Users\user\Documents\upper-codagon"
```

Or in linux:

```bash
export PYTHONPATH=$PYTHONPATH:/home/user/upper-codagon
```

Then, you can run the VC Router:

```bash
python otp/vc_router.py 35e58b29-ea03-4b34-b533-05c848b9fb31
```

The uuid here is the Virtual Commuter Set ID. You can find this ID in the database.

## What will happen

- It will add any virtual-commuter jobs that are not yet in the database
- It will download OTP to otp/bin
- It will download the resource files to otp/data
- It will build the OTP graph if it does not exist yet
- It will start the OTP server
- It will route the virtual commuter jobs that are pending and in the database
