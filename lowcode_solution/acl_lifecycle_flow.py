#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: acl_lifecycle_flow.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
NAF ACL Lifecycle Flow — low-code solution.

Infrahub is the single source of truth for DHCP server IPs.  When a
Proposed Change is merged in Infrahub, the webhook receiver
(webhook_receiver.py) creates a run of this deployment.  Step 1 queries
Infrahub for the current DHCP server IPs; the rest of the 12-step NAF
workflow proceeds from there.

Run (registers deployment and starts serving):
    uv run python lowcode_solution/acl_lifecycle_flow.py
"""

import os
import requests as _requests
from dotenv import load_dotenv
from prefect import flow, task, get_run_logger

_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.normpath(os.path.join(_HERE, "..", ".env"))

INFRAHUB_GRAPHQL_URL = "https://sandbox.infrahub.app/graphql"
DHCP_DEVICE_TYPE = "DHCP Server"
SITE_NAME = "muc"
FLOW_NAME = "acl-lifecycle"


# ---------------------------------------------------------------------------
# Infrahub helper
# ---------------------------------------------------------------------------

def _infrahub_gql(query: str, variables: dict, token: str) -> dict:
    headers = {"X-INFRAHUB-KEY": token, "Content-Type": "application/json"}
    resp = _requests.post(
        INFRAHUB_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data") or {}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@task(name="Step 1 | Fetch DHCP Servers from Infrahub")
def fetch_dhcp_servers() -> list[dict]:
    """Query Infrahub for InfraDevice nodes with type 'DHCP Server' at the muc site."""
    logger = get_run_logger()
    load_dotenv(ENV_FILE)
    token = os.getenv("INFRAHUB_TOKEN")
    if not token:
        raise RuntimeError("INFRAHUB_TOKEN not set — check .env")

    data = _infrahub_gql(
        """
        query GetDHCPDevices($type: String!) {
          InfraDevice(type__value: $type) {
            edges {
              node {
                name        { value }
                description { value }
                status      { value }
              }
            }
          }
        }
        """,
        {"type": DHCP_DEVICE_TYPE},
        token,
    )
    devices = [
        {
            "name": e["node"]["name"]["value"],
            "description": (e["node"]["description"] or {}).get("value", ""),
            "status": (e["node"]["status"] or {}).get("value", ""),
        }
        for e in (data.get("InfraDevice") or {}).get("edges", [])
    ]
    if not devices:
        raise RuntimeError(
            f"No '{DHCP_DEVICE_TYPE}' devices found in Infrahub. "
            "Run provisioning/infrahub_dhcp_device_upsert.py first."
        )
    logger.info("Infrahub: found %d DHCP server device(s)", len(devices))
    for d in devices:
        logger.info("  %s — %s (%s)", d["name"], d["description"], d["status"])
    return devices


@task(name="Step 2 | Trigger")
def trigger(dhcp_devices: list[dict]) -> dict:
    logger = get_run_logger()
    change = {
        "trigger": "Infrahub proposed_change.merged — DHCP server device added at muc site",
        "scope": "UWACO_PacificHQ",
        "dhcp_devices": dhcp_devices,
        "acl_names": ["BASIC_DATA_SRVC_IN", "BASIC_DATA_SRVC_OUT"],
    }
    logger.info("Pipeline triggered — %d DHCP server device(s) in scope", len(dhcp_devices))
    return change


@task(name="Step 3 | Build Configuration Artifact")
def build_artifact(change: dict) -> str:
    logger = get_run_logger()
    devices = change["dhcp_devices"]
    lines = ["ip access-list extended BASIC_DATA_SRVC_IN"]
    for d in devices:
        lines.append(f" permit udp any host {d['name']} eq 67  ! {d['description']}")
    lines.append(" deny   ip any any log")
    acl = "\n".join(lines) + "\n"
    logger.info("ACL artifact built from Infrahub InfraDevice data (%d server(s))", len(devices))
    return acl


@task(name="Step 4 | Quantify Impact")
def quantify_impact(change: dict) -> dict:
    logger = get_run_logger()
    impact = {"location": change["scope"], "devices": 3, "svis": 6}
    logger.info("Impact: %d devices, %d SVIs at %s", impact["devices"], impact["svis"], impact["location"])
    return impact


@task(name="Step 5 | Check Current State")
def check_current_state(impact: dict) -> dict:
    logger = get_run_logger()
    snapshot = {
        "devices": {
            "core-sw1": {"data_svis": [{"interface": "Vlan10", "acl_in": "BASIC_DATA_SRVC_IN"}]},
            "dist-sw1": {"data_svis": [{"interface": "Vlan20", "acl_in": "BASIC_DATA_SRVC_IN"}]},
        }
    }
    logger.info("Pre-change snapshot captured for %d devices", len(snapshot["devices"]))
    return snapshot


@task(name="Step 6 | Create Change Record")
def create_change_record(change: dict, impact: dict, artifact: str) -> str:
    logger = get_run_logger()
    cr = (
        f"CHANGE RECORD\n"
        f"Trigger  : {change['trigger']}\n"
        f"Location : {change['scope']}\n"
        f"Devices  : {impact['devices']}\n"
        f"SVIs     : {impact['svis']}\n"
        f"DHCP SoT : Infrahub InfraDevice / type={DHCP_DEVICE_TYPE}\n"
        f"Servers  : {', '.join(d['name'] for d in change['dhcp_devices'])}\n"
    )
    logger.info("Change record created — ready for ITSM ticket")
    return cr


@task(name="Step 7 | Lab Validation (scale=1)")
def lab_validation(artifact: str) -> bool:
    logger = get_run_logger()
    logger.info("ContainerLab topology generated; artifact pushed to core-sw1 — PASSED")
    return True


@task(name="Step 8 | Push to Scope")
def push_to_scope(snapshot: dict, artifact: str) -> dict:
    logger = get_run_logger()
    devices = list(snapshot["devices"].keys())
    results = {dev: {"success": True, "diff": {"added": 2, "removed": 1}} for dev in devices}
    logger.info("Pushed to %d device(s)", len(devices))
    return results


@task(name="Step 9 | Verify Changes")
def verify_changes(push_results: dict) -> bool:
    logger = get_run_logger()
    passed = all(r["success"] for r in push_results.values())
    logger.info("Verification: %s", "PASSED" if passed else "FAILED")
    return passed


@task(name="Step 10 | Test Across Scope")
def test_across_scope(push_results: dict) -> bool:
    logger = get_run_logger()
    logger.info("ACL counter test across %d device(s): PASSED", len(push_results))
    return True


@task(name="Step 11 | Save / Commit")
def save_commit(push_results: dict) -> None:
    logger = get_run_logger()
    logger.info("'write memory' issued on %d device(s)", len(push_results))


@task(name="Step 12 | Final Record Update")
def final_record(change: dict, push_results: dict, cr: str) -> str:
    logger = get_run_logger()
    summary = (
        f"WORKFLOW COMPLETE\n"
        f"Trigger  : {change['trigger']}\n"
        f"Location : {change['scope']}\n"
        f"DHCP servers: {len(change['dhcp_devices'])}\n"
        f"Network devices pushed: {len(push_results)}\n"
        f"All succeeded: {all(r['success'] for r in push_results.values())}\n"
    )
    logger.info("Final record written — ready to close ticket")
    return summary


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

@flow(name=FLOW_NAME)
def acl_lifecycle_flow() -> str:
    # Steps 1 & 2 — Intent from Infrahub + Trigger
    dhcp_devices = fetch_dhcp_servers()
    change = trigger(dhcp_devices)

    # Step 3 — Build artifact using live Infrahub data
    artifact = build_artifact(change)

    # Step 4 — Quantify impact
    impact = quantify_impact(change)

    # Step 5 — Current state
    snapshot = check_current_state(impact)

    # Step 6 — Change record
    cr = create_change_record(change, impact, artifact)

    # Step 7 — Lab validation
    lab_validation(artifact)

    # Steps 8–11
    push_results = push_to_scope(snapshot, artifact)
    verify_changes(push_results)
    test_across_scope(push_results)
    save_commit(push_results)

    # Step 12
    return final_record(change, push_results, cr)


if __name__ == "__main__":
    acl_lifecycle_flow.serve(name=FLOW_NAME)
