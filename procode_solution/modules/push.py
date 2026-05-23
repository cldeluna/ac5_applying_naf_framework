#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: push.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "5/22/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import netmiko
import os
import typing


def push_and_verify_device(
    hostname: str,
    address: str,
    username: str,
    password: str,
    config: str,
    acl_names: list[str],
    device_type: str = "cisco_ios",
    port: int = 22,
) -> dict[str, typing.Any]:
    """Connect once: capture pre-state, push config, capture post-state, diff.

    Args:
        hostname: Device hostname (used for labelling).
        address: Management IP address.
        username: SSH username.
        password: SSH password.
        config: Configuration string to push (send_config_set).
        acl_names: ACL names to show before and after the push.
        device_type: Netmiko device type string.
        port: SSH port number.

    Returns:
        Dict with 'hostname', 'success', 'pre_state', 'push_output',
        'post_state', 'diff', and 'error' keys.
    """
    conn_params = {
        "device_type": device_type,
        "host": address,
        "port": port,
        "username": username,
        "password": password,
    }
    config_lines = [line for line in config.splitlines() if line.strip()]
    result = {
        "hostname": hostname,
        "success": False,
        "pre_state": {},
        "pre_config": {},
        "push_output": "",
        "post_state": {},
        "diff": {},
        "error": None,
    }
    try:
        with netmiko.ConnectHandler(**conn_params) as conn:
            for acl in acl_names:
                result["pre_state"][acl] = conn.send_command(f"show ip access-lists {acl}")
                result["pre_config"][acl] = conn.send_command(
                    f"show running-config | section ip access-list extended {acl}"
                )
            result["push_output"] = conn.send_config_set(config_lines)
            for acl in acl_names:
                result["post_state"][acl] = conn.send_command(f"show ip access-lists {acl}")
        for acl in acl_names:
            pre_lines = set(result["pre_state"][acl].splitlines())
            post_lines = set(result["post_state"][acl].splitlines())
            result["diff"][acl] = {
                "added": sorted(post_lines - pre_lines),
                "removed": sorted(pre_lines - post_lines),
            }
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main():
    """
    Step 8 — Push Update to Scope

    Uses Netmiko to push the generated ACL configuration to all devices
    in the target location.  Results (success/failure per device) are
    returned and written to output/<location>_push_results.json.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 8 - Push Update to Scope",
                                     epilog="Usage: ' python push.py' ")
    arguments = parser.parse_args()
    main()
