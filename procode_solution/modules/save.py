#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: save.py
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


SAVE_COMMAND = {
    "cisco_ios": "write memory",
    "cisco_nxos": "copy running-config startup-config",
    "arista_eos": "write memory",
    "juniper_junos": "commit confirmed",
}


def save_scope(
    devices: list[dict],
    username: str,
    password: str,
    location: str,
    device_type: str = "cisco_ios",
    output_dir: str = "./output",
) -> str:
    """Save running config to startup across all devices in scope.

    Args:
        devices: List of dicts with 'hostname' and 'address'.
        username: SSH username.
        password: SSH password.
        location: Namespace/location label for output filename.
        device_type: Netmiko device type string.
        output_dir: Directory to write the results JSON.

    Returns:
        Path to the written results JSON file.
    """
    # TODO: iterate devices, call save_device(), aggregate results
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "location": location,
        "timestamp": timestamp,
        "devices": {},
    }

    for device in devices:
        results["devices"][device["hostname"]] = {
            "address": device["address"],
            "success": None,
            "output": None,
            "error": None,
        }

    output_path = os.path.join(output_dir, f"{location}_save_results_{timestamp}.json")
    with open(output_path, "w") as fh:
        json.dump(results, fh, indent=2)

    return output_path


def main():
    """
    Step 11 — Save / Commit Across Scope

    Uses Netmiko to write the running configuration to startup on all
    devices in scope.  Results are returned and written to
    output/<location>_save_results.json.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 11 - Save / Commit Across Scope",
                                     epilog="Usage: ' python save.py' ")
    arguments = parser.parse_args()
    main()
