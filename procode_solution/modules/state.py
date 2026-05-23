#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: state.py
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
import re
import typing
import netmiko


SHOW_COMMANDS = [
    "show running-config | section interface Vlan",
    "show ip access-lists",
]


def find_data_svis(running_config: str) -> list[dict]:
    """Parse running-config output to find Vlan SVIs with 'Data' in description.

    Args:
        running_config: Output of 'show running-config | section interface Vlan'.

    Returns:
        List of dicts with keys: interface, description, acl_in, acl_out.
    """
    svi_blocks = re.split(r'(?=^interface Vlan)', running_config, flags=re.MULTILINE)
    data_svis = []
    for block in svi_blocks:
        if not block.strip().startswith('interface Vlan'):
            continue
        desc_match = re.search(r'description\s+(.+)', block)
        if not desc_match or 'data' not in desc_match.group(1).lower():
            continue
        intf_match = re.match(r'interface\s+(Vlan\S+)', block)
        acl_in = re.search(r'ip access-group\s+(\S+)\s+in', block)
        acl_out = re.search(r'ip access-group\s+(\S+)\s+out', block)
        data_svis.append({
            'interface': intf_match.group(1) if intf_match else 'unknown',
            'description': desc_match.group(1).strip(),
            'acl_in': acl_in.group(1) if acl_in else None,
            'acl_out': acl_out.group(1) if acl_out else None,
        })
    return data_svis


def get_device_state(
    hostname: str,
    address: str,
    username: str,
    password: str,
    device_type: str = "cisco_ios",
    port: int = 22,
    commands: list[str] | None = None,
) -> dict[str, typing.Any]:
    """Connect to a device via Netmiko and capture show command output.

    Args:
        hostname: Device hostname (used for labelling).
        address: Management IP address.
        username: SSH username.
        password: SSH password.
        device_type: Netmiko device type string.
        port: SSH port number.
        commands: List of show commands to run. Defaults to SHOW_COMMANDS.

    Returns:
        Dict mapping each command to its raw output string.
    """
    result = {
        "hostname": hostname,
        "address": address,
        "data_svis": [],
        "acl_details": {},
        "running_config_svis": "",
        "error": None,
    }
    try:
        device_params = {
            "device_type": device_type,
            "host": address,
            "port": port,
            "username": username,
            "password": password,
        }
        with netmiko.ConnectHandler(**device_params) as conn:
            running_config = conn.send_command(
                "show running-config | section interface Vlan"
            )
            result["running_config_svis"] = running_config
            result["data_svis"] = find_data_svis(running_config)
            for svi in result["data_svis"]:
                for acl_name in [svi["acl_in"], svi["acl_out"]]:
                    if acl_name and acl_name not in result["acl_details"]:
                        result["acl_details"][acl_name] = conn.send_command(
                            f"show ip access-lists {acl_name}"
                        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def save_rollback_acls(device_state: dict, output_dir: str, location: str) -> list[str]:
    """Save the current ACL text for each ACL found to a rollback file.

    Args:
        device_state: Dict returned by get_device_state().
        output_dir: Directory to write rollback files.
        location: Namespace/location label for filenames.

    Returns:
        List of paths to written rollback files.
    """
    saved = []
    hostname = device_state.get("hostname", "unknown")
    for acl_name, acl_text in device_state.get("acl_details", {}).items():
        filename = f"{location}_{hostname}_{acl_name}_rollback.txt"
        path = os.path.join(output_dir, filename)
        with open(path, "w") as fh:
            fh.write(acl_text)
        saved.append(path)
    return saved


def print_device_summary(device_state: dict) -> None:
    """Print Data SVIs and ACL status found on a device.

    Args:
        device_state: Dict returned by get_device_state().
    """
    hostname = device_state.get("hostname", "unknown")
    data_svis = device_state.get("data_svis", [])
    acl_details = device_state.get("acl_details", {})

    if not data_svis:
        print(f"  {hostname}: no Data SVIs found")
        return

    print(f"  {hostname}: {len(data_svis)} Data SVI(s) found")
    for svi in data_svis:
        print(f"    - {svi['interface']}  ({svi['description']})")
        if svi["acl_in"]:
            print(f"      ACL inbound : {svi['acl_in']}")
        if svi["acl_out"]:
            print(f"      ACL outbound: {svi['acl_out']}")
        if not svi["acl_in"] and not svi["acl_out"]:
            print(f"      ACL         : none applied")

    if acl_details:
        print(f"\n    Current ACL(s) on {hostname}:")
        for name, text in acl_details.items():
            print(f"\n      --- {name} ---")
            for line in text.splitlines():
                print(f"      {line}")


def capture_location_state(
    devices: list[dict],
    username: str,
    password: str,
    output_dir: str = "./output",
    location: str = "unknown",
    port: int = 22,
) -> str:
    """Capture pre-change state for all devices at a location.

    Args:
        devices: List of dicts with 'hostname' and 'address' keys.
        username: SSH username.
        password: SSH password.
        output_dir: Directory to write snapshot JSON.
        location: Namespace/location label used in the output filename.
        port: SSH port number.

    Returns:
        Path to the written snapshot file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot = {
        "location": location,
        "timestamp": timestamp,
        "devices": {},
    }
    rollback_files = []

    for device in devices:
        print(f"\n  Connecting to {device['hostname']} ({device['address']}:{port})...")
        device_state = get_device_state(
            device["hostname"], device["address"], username, password, port=port
        )
        snapshot["devices"][device["hostname"]] = device_state
        if device_state.get("error"):
            print(f"  ERROR: {device_state['error']}")
        else:
            print_device_summary(device_state)
            saved = save_rollback_acls(device_state, output_dir, location)
            rollback_files.extend(saved)

    if rollback_files:
        print("\n  Rollback ACL files saved:")
        for f in rollback_files:
            print(f"    {f}")

    output_path = os.path.join(output_dir, f"{location}_prechange_state_{timestamp}.json")
    with open(output_path, "w") as fh:
        json.dump(snapshot, fh, indent=2)

    return output_path


def main():
    """
    Step 5 — Check and Document Current State

    Uses Netmiko to pull show commands from each device in the target location
    and parses the output with TextFSM to produce a structured pre-change
    snapshot saved to output/<location>_prechange_state.json.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 5 - Check and Document Current State",
                                     epilog="Usage: ' python state.py' ")
    arguments = parser.parse_args()
    main()
