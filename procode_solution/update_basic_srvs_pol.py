#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: update_basic_srvs_pol.py
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
import dotenv
import ipaddress
import jinja2
import json
import os
import re
import subprocess
import sys
import yaml

import modules.impact as impact
import modules.state as state
import modules.change_record as change_record
import modules.push as push
import modules.verify as verify
import modules.save as save


_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.normpath(os.path.join(_HERE, "..", ".env"))
DEFINITIONS_DIR = os.path.normpath(os.path.join(_HERE, "..", "acl_aerleon", "def"))
POLICY_FILE = os.path.normpath(os.path.join(
    _HERE, "..", "acl_aerleon", "policies", "pol", "basic_services_monolithic.pol.yaml"
))
INVENTORY_FILE = os.path.join(_HERE, "inventory.yml")
TEMPLATES_DIR = os.path.join(_HERE, "templates")
OUTPUT_DIR = os.path.join(_HERE, "output")
ACL_NAME = "BASIC_DATA_SRVC_IN"
ACL_NAME_OUT = "BASIC_DATA_SRVC_OUT"
L3_ROLES = {"core", "distribution", "spine", "leaf"}

_HOSTNAME_ROLE_PATTERNS = [
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
    (r"access", "access"),
    (r"-c\d", "core"),
    (r"-d\d", "distribution"),
    (r"-a\d", "access"),
    (r"-f\d", "firewall"),
]


def build_apply_commands(svis: list[dict]) -> str:
    """Generate interface-level commands to apply the standard ACLs to Data SVIs.

    Always applies both ACL_NAME (inbound) and ACL_NAME_OUT (outbound)
    unconditionally — the goal is standardisation regardless of what was
    previously configured.

    Args:
        svis: List of SVI dicts with 'interface', 'acl_in', 'acl_out' keys.

    Returns:
        IOS config snippet string with interface commands.
    """
    lines = ["!", "! Apply Standard ACLs to Data SVIs", "!"]
    for svi in svis:
        lines.append(f"interface {svi['interface']}")
        lines.append(f" ip access-group {ACL_NAME} in")
        lines.append(f" ip access-group {ACL_NAME_OUT} out")
        lines.append(" exit")
    lines.append("!")
    return "\n".join(lines)


def build_rollback_config_for_device(
    svis: list[dict],
    pre_config: dict[str, str],
    acl_names: list[str],
) -> str:
    """Generate IOS rollback commands for a single device.

    Handles three scenarios per ACL / interface:
      1. Same ACL name updated — restore original content; interface untouched.
      2. Different ACL name was present — swap interface binding back, remove new ACL.
      3. No prior ACL — remove new ACL and its interface binding entirely.

    Args:
        svis: SVI dicts with 'interface', 'acl_in', 'acl_out' keys
              (values are the ACL names that were on the device *before* the push).
        pre_config: Dict keyed by ACL name containing the running-config section
                    captured before the push (empty string if ACL was absent).
        acl_names: Ordered list [acl_in_name, acl_out_name] used in this push.

    Returns:
        IOS config snippet string.
    """
    acl_in_name, acl_out_name = acl_names[0], acl_names[1] if len(acl_names) > 1 else None
    lines = ["!", "! Rollback", "!"]

    for svi in svis:
        orig_in = svi.get("acl_in", "")
        orig_out = svi.get("acl_out", "")
        iface_lines = []
        if orig_in and orig_in != acl_in_name:
            iface_lines.append(f" no ip access-group {acl_in_name} in")
            iface_lines.append(f" ip access-group {orig_in} in")
        elif not orig_in:
            iface_lines.append(f" no ip access-group {acl_in_name} in")
        if acl_out_name:
            if orig_out and orig_out != acl_out_name:
                iface_lines.append(f" no ip access-group {acl_out_name} out")
                iface_lines.append(f" ip access-group {orig_out} out")
            elif not orig_out:
                iface_lines.append(f" no ip access-group {acl_out_name} out")
        if iface_lines:
            lines.append(f"interface {svi['interface']}")
            lines.extend(iface_lines)
            lines.append(" exit")

    lines.append("!")
    for acl in acl_names:
        orig_cfg = pre_config.get(acl, "").strip()
        lines.append(f"no ip access-list extended {acl}")
        if orig_cfg:
            lines.append(orig_cfg)
    lines.append("!")
    return "\n".join(lines)


