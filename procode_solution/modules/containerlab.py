#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: containerlab.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "5/22/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import os
import re
import yaml


_HOSTNAME_ROLE_HINTS = [
    (r"-cs\d", "core"),
    (r"-ds\d", "distribution"),
    (r"-as\d", "access"),
    (r"-sw\d", "access"),
    (r"-fwl", "firewall"),
    (r"-wlc", "wlc"),
    (r"spine", "spine"),
    (r"leaf", "leaf"),
    (r"core", "core"),
    (r"dist", "distribution"),
    (r"-c\d", "core"),
    (r"-d\d", "distribution"),
]


CLAB_TEMPLATE = {
    "name": None,
    "topology": {
        "nodes": {},
        "links": [],
    },
}


def build_topology(
    location: str,
    device: dict,
    image: str = "vrnetlab/vr-csr:17.03.01a",
    output_dir: str = "./output",
) -> str:
    """Generate a single-node Containerlab topology for lab validation.

    Args:
        location: Namespace/location name — used in the topology name.
        device: Dict with 'hostname' and 'address' for the representative node.
        image: Container image to use for the lab node.
        output_dir: Directory to write the topology file.

    Returns:
        Path to the written topology YAML file.
    """
    # TODO: extend to support multi-vendor images based on device naming conventions
    topology = {
        "name": f"lab-{location}",
        "topology": {
            "nodes": {
                device["hostname"]: {
                    "kind": "vr-csr",
                    "image": image,
                    "mgmt-ipv4": device["address"],
                }
            },
            "links": [],
        },
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{location}_clab_topology.yml")
    with open(output_path, "w") as fh:
        yaml.dump(topology, fh, default_flow_style=False, sort_keys=False)

    return output_path


def _hint_role(hostname: str) -> str:
    """Infer role from hostname patterns as a fallback for missing role fields."""
    h = hostname.lower()
    for pattern, role in _HOSTNAME_ROLE_HINTS:
        if re.search(pattern, h):
            return role
    return "unknown"


def get_representative_device(devices: list[dict]) -> dict:
    """Select a single representative device from the location device list.

    Prefers core, then distribution, then spine.  Uses the explicit 'role'
    field from inventory.yml; falls back to hostname pattern inference when
    the field is absent.

    Args:
        devices: List of dicts with 'hostname', 'address', and optional 'role'.

    Returns:
        A single device dict.
    """
    for preferred_role in ("core", "distribution", "spine"):
        for device in devices:
            role = device.get("role") or _hint_role(device.get("hostname", ""))
            if role == preferred_role:
                return device
    return devices[0]


def main():
    """
    Step 7 — Lab it up (Scale = 1)

    Generates a Containerlab topology YAML file with a single device
    representative of the target location for pre-push ACL validation.
    The topology is written to output/<location>_clab_topology.yml.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 7 - Lab it up (Scale = 1)",
                                     epilog="Usage: ' python containerlab.py' ")
    arguments = parser.parse_args()
    main()
