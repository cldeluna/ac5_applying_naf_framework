#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: verify.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "5/22/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import json
import os
import datetime
import typing
import netmiko


def verify_scope(
    devices: list[dict],
    username: str,
    password: str,
    pre_snapshot_path: str,
    location: str,
    output_dir: str = "./output",
) -> str:
    """Verify post-change state across all devices in scope.

    Args:
        devices: List of dicts with 'hostname' and 'address'.
        username: SSH username.
        password: SSH password.
        pre_snapshot_path: Path to pre-change snapshot JSON.
        location: Namespace/location label for output filename.
        output_dir: Directory to write the verification report.

    Returns:
        Path to the written verification report JSON file.
    """
    # TODO: iterate devices, call verify_device(), call diff_state()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "location": location,
        "timestamp": timestamp,
        "pre_snapshot": pre_snapshot_path,
        "devices": {},
    }

    output_path = os.path.join(output_dir, f"{location}_verify_report_{timestamp}.json")
    with open(output_path, "w") as fh:
        json.dump(report, fh, indent=2)

    return output_path


def test_acl_counters(
    devices: list[dict],
    username: str,
    password: str,
    acl_name: str = "BASIC_DATA_SRVC_IN",
    port: int = 22,
) -> dict[str, typing.Any]:
    """Check ACL hit counters on all devices to confirm policy is active.

    Args:
        devices: List of dicts with 'hostname' and 'address'.
        username: SSH username.
        password: SSH password.
        acl_name: Name of the ACL to check counters on.
        port: SSH port number (default 22; pass net_device_port for non-standard).

    Returns:
        Dict mapping hostname to ACL counter output.
    """
    results = {}
    for device in devices:
        hostname = device["hostname"]
        address = device["address"]
        entry = {"hostname": hostname, "acl_name": acl_name, "output": "", "error": None}
        try:
            device_params = {
                "device_type": "cisco_ios",
                "host": address,
                "port": port,
                "username": username,
                "password": password,
            }
            with netmiko.ConnectHandler(**device_params) as conn:
                output = conn.send_command(f"show ip access-lists {acl_name}")
                entry["output"] = output
                print(f"\n  {hostname} — {acl_name}:")
                for line in output.splitlines():
                    print(f"    {line}")
        except Exception as exc:
            entry["error"] = str(exc)
            print(f"  ERROR on {hostname}: {exc}")
        results[hostname] = entry
    return results


def main():
    """
    Steps 9 & 10 — Verify Changes and Test Across Scope

    Step 9: Post-change verification — pulls the same show commands used in
            Step 5 and diffs the output against the pre-change snapshot.

    Step 10: Functional test — sends test traffic commands or checks ACL
             hit counters to confirm the policy is operating as expected.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Steps 9 & 10 - Verify and Test Across Scope",
                                     epilog="Usage: ' python verify.py' ")
    arguments = parser.parse_args()
    main()