def prompt_rollback_or_continue(label: str) -> bool:
    """Prompt the user to rollback or continue.

    Args:
        label: Context label shown in the prompt (e.g. 'clab' or 'production').

    Returns:
        True if the user chooses rollback, False to continue.
    """
    while True:
        choice = input(
            f"\n[{label}] Type 'rollback' to undo changes, or press Enter to continue: "
        ).strip().lower()
        if choice == "rollback":
            return True
        if choice == "":
            return False
        print("  Please type 'rollback' or press Enter to continue.")


def load_inventory(inventory_file: str) -> dict:
    """Load inventory.yml and return the full namespace dict."""
    with open(inventory_file) as fh:
        return yaml.safe_load(fh) or {}


def infer_role_from_hostname(hostname: str) -> str:
    """Infer device role from hostname naming convention.

    Used as a fallback when a device in inventory.yml has no 'role' field.
    Patterns are checked in order from most specific to least specific.

    Args:
        hostname: Device hostname string.

    Returns:
        Role string (e.g. 'core', 'distribution', 'access') or 'unknown'.
    """
    h = hostname.lower()
    for pattern, role in _HOSTNAME_ROLE_PATTERNS:
        if re.search(pattern, h):
            return role
    return "unknown"


def get_devices(inventory: dict, location: str) -> list[dict]:
    """Return only L3 devices for a given namespace/location.

    Filters to devices whose role is in L3_ROLES (core, distribution,
    spine, leaf).  Role is taken from the explicit 'role' field in
    inventory.yml when present; otherwise it is inferred from the hostname
    using _HOSTNAME_ROLE_PATTERNS.  Devices whose role cannot be determined
    are included with a warning.  Non-L3 devices are skipped and logged.

    Args:
        inventory: Full inventory dict.
        location: Namespace key to look up.

    Returns:
        List of L3 device dicts with 'hostname', 'address', and 'role'.

    Raises:
        SystemExit: If location is not found in inventory.
    """
    if location not in inventory:
        available = ", ".join(inventory.keys())
        print(f"ERROR: location '{location}' not found in inventory.")
        print(f"Available locations: {available}")
        sys.exit(1)
    all_devices = inventory[location]
    l3_devices = []
    skipped = []
    for device in all_devices:
        explicit_role = device.get("role", "")
        if explicit_role:
            effective_role = explicit_role
            role_source = "inventory"
        else:
            effective_role = infer_role_from_hostname(device["hostname"])
            role_source = "inferred"
        if effective_role in L3_ROLES:
            if role_source == "inferred":
                print(f"  INFO: {device['hostname']}: no 'role' field — role '{effective_role}' inferred from hostname.")
            l3_devices.append(device)
        elif effective_role == "unknown":
            print(f"  WARNING: {device['hostname']}: no role field and hostname gives no clue — including by default.")
            l3_devices.append(device)
        else:
            skipped.append((device, effective_role, role_source))
    if skipped:
        print(f"\nSkipping {len(skipped)} non-L3 device(s) at {location} (not eligible for SVI ACL updates):")
        for d, role, source in skipped:
            suffix = " — inferred from hostname" if source == "inferred" else ""
            print(f"  - {d['hostname']} (role: {role}{suffix})")
    return l3_devices


