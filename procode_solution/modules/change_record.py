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


_PORT_NAMES = {
    "eq www": "eq 80",
    "eq http": "eq 80",
    "eq domain": "eq 53",
    "eq bootps": "eq 67",
    "eq bootpc": "eq 68",
    "eq ftp": "eq 21",
    "eq ssh": "eq 22",
    "eq telnet": "eq 23",
    "eq smtp": "eq 25",
    "eq https": "eq 443",
}


def _normalize_ace(line: str) -> str:
    """Normalize named port keywords to numeric so comparisons are semantic."""
    result = line.lower().strip()
    for named, numeric in _PORT_NAMES.items():
        result = result.replace(named, numeric)
    return result


def _rules_from_show(acl_text: str) -> list:
    """Extract permit/deny lines from 'show ip access-lists' output, stripping sequence numbers."""
    rules = []
    for line in acl_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("extended ip"):
            continue
        parts = stripped.split(None, 1)
        if parts and parts[0].isdigit() and len(parts) > 1:
            stripped = parts[1]
        if stripped.startswith("permit") or stripped.startswith("deny"):
            rules.append(stripped)
    return rules


def _rules_from_artifact(artifact: str, acl_name: str) -> list:
    """Extract permit/deny lines from the rendered ACL artifact for one named ACL."""
    rules = []
    in_acl = False
    for line in artifact.splitlines():
        stripped = line.strip()
        if stripped == f"ip access-list extended {acl_name}":
            in_acl = True
            continue
        if in_acl:
            if stripped == "exit" or stripped.startswith("no ip access-list"):
                in_acl = False
                continue
            if stripped.startswith("ip access-list") and acl_name not in stripped:
                in_acl = False
                continue
            if stripped.startswith("permit") or stripped.startswith("deny"):
                rules.append(stripped)
    return rules


def _acl_names_from_artifact(artifact: str) -> list:
    """Return ordered list of ACL names defined in the artifact."""
    names = []
    for line in artifact.splitlines():
        if line.startswith("ip access-list extended "):
            name = line.replace("ip access-list extended ", "").strip()
            if name not in names:
                names.append(name)
    return names


def _build_delta_section(snapshot: dict, acl_artifact: str) -> str:
    """Build the CURRENT STATE vs. PROPOSED CHANGES block for the change record.

    For each device in the snapshot:
    - Devices with no Data SVIs: explain WHY (SVI exists but missing 'data' description)
      so the engineer knows what to fix if that device should be in scope.
    - Devices with Data SVIs: show per-ACL REMOVED / ADDED / UNCHANGED ACE counts
      with port-name normalization so semantic equivalence is detected correctly.

    Args:
        snapshot: Pre-change state dict (loaded from the JSON snapshot file).
        acl_artifact: Rendered ACL configuration string from the artifact engine.

    Returns:
        Formatted string block ready to embed in the change record.
    """
    if not snapshot or "devices" not in snapshot:
        return ""

    acl_names = _acl_names_from_artifact(acl_artifact)

    out = [
        "",
        "CURRENT STATE vs. PROPOSED CHANGES",
        "-----------------------------------",
    ]

    for hostname, dev in snapshot.get("devices", {}).items():
        out.append(f"\ndevice: {hostname} ({dev.get('address', '?')})")
        data_svis = dev.get("data_svis", [])

        if not data_svis:
            running = dev.get("running_config_svis", "")
            applied = [n for n in acl_names if n in running]
            if applied:
                out.append("  WARNING: No Data SVIs detected — this device will NOT receive the new ACL.")
                out.append("  The following ACLs are applied on this device but no SVI has 'data' in its description:")
                for n in applied:
                    out.append(f"    {n}")
                out.append("  ACTION: Add 'data' to the SVI description (e.g. 'description <name> data') to include it.")
            else:
                out.append("  No Data SVIs and no matching ACLs detected — no changes will be applied.")
            continue

        for svi in data_svis:
            out.append(f"  SVI: {svi.get('interface')} ({svi.get('description', '')})")

        acl_details = dev.get("acl_details", {})
        for acl_name in acl_names:
            current_rules = _rules_from_show(acl_details.get(acl_name, "")) if acl_name in acl_details else []
            proposed_rules = _rules_from_artifact(acl_artifact, acl_name)

            cur_norm = {_normalize_ace(r): r for r in current_rules}
            prop_norm = {_normalize_ace(r): r for r in proposed_rules}

            removed = [cur_norm[k] for k in cur_norm if k not in prop_norm]
            added = [prop_norm[k] for k in prop_norm if k not in cur_norm]
            unchanged = sum(1 for k in cur_norm if k in prop_norm)

            out.append(f"\n  ACL: {acl_name}")
            if not removed and not added:
                out.append(f"    NO CHANGES — proposed ACL is semantically identical to deployed ACL.")
                out.append(f"    ({unchanged} ACE(s) unchanged; named ports normalized for comparison)")
            else:
                if removed:
                    out.append(f"    REMOVED ({len(removed)} ACE(s)):")
                    for r in removed:
                        out.append(f"      - {r}")
                if added:
                    out.append(f"    ADDED ({len(added)} ACE(s)):")
                    for a in added:
                        out.append(f"      + {a}")
                if unchanged:
                    out.append(f"    UNCHANGED: {unchanged} ACE(s)")
                out.append("    NOTE: named ports (eq www, eq domain, eq bootps/bootpc) normalized")
                out.append("          to numeric (eq 80, eq 53, eq 67/68) before comparison.")

    return "\n".join(out)


def build_change_record(
    location: str,
    devices: list[dict],
    impact: dict,
    acl_artifact: str,
    engine: str,
    output_dir: str = "./output",
    data_svis: list[dict] | None = None,
    pre_change_snapshot: dict | None = None,
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
        pre_change_snapshot: Full snapshot dict from state.capture_location_state();
            when provided a CURRENT STATE vs. PROPOSED CHANGES diff is appended.

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

    delta_section = _build_delta_section(pre_change_snapshot, acl_artifact) if pre_change_snapshot else ""

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
{delta_section}

INSTRUCTIONS
------------
1. Review the CURRENT STATE vs. PROPOSED CHANGES section above before proceeding.
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
