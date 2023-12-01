# Routing

This package contains the OTP server and the OTP client. The OTP server is a Java application that can be run from the
command line. The OTP client is a Python package that can be used to communicate with the OTP server.

We also include a `otp_builder.py` file that downloads OTP and resource files and builds the OTP graph.
The `vc_router.py`
contains code to pull virtual commuter jobs from the database, route them, and store the results in the database.

## Usage

For usage of the `otp.py` client, see [here](otp.md).

You can run the VC Router like this:

```bash
python routing/vc_router.py 35e58b29-ea03-4b34-b533-05c848b9fb31
```

The uuid here is the sim-id. You can get this ID in the database or when creating a simulation.

## What will happen

- It will add any virtual-commuter jobs that are not yet in the database
- It will download OTP to routing/bin
- It will download the resource files to routing/data
- It will build the OTP graph if it does not exist yet
- It will start the OTP server
- It will route the virtual commuter jobs that are pending and in the database