def build_artifact_jinja2(definitions_dir: str, output_dir: str) -> str:
    """Step 3 (Jinja2 path) — render ACL from definitions and template.

    Args:
        definitions_dir: Path to aerleon def/ directory.
        output_dir: Directory to write the rendered ACL.

    Returns:
        Rendered ACL configuration string.
    """
    defs = impact.load_definitions(definitions_dir)

    def host_ip(cidr):
        return str(ipaddress.ip_interface(cidr).ip)

    dns_servers = [
        {"address": host_ip(e["address"])}
        for e in defs.get("networks", {}).get("DNS_SERVERS", {}).get("values", [])
        if "address" in e
    ]
    dhcp_servers = [
        {"address": host_ip(e["address"])}
        for e in defs.get("networks", {}).get("DHCP_SERVERS", {}).get("values", [])
        if "address" in e
    ]
    web_servers = [
        {"address": host_ip(e["address"])}
        for e in defs.get("networks", {}).get("WEB_SERVERS", {}).get("values", [])
        if "address" in e
    ]
    rfc1918_networks = [
        {
            "network": str(ipaddress.ip_network(e["address"], strict=False).network_address),
            "wildcard": str(ipaddress.ip_network(e["address"], strict=False).hostmask),
        }
        for e in defs.get("networks", {}).get("RFC1918", {}).get("values", [])
        if "address" in e
    ]

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("basic_services_acl.j2")
    rendered = template.render(
        dns_servers=dns_servers,
        dhcp_servers=dhcp_servers,
        web_servers=web_servers,
        rfc1918_networks=rfc1918_networks,
    )

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "basic_services_acl.txt")
    with open(out_path, "w") as fh:
        fh.write(rendered)

    return rendered


def build_artifact_aerleon(policy_file: str, output_dir: str) -> str:
    """Step 3 (aerleon path) — run aclgen and return generated config.

    Args:
        policy_file: Path to the aerleon policy YAML file.
        output_dir: Directory to write generated files.

    Returns:
        Path to the aerleon-generated output file.
    """
    abs_policy_file = os.path.abspath(policy_file)
    base_dir = os.path.normpath(
        os.path.join(os.path.dirname(abs_policy_file), "..", "..")
    )
    result = subprocess.run(
        ["aclgen", "--base_directory", base_dir, "--policy_file", abs_policy_file],
        capture_output=True,
        text=True,
        cwd=base_dir,
    )
    if result.returncode != 0:
        print(f"aclgen stderr:\n{result.stderr}")
        raise RuntimeError(f"aclgen failed (exit {result.returncode})")

    acl_filename = os.path.basename(abs_policy_file).replace(".yaml", "") + ".acl"
    rel_path = os.path.relpath(abs_policy_file, base_dir)
    output_subdir = os.path.dirname(os.path.dirname(rel_path))
    acl_path = os.path.join(base_dir, output_subdir, acl_filename)

    with open(acl_path) as fh:
        content = fh.read()

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, acl_filename)
    with open(out_path, "w") as fh:
        fh.write(content)

    return content


def print_push_result(result: dict) -> None:
    """Print a structured push_and_verify_device() result to stdout."""
    hostname = result["hostname"]
    if result["error"]:
        print(f"  [{hostname}] ERROR: {result['error']}")
        return
    for acl in result["pre_state"]:
        pre = result["pre_state"][acl].strip() or "(not present)"
        post = result["post_state"][acl].strip() or "(not present)"
        added = result["diff"][acl]["added"]
        removed = result["diff"][acl]["removed"]
        print(f"\n  [{hostname}] PRE  — {acl}:")
        for line in pre.splitlines():
            print(f"    {line}")
        print(f"\n  [{hostname}] POST — {acl}:")
        for line in post.splitlines():
            print(f"    {line}")
        if added or removed:
            print(f"\n  [{hostname}] DIFF — {acl}:")
            for line in added:
                print(f"    + {line}")
            for line in removed:
                print(f"    - {line}")
        else:
            print(f"  [{hostname}] DIFF — {acl}: no change")


