#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: infrahub_dhcp_propose.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
Create an Infrahub branch and open a Proposed Change for a new DHCP server.

NOTE: The Infrahub sandbox does not isolate API writes by branch — mutations
go directly to main regardless of the X-INFRAHUB-BRANCH header.  To make a
real branch-isolated change, this script creates the branch and Proposed
Change, then hands off to the user to add the new DHCP server device in the
Infrahub UI (where branch context IS enforced).

Workflow:
  1. Script creates branch 'add-dhcp-server-CdL-<date>'
  2. Script opens a Proposed Change for that branch
  3. User goes to https://sandbox.infrahub.app, switches to the branch,
     and adds the new DHCP server InfraDevice in the UI
  4. User merges the Proposed Change in the UI (or run --merge)
  5. Infrahub fires 'proposed_change.merged' webhook -> Prefect runs

Run:
    uv run python provisioning/infrahub_dhcp_propose.py                  # branch + PR
    uv run python provisioning/infrahub_dhcp_propose.py --merge           # merge existing PR
    uv run python provisioning/infrahub_dhcp_propose.py --delete-branch   # cleanup
"""

import argparse
import datetime
import os
import sys
import requests
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.normpath(os.path.join(_HERE, "..", ".env"))

load_dotenv(ENV_FILE)
INFRAHUB_TOKEN = os.getenv("INFRAHUB_TOKEN")
INFRAHUB_BASE = "https://sandbox.infrahub.app"
INFRAHUB_GRAPHQL = f"{INFRAHUB_BASE}/graphql"

SITE_NAME = "muc"
BRANCH_NAME = f"add-dhcp-server-CdL-{datetime.date.today().isoformat()}"
DESTINATION_BRANCH = "main"

if not INFRAHUB_TOKEN:
    print("ERROR: INFRAHUB_TOKEN not set in .env")
    sys.exit(1)


def _headers(branch: str = None) -> dict:
    h = {"X-INFRAHUB-KEY": INFRAHUB_TOKEN, "Content-Type": "application/json"}
    if branch:
        h["X-INFRAHUB-BRANCH"] = branch
    return h


def gql(query: str, variables: dict = None, branch: str = None) -> dict:
    resp = requests.post(
        INFRAHUB_GRAPHQL,
        json={"query": query, "variables": variables or {}},
        headers=_headers(branch),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        for err in data["errors"]:
            print(f"  GraphQL error: {err.get('message')}")
    return data.get("data") or {}


# ---------------------------------------------------------------------------
# Step 1 — Create branch
# ---------------------------------------------------------------------------

def create_branch(branch_name: str) -> str:
    result = gql(
        """
        mutation CreateBranch($name: String!, $desc: String!) {
          BranchCreate(data: { name: $name, description: $desc }) {
            object { name }
          }
        }
        """,
        {"name": branch_name, "desc": f"Add new DHCP server device to site '{SITE_NAME}'"},
    )
    branch_obj = (result or {}).get("BranchCreate") or {}
    if branch_obj.get("object"):
        print(f"  Created branch '{branch_name}'")
    else:
        print(f"  Branch '{branch_name}' already exists — reusing it")
    return branch_name


# ---------------------------------------------------------------------------
# Step 2 — Open a Proposed Change
# ---------------------------------------------------------------------------

def create_proposed_change(branch_name: str) -> str:
    result = gql(
        """
        mutation CreatePC(
          $name: String! $source: String! $dest: String! $desc: String!
        ) {
          CoreProposedChangeCreate(data: {
            name:               { value: $name }
            source_branch:      { value: $source }
            destination_branch: { value: $dest }
            description:        { value: $desc }
          }) { object { id } }
        }
        """,
        {
            "name": f"Add new DHCP server at {SITE_NAME}",
            "source": branch_name,
            "dest": DESTINATION_BRANCH,
            "desc": (
                f"DNS team: adding new DHCP server device at site '{SITE_NAME}'. "
                "Change made in Infrahub UI on branch. "
                "Merging this PR triggers the Prefect acl-lifecycle workflow automatically."
            ),
        },
    )
    pc_obj = ((result or {}).get("CoreProposedChangeCreate") or {}).get("object") or {}
    pc_id = pc_obj.get("id")
    if pc_id:
        print(f"  Proposed Change created (id: {pc_id})")
        return pc_id

    # Already exists — look it up
    find = gql(
        "query FindPC($branch: String!) { CoreProposedChange(source_branch__value: $branch) { edges { node { id } } } }",
        {"branch": branch_name},
    )
    edges = (find or {}).get("CoreProposedChange", {}).get("edges", [])
    pc_id = edges[0]["node"]["id"] if edges else "unknown"
    print(f"  Proposed Change already exists (id: {pc_id}) — reusing it")
    return pc_id


# ---------------------------------------------------------------------------
# Merge the Proposed Change (triggers webhook)
# ---------------------------------------------------------------------------

def merge_proposed_change(pc_id: str) -> None:
    result = gql(
        "mutation MergePC($id: String!) { CoreProposedChangeMerge(data: { id: $id }) { ok } }",
        {"id": pc_id},
    )
    ok = (result or {}).get("CoreProposedChangeMerge", {}).get("ok", False)
    if ok:
        print(f"  Proposed Change {pc_id} merged into '{DESTINATION_BRANCH}'")
        print("  Infrahub will now fire the 'proposed_change.merged' webhook")
    else:
        print(f"  WARNING: merge may have failed — check Infrahub UI")


# ---------------------------------------------------------------------------
# Delete branch (cleanup/reset)
# ---------------------------------------------------------------------------

def delete_branch(branch_name: str) -> None:
    result = gql(
        "mutation DeleteBranch($name: String!) { BranchDelete(data: { name: $name }) { ok } }",
        {"name": branch_name},
    )
    ok = ((result or {}).get("BranchDelete") or {}).get("ok", False)
    if ok:
        print(f"  Deleted branch '{branch_name}'")
    else:
        print(f"  WARNING: branch delete may have failed — check Infrahub UI")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args: argparse.Namespace) -> None:
    if args.delete_branch:
        print(f"\n--- Deleting branch '{BRANCH_NAME}' ---")
        delete_branch(BRANCH_NAME)
        print("\nDone.")
        return

    print(f"\n--- Step 1: Create branch '{BRANCH_NAME}' ---")
    branch = create_branch(BRANCH_NAME)

    print(f"\n--- Step 2: Open Proposed Change '{BRANCH_NAME}' -> '{DESTINATION_BRANCH}' ---")
    pc_id = create_proposed_change(branch)

    if args.merge:
        print(f"\n--- Merging Proposed Change (triggers webhook -> Prefect) ---")
        merge_proposed_change(pc_id)
    else:
        print(f"""
Branch '{BRANCH_NAME}' is ready.  Proposed Change is open.

Next steps:
  1. Go to {INFRAHUB_BASE} and switch to branch '{BRANCH_NAME}'
  2. Navigate to Devices and add a new DHCP server InfraDevice:
       name   : dhcp-muc-<number>   (e.g. dhcp-muc-14)
       type   : DHCP Server
       role   : edge
       status : active
       site   : muc
  3. Save the device on the branch
  4. Return here and merge with:
         uv run python provisioning/infrahub_dhcp_propose.py --merge
     or merge directly in the Infrahub UI Proposed Changes view.
  5. Merging fires the webhook -> Prefect acl-lifecycle flow runs.
""")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create an Infrahub branch and Proposed Change for a new DHCP server.",
        epilog="Example: uv run python provisioning/infrahub_dhcp_propose.py --merge",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        default=False,
        help="Merge the open Proposed Change (triggers the Infrahub webhook -> Prefect)",
    )
    parser.add_argument(
        "--delete-branch",
        action="store_true",
        default=False,
        help=f"Delete the '{BRANCH_NAME}' branch from Infrahub (cleanup/reset)",
    )
    main(parser.parse_args())
