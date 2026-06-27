# Anubis-Support

Tools for Anubis support on Koozali infrastructure.

# Anubis Setup and Test Scripts

This repository contains two companion scripts for deploying and validating an Anubis bot-protection setup. The shell script creates the service configuration, and the Python script runs end-to-end checks against the public site and the local Anubis instance [file:1][file:2].

## What’s included

- `make-anubis-2.sh` sets up an Anubis service, writes policy and environment files, and creates a systemd unit for the instance [file:1].
- `anubis_test_v2.py` exercises the deployed setup with HTTP requests, checks expected status codes and body content, and writes results to CSV [file:2].

## Requirements

- Linux system with `bash`, `systemd`, and standard core utilities [file:1].
- An installed Anubis binary at `/usr/sbin/anubis` [file:1].
- Python 3 for the test runner [file:2].
- Network access to the target service and the public URL being tested [file:2].

## Script overview

### `make-anubis-2.sh`

The setup script expects a service name and a port, then validates the inputs before generating configuration files under `/etc/anubis` and a systemd service under `/etc/systemd/system` [file:1]. It also creates an `anubis` system user if needed, assigns permissions, and defines a policy that allows normal browsers while challenging unknown clients [file:1]. The script also calculates a metrics port by adding `10000` to the service port and fails safely if that would exceed the valid port range [file:1].

### `anubis_test_v2.py`

The test script targets both the local Anubis listener and the public site, using a set of named test cases with headers, expected statuses, and body assertions [file:2]. It captures response status, selected headers, timing, and a body preview, then writes all results into `anubis_test_results.csv` [file:2]. The tests include browser allowance, bot challenge behavior, a probe request, and a negative path check [file:2].

## Usage

### 1. Create the Anubis service

Run the setup script with a service name and port, then optionally override the target and difficulty settings [file:1].

```bash
sudo ./make-anubis-2.sh <name> <port> [--target <url>] [--difficulty <1-10>]
```

Example:

```bash
sudo ./make-anubis-2.sh mail 3002 --target https://mail.bjsystems.co.uk:443 --difficulty 3
```

### 2. Run the test suite

After deployment, run the Python test script to validate behavior and generate a CSV report [file:2].

```bash
python3 anubis_test_v2.py
```

## Output

The test runner appends rows to `anubis_test_results.csv`, including timestamp, test name, URL, status, latency, response length, headers, pass/fail state, failure reason, and a response body preview [file:2].

## Notes

- The setup script is opinionated and writes fixed paths and defaults, so review the generated policy before using it in production [file:1].
- The test script is intended for repeated verification and may append to an existing CSV file rather than overwriting it [file:2].
- Some configuration values, such as hostnames, ports, and the public base URL, are hard-coded in the test script and may need editing for a different environment [file:2].