def run_rollback_loop(
    devices: list[dict],
    push_results: dict,
    username: str,
    password: str,
    svis: list[dict],
    acl_names: list[str],
    default_port: int = 22,
) -> dict:
    """Build a per-device rollback config and push it to each device.

    Args:
        devices: Device dicts with 'hostname', 'address', optional 'port'.
        push_results: Results from the preceding push loop keyed by hostname.
        username: SSH username.
        password: SSH password.
        svis: SVI dicts with original (pre-push) ACL binding names.
        acl_names: ACL names that were pushed.
        default_port: SSH port fallback.

    Returns:
        Dict of rollback results keyed by hostname.
    """
    results = {}
    for device in devices:
        hostname = device["hostname"]
        port = device.get("port", default_port)
        device_push = push_results.get(hostname, {})
        diff = device_push.get("diff", {})
        no_change = all(
            not d.get("added") and not d.get("removed")
            for d in diff.values()
        )
        if no_change:
            print(f"\n  {hostname}: push made no changes — rollback skipped (idempotent).")
            results[hostname] = {"hostname": hostname, "skipped": True,
                                 "reason": "no changes in push diff"}
            continue
        pre_config = device_push.get("pre_config", {})
        rollback_config = build_rollback_config_for_device(svis, pre_config, acl_names)
        print(f"\n  Rolling back {hostname} ({device['address']}:{port}) ...")
        result = push.push_and_verify_device(
            hostname, device["address"], username, password,
            rollback_config, acl_names, port=port,
        )
        print_push_result(result)
        results[hostname] = result
    return results


def run_push_validate_loop(
    devices: list[dict],
    username: str,
    password: str,
    config: str,
    acl_names: list[str],
    default_port: int = 22,
) -> dict:
    """Push and verify config on each device and return results.

    Args:
        devices: List of device dicts with 'hostname', 'address', and
                 optional 'port' (overrides default_port when present).
        username: SSH username.
        password: SSH password.
        config: Configuration string to push.
        acl_names: ACL names to capture pre/post state for.
        default_port: SSH port used when a device dict has no 'port' key.

    Returns:
        Dict of push results keyed by hostname.
    """
    results = {}
    for device in devices:
        port = device.get("port", default_port)
        print(f"\n  Connecting to {device['hostname']} ({device['address']}:{port}) ...")
        result = push.push_and_verify_device(
            device["hostname"], device["address"], username, password,
            config, acl_names, port=port,
        )
        print_push_result(result)
        results[device["hostname"]] = result
    return results


def build_ticket_narrative(record: dict) -> str:
    """Generate a plain-text ServiceNow ticket narrative from the workflow record.

    Args:
        record: Consolidated workflow record dict.

    Returns:
        Multi-line string suitable for pasting into a change ticket.
    """
    sep = "=" * 70
    acl_names = record.get("acl_names", [])
    lines = [
        sep,
        "CHANGE SUMMARY: Update Basic Services ACL",
        f"Location : {record['location']}",
        f"Date/Time: {record['timestamp']}",
        f"Engine   : {record['engine']}",
        f"ACLs     : {', '.join(acl_names)}",
        sep,
        "",
        "SCOPE",
        f"  Devices : {record.get('device_count', 'n/a')}",
        f"  SVIs    : {record.get('svi_count', 'n/a')}",
    ]
    non_std = record.get("non_standard_acls", [])
    if non_std:
        lines += ["", "TECHNICAL DEBT REMOVAL",
                  "  Non-standard ACL names replaced with standard names:"]
        for s in non_std:
            if s.get("acl_in") and s["acl_in"] != acl_names[0]:
                lines.append(f"  - {s['hostname']} {s['interface']}: "
                              f"inbound '{s['acl_in']}' -> '{acl_names[0]}'")
            if len(acl_names) > 1 and s.get("acl_out") and s["acl_out"] != acl_names[1]:
                lines.append(f"  - {s['hostname']} {s['interface']}: "
                              f"outbound '{s['acl_out']}' -> '{acl_names[1]}'")
    lab = record.get("lab_validation") or {}
    if lab:
        lines += ["", "LAB VALIDATION"]
        for hostname, r in lab.items():
            status = "PASSED" if r.get("success") else "FAILED"
            lines.append(f"  - {hostname}: {status}")
        if record.get("lab_rolled_back"):
            lines.append("  Lab configuration was rolled back after validation.")
    prod = record.get("production_push") or {}
    if prod:
        lines += ["", "PRODUCTION PUSH"]
        for hostname, r in prod.items():
            status = "SUCCESS" if r.get("success") else f"FAILED - {r.get('error', 'unknown')}"
            lines.append(f"  - {hostname}: {status}")
            for acl, diff in r.get("diff", {}).items():
                added = len(diff.get("added", []))
                removed = len(diff.get("removed", []))
                lines.append(f"    {acl}: +{added} lines, -{removed} lines")
    if record.get("production_rolled_back"):
        lines += ["", "ROLLBACK EXECUTED",
                  "  Production changes were rolled back to pre-change state."]
        for hostname, r in (record.get("rollback_details") or {}).items():
            if r.get("skipped"):
                status = f"SKIPPED — {r.get('reason', 'no changes to roll back')}"
            elif r.get("success"):
                status = "RESTORED"
            else:
                status = f"FAILED - {r.get('error', 'unknown')}"
            lines.append(f"  - {hostname}: {status}")
    lines += ["", "ROLLBACK AVAILABILITY",
              "  Pre-change ACL config is embedded in the push record JSON.",
              f"  Record: {record.get('record_path', 'see output directory')}",
              "", sep]
    return "\n".join(lines)


