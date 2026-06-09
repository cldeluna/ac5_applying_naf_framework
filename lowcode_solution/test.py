#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: test.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
Prefect smoke test for the NAF Framework low-code solution.

Mirrors the 12-step ACL lifecycle workflow using Prefect @task and @flow
decorators.  No real devices or credentials are needed — all tasks use
stub data so you can verify Prefect is installed and working before wiring
up the real implementation.

Run:
    uv run python lowcode_solution/test.py
    # or, to view the run in the Prefect UI first start the server:
    #   uv run prefect server start
    # then in a second terminal:
    #   uv run python lowcode_solution/test.py
"""

from prefect import flow, task, get_run_logger


# ---------------------------------------------------------------------------
# Tasks — one per workflow step
# ---------------------------------------------------------------------------

@task(name="Step 1 | Document Intent")
def document_intent() -> dict:
    logger = get_run_logger()
    change = {
        "trigger": "DNS team decommissioned old DHCP server and brought new one online — DHCP server list updated",
        "scope": "UWACO_PacificHQ",
        "acl_names": ["BASIC_DATA_SRVC_IN", "BASIC_DATA_SRVC_OUT"],
    }
    logger.info("Change documented: %s", change["trigger"])
    return change


@task(name="Step 2 | Trigger")
def trigger(change: dict) -> str:
    logger = get_run_logger()
    location = change["scope"]
    logger.info("Pipeline triggered for location: %s", location)
    return location


@task(name="Step 3 | Build Configuration Artifact")
def build_artifact(change: dict) -> str:
    logger = get_run_logger()
    acl_stub = (
        "ip access-list extended BASIC_DATA_SRVC_IN\n"
        " permit udp any host 10.0.0.11 eq 67\n"
        " permit udp any host 10.0.0.12 eq 67\n"
        " permit udp any host 10.0.0.13 eq 67\n"
        " deny   ip any any log\n"
    )
    logger.info("ACL artifact built (%d lines)", acl_stub.count("\n"))
    return acl_stub


@task(name="Step 4 | Quantify Impact")
def quantify_impact(location: str) -> dict:
    logger = get_run_logger()
    impact = {"location": location, "devices": 3, "svis": 6}
    logger.info("Impact: %d devices, %d SVIs", impact["devices"], impact["svis"])
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
def create_change_record(location: str, impact: dict, artifact: str) -> str:
    logger = get_run_logger()
    cr = (
        f"CHANGE RECORD\n"
        f"Location : {location}\n"
        f"Devices  : {impact['devices']}\n"
        f"SVIs     : {impact['svis']}\n"
        f"Artifact preview:\n{artifact[:120]}...\n"
    )
    logger.info("Change record created — ready for ITSM ticket")
    return cr


@task(name="Step 7 | Lab Validation (scale=1)")
def lab_validation(artifact: str) -> bool:
    logger = get_run_logger()
    # Stub: pretend the clab push succeeded
    logger.info("ContainerLab topology generated and artifact pushed to core-sw1")
    logger.info("Lab validation: PASSED")
    return True


@task(name="Step 8 | Push to Scope")
def push_to_scope(devices: list[str], artifact: str) -> dict:
    logger = get_run_logger()
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
        f"Location : {change['scope']}\n"
        f"Devices  : {len(push_results)}\n"
        f"All succeeded: {all(r['success'] for r in push_results.values())}\n"
    )
    logger.info("Final record written — ready to close ticket")
    return summary


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

@flow(name="NAF ACL Lifecycle — DHCP Server Change")
def acl_lifecycle_flow() -> str:
    # Step 1
    change = document_intent()

    # Step 2
    location = trigger(change)

    # Step 3
    artifact = build_artifact(change)

    # Step 4
    impact = quantify_impact(location)

    # Step 5
    snapshot = check_current_state(impact)

    # Step 6
    cr = create_change_record(location, impact, artifact)

    # Step 7
    lab_ok = lab_validation(artifact)

    # Steps 8–11 only run when lab passed
    devices = list(snapshot["devices"].keys())
    push_results = push_to_scope(devices, artifact)
    verify_changes(push_results)
    test_across_scope(push_results)
    save_commit(push_results)

    # Step 12
    summary = final_record(change, push_results, cr)
    return summary


if __name__ == "__main__":
    result = acl_lifecycle_flow()
    print("\n" + "=" * 60)
    print(result)
