#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: change_record.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "5/22/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import datetime
import os


def build_change_record(
    location: str,
    devices: list[dict],
    impact: dict,
    acl_artifact: str,
    engine: str,
    output_dir: str = "./output",
    data_svis: list[dict] | None = None,
) -> str:
    """Build change record text and save to file.

    Args:
        location: Namespace/location name from inventory.
        devices: List of dicts with 'hostname' and 'address'.
        impact: Dict from impact.quantify_impact().
        acl_artifact: Rendered ACL configuration string.
        engine: 'jinja2' or 'aerleon' — records which engine was used.
        output_dir: Directory to write the CR text file.
        data_svis: List of Data SVI dicts from pre-change state snapshot.

    Returns:
        Path to the written change record file.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    svi_lines = ""
    if data_svis:
        for svi in data_svis:
            acl_in = svi.get("acl_in") or "none"
            acl_out = svi.get("acl_out") or "none"
            svi_lines += (
                f"  - {svi.get('hostname', '?')}  {svi.get('interface', '?')}"
                f"  ({svi.get('description', '')})"
                f"  ACL-in: {acl_in}  ACL-out: {acl_out}\n"
            )
    else:
        svi_lines = "  (none identified)"

    scope_lines = "\n".join(f"  - {s}" for s in impact.get("scope", []))
    impact_lines = "\n".join(f"  - {s}" for s in impact.get("service_impact", []))
    device_lines = "\n".join(
        f"  - {d['hostname']} ({d['address']})" for d in devices
    )

    cr_text = f"""CHANGE RECORD
=============
Generated  : {timestamp}
Location   : {location}
Policy     : {impact.get('policy_name', 'BASIC_SERVICES_POLICY')}
Engine     : {engine}

SCOPE
-----
{scope_lines}

SERVICE IMPACT
--------------
{impact_lines}

DEVICES IN SCOPE
----------------
{device_lines}

TARGET DATA SVIs
----------------
{svi_lines}
CONFIGURATION ARTIFACT
----------------------
{acl_artifact}

INSTRUCTIONS
------------
1. Review the configuration artifact above.
2. Validate in lab (Scale=1) before pushing to scope.
3. Submit this text to the change management system.
4. Attach pre-change state snapshot from output/.
"""

    os.makedirs(output_dir, exist_ok=True)
    safe_ts = timestamp.replace(":", "").replace(" ", "_")
    output_path = os.path.join(output_dir, f"{location}_change_record_{safe_ts}.txt")
    with open(output_path, "w") as fh:
        fh.write(cr_text)

    return output_path


def main():
    """
    Step 6 — Create Change Record (CR)

    Generates the text body for a change ticket based on the impact summary,
    target location, device list, and generated ACL artifact.  Output is
    printed to stdout and saved to output/<location>_change_record.txt for
    manual submission to the ticketing system.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 6 - Create Change Record",
                                     epilog="Usage: ' python change_record.py' ")
    arguments = parser.parse_args()
    main()