def push_had_changes(push_results: dict) -> bool:
    """Return True if any device in push_results has a non-empty diff.

    Used to decide whether it is worth asking the operator about rollback.
    A push that made no changes to any device needs no rollback.

    Args:
        push_results: Dict of per-device results from run_push_validate_loop.

    Returns:
        True if at least one ACL line was added or removed on any device.
    """
    for r in push_results.values():
        for d in r.get("diff", {}).values():
            if d.get("added") or d.get("removed"):
                return True
    return False


def step_banner(step: int, title: str) -> None:
    """Print a formatted step banner to stdout."""
    print(f"\n{'='*60}")
    print(f"  Step {step:>2} | {title}")
    print(f"{'='*60}")


def main(args: argparse.Namespace) -> int:
    """
    update_basic_srvs_pol.py — Main Orchestrator

    Implements the 12-step NAF workflow for updating the basic services
    access-control policy at a given location.

    Usage:
        python update_basic_srvs_pol.py --location <namespace> [options]

    Steps:
        1  Intent documented  — definitions YAML + git commit (manual / CI)
        2  Trigger            — this script (--location, --engine)
        3  Build artifact     — Jinja2 or aerleon
        4  Quantify impact    — modules/impact.py
        5  Current state      — modules/state.py  (Netmiko + TextFSM)
        6  Change record      — modules/change_record.py
        7  Lab it up          — generate_clab_topology.py → output/containerlab_topology/
        8  Push to scope      — modules/push.py   (skipped with --dry-run)
        9  Verify changes     — modules/verify.py
        10 Test across scope  — modules/verify.py
        11 Save/commit        — modules/save.py   (skipped with --dry-run)
        12 Final record       — stdout + output file

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    inventory = load_inventory(INVENTORY_FILE)

    if not args.location:
        print("ERROR: --location is required.\n")
        print("Available locations (from inventory.yml):")
        for loc in inventory:
            print(f"  {loc}  ({len(inventory[loc])} devices)")
        print(f"\nExample: python update_basic_srvs_pol.py --location {next(iter(inventory))}")
        return 1

    devices = get_devices(inventory, args.location)
    run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    record_path = os.path.join(OUTPUT_DIR, f"{args.location}_{run_ts}_push_record.json")
    narrative_path = os.path.join(OUTPUT_DIR, f"{args.location}_{run_ts}_ticket_notes.txt")
    workflow_record = {
        "location": args.location,
        "timestamp": run_ts,
        "engine": None,
        "acl_names": [ACL_NAME, ACL_NAME_OUT],
        "artifact": None,
        "device_count": len(devices),
        "svi_count": 0,
        "non_standard_acls": [],
        "svis": [],
        "lab_validation": None,
        "lab_rolled_back": False,
        "production_push": None,
        "production_rolled_back": False,
        "rollback_details": None,
        "record_path": record_path,
    }

    dotenv.load_dotenv(ENV_FILE)
    username = args.username or os.environ.get("NET_DEVICE_USERNAME")
    password = args.password or os.environ.get("NET_DEVICE_PASSWORD")
    net_device_port = int(os.environ.get("NET_DEVICE_PORT", "22"))
    missing = [v for v, val in [("NET_DEVICE_USERNAME", username), ("NET_DEVICE_PASSWORD", password)] if not val]
    if missing:
        print(f"ERROR: missing credentials — set {', '.join(missing)} in {ENV_FILE} or pass --username/--password.")
        return 1

    # ------------------------------------------------------------------
    # Step 2 — Trigger
    # ------------------------------------------------------------------
    step_banner(2, "Trigger")
    print(f"Location : {args.location}")
    print(f"Devices  : {len(devices)}")
    print(f"Engine   : {args.engine}")
    print(f"Dry-run  : {args.dry_run}")

    # ------------------------------------------------------------------
    # Step 3 — Build configuration artifact
    # ------------------------------------------------------------------
    step_banner(3, "Build Configuration Artifact")
    if args.engine == "jinja2":
        acl_artifact = build_artifact_jinja2(DEFINITIONS_DIR, OUTPUT_DIR)
    else:
        acl_artifact = build_artifact_aerleon(POLICY_FILE, OUTPUT_DIR)
    workflow_record["engine"] = args.engine
    workflow_record["artifact"] = acl_artifact
    print(f"\n--- Generated ACL Artifact ---\n{acl_artifact}\n--- End of Artifact ---")

    # ------------------------------------------------------------------
    # Step 4 — Quantify impact
    # ------------------------------------------------------------------
    step_banner(4, "Quantify Impact")
    impact_data = impact.quantify_impact(DEFINITIONS_DIR)
    print(impact.format_impact_summary(impact_data))

    # ------------------------------------------------------------------
    # Step 5 — Check and document current state
    # ------------------------------------------------------------------
    step_banner(5, "Check and Document Current State")
    pre_snapshot_path = state.capture_location_state(
        devices, username, password, OUTPUT_DIR, args.location, port=net_device_port
    )
    print(f"Pre-change snapshot: {pre_snapshot_path}")

    with open(pre_snapshot_path) as fh:
        snapshot = json.load(fh)

    all_svis = []
    for dev_state in snapshot.get("devices", {}).values():
        for svi in dev_state.get("data_svis", []):
            all_svis.append({"hostname": dev_state.get("hostname", "unknown"), **svi})

    if not all_svis:
        print("\nWARNING: No Data SVIs found on any device at this location.")
        print("  Cannot determine target interfaces — aborting.")
        return 1

    svis_with_acl = [s for s in all_svis if s.get("acl_in") or s.get("acl_out")]
    if not svis_with_acl:
        print("\nWARNING: Data SVIs found but NONE have a pre-existing ACL applied:")
        for svi in all_svis:
            print(f"  - {svi['hostname']} {svi['interface']} ({svi['description']})")
        print("  Adding an ACL to a previously unconstrained interface is high-risk — aborting.")
        return 1

    workflow_record["svi_count"] = len(svis_with_acl)
    workflow_record["svis"] = svis_with_acl

    non_standard = [
        s for s in svis_with_acl
        if (s.get("acl_in") and s["acl_in"] != ACL_NAME)
        or (s.get("acl_out") and s["acl_out"] != ACL_NAME_OUT)
    ]
    workflow_record["non_standard_acls"] = non_standard
    if non_standard:
        print("\nNOTE: Non-standard ACL names found — replacing with standard names (technical debt removal):")
        for s in non_standard:
            if s.get("acl_in") and s["acl_in"] != ACL_NAME:
                print(f"  {s['hostname']} {s['interface']}: inbound '{s['acl_in']}' → '{ACL_NAME}'")
            if s.get("acl_out") and s["acl_out"] != ACL_NAME_OUT:
                print(f"  {s['hostname']} {s['interface']}: outbound '{s['acl_out']}' → '{ACL_NAME_OUT}'")
        print("  Rollback will restore the original ACL names if needed.")

    apply_commands = build_apply_commands(svis_with_acl)
    acl_artifact = acl_artifact + "\n" + apply_commands
    print(f"\n--- Interface Application Commands ---\n{apply_commands}\n--- End ---")

    # ------------------------------------------------------------------
    # Step 6 — Create change record
    # ------------------------------------------------------------------
    step_banner(6, "Create Change Record")
    cr_path = change_record.build_change_record(
        args.location, devices, impact_data, acl_artifact, args.engine, OUTPUT_DIR,
        data_svis=all_svis,
    )
    print(f"Change record: {cr_path}")
    print("\nAction required:")
    print("  1. Open the change record above and create/update the ticket in your ITSM.")
    print("  2. Set the ticket status to IMPLEMENT.")
    input("\nPress Enter to continue once the ticket is in IMPLEMENT state...")

    # ------------------------------------------------------------------
    # Step 7 — Lab it up (Scale = 1)
    # ------------------------------------------------------------------
    step_banner(7, "Lab it up (Scale = 1)")
    gen_script = os.path.join(_HERE, "generate_clab_topology.py")
    clab_topo_path = os.path.join(
        _HERE, "output", "containerlab_topology", "internet-cisco-iol-l3-lab.clab.yml",
    )
    print("  Generating ContainerLab topology from acl_aerleon/def/ source of truth ...")
    print(f"  Reference repo : https://github.com/cldeluna/internet-cisco-iol-l2-clab\n")
    gen_result = subprocess.run(
        [sys.executable, gen_script],
        capture_output=False,
        text=True,
    )
    if gen_result.returncode != 0:
        print(f"\n  ERROR: generate_clab_topology.py failed (exit {gen_result.returncode}).")
        input("\n  Resolve the error, then press Enter to continue...")
    if not os.path.isfile(clab_topo_path):
        print(f"\n  WARNING: topology file still missing: {clab_topo_path}")
        input("\n  Deploy the lab (sudo clab deploy) and press Enter to continue...")

    clab_host = os.environ.get("CLAB_HOST")
    clab_port = os.environ.get("CLAB_PORT", "20512")  # core-sw1 mapped SSH port
    clab_user = os.environ.get("CLAB_USER")
    clab_password = os.environ.get("CLAB_PASSWORD")
    clab_missing = [v for v, val in [
        ("CLAB_HOST", clab_host), ("CLAB_USER", clab_user), ("CLAB_PASSWORD", clab_password)
    ] if not val]

    if clab_missing:
        print(f"\nWARNING: clab validation skipped — set {', '.join(clab_missing)} in {ENV_FILE}.")
        input("\nDeploy the lab (sudo clab deploy) and validate manually, then press Enter to continue...")
    else:
        clab_port_int = int(clab_port)
        clab_devices = [{"hostname": "core-sw1", "address": clab_host, "port": clab_port_int}]
        lab_results = run_push_validate_loop(
            clab_devices, clab_user, clab_password, acl_artifact,
            [ACL_NAME, ACL_NAME_OUT],
        )
        workflow_record["lab_validation"] = lab_results
        if not all(r["success"] for r in lab_results.values()):
            print("\nERROR: one or more clab devices failed — review output above.")
            input("Press Enter to continue anyway, or Ctrl-C to abort...")
        else:
            if not push_had_changes(lab_results):
                print("\nNo ACL changes detected on clab device — rollback not applicable.")
            elif prompt_rollback_or_continue("clab"):
                print("\nRolling back clab ...")
                run_rollback_loop(
                    clab_devices, lab_results, clab_user, clab_password,
                    svis_with_acl, [ACL_NAME, ACL_NAME_OUT],
                )
                workflow_record["lab_rolled_back"] = True
                print("Clab rollback complete.")
            input("\nPress Enter to continue to production push...")

    if args.dry_run:
        step_banner(0, "DRY-RUN — stopping before push")
        print("Steps 8–12 skipped. Review output/ before re-running without --dry-run.")
        return 0

    # ------------------------------------------------------------------
    # Step 8 — Push update to scope
    # ------------------------------------------------------------------
    step_banner(8, "Push Update to Scope")
    push_results = run_push_validate_loop(
        devices, username, password, acl_artifact,
        [ACL_NAME, ACL_NAME_OUT], default_port=net_device_port,
    )
    workflow_record["production_push"] = push_results

    if not push_had_changes(push_results):
        print("\nNo ACL changes detected on any production device — rollback not applicable.")
    elif prompt_rollback_or_continue("production"):
        print("\nRolling back production ...")
        rollback_results = run_rollback_loop(
            devices, push_results, username, password,
            svis_with_acl, [ACL_NAME, ACL_NAME_OUT],
            default_port=net_device_port,
        )
        workflow_record["production_rolled_back"] = True
        workflow_record["rollback_details"] = rollback_results
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(record_path, "w") as fh:
            json.dump(workflow_record, fh, indent=2)
        narrative = build_ticket_narrative(workflow_record)
        with open(narrative_path, "w") as fh:
            fh.write(narrative)
        print("\nProduction rollback complete.")
        print(f"Push record : {record_path}")
        print(f"Ticket notes: {narrative_path}")
        return 0

    # ------------------------------------------------------------------
    # Steps 9 & 10 — Verify and test
    # ------------------------------------------------------------------
    step_banner(9, "Verify Changes Across Scope")
    verify_path = verify.verify_scope(
        devices, username, password, pre_snapshot_path, args.location, OUTPUT_DIR
    )
    print(f"Verification report: {verify_path}")

    step_banner(10, "Test Across Scope")
    verify.test_acl_counters(devices, username, password, port=net_device_port)

    # ------------------------------------------------------------------
    # Step 11 — Save / commit
    # ------------------------------------------------------------------
    step_banner(11, "Save / Commit Across Scope")
    save_path = save.save_scope(
        devices, username, password, args.location, output_dir=OUTPUT_DIR
    )
    print(f"Save results: {save_path}")

    # ------------------------------------------------------------------
    # Step 12 — Final record update
    # ------------------------------------------------------------------
    step_banner(12, "Final Record Updates")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(record_path, "w") as fh:
        json.dump(workflow_record, fh, indent=2)
    narrative = build_ticket_narrative(workflow_record)
    with open(narrative_path, "w") as fh:
        fh.write(narrative)
    print(narrative)
    print(f"\nPush record : {record_path}")
    print(f"Ticket notes: {narrative_path}")
    print("\nAttach both files to the change ticket and close the record.")
    print("Note: the push record JSON contains pre-change ACL config for rollback if needed.")
    

    return 0


# Standard call to the main() function.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Update basic services ACL policy at a given location.",
        epilog="Example: python update_basic_srvs_pol.py --location UWACO_PacificHQ_TEST",
    )
    parser.add_argument(
        "location",
        nargs="?",
        default=None,
        help="Namespace/location key from inventory.yml (omit to list available locations)",
    )
    parser.add_argument(
        "--engine",
        choices=["jinja2", "aerleon"],
        default="jinja2",
        help="ACL generation engine (default: jinja2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run Steps 2–7 only; skip push, verify, save",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="SSH username (prompted if not provided)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="SSH password (prompted if not provided)",
    )
    arguments = parser.parse_args()
    sys.exit(main(arguments))
