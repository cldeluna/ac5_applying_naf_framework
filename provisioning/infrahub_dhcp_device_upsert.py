#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: infrahub_dhcp_device_upsert.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
Upsert DHCP servers as InfraDevice nodes in Infrahub.

IpamIPAddress nodes do not branch-isolate on the sandbox — writes go
directly to main regardless of the branch header.  InfraDevice nodes
are branch-aware, so this script uses InfraDevice to represent DHCP
servers so that the branch -> proposed change -> merge -> webhook
workflow functions correctly.

Each DHCP server is created as an InfraDevice at the muc site with:
  type        : DHCP Server
  role        : edge
  description : IP address of the server

Run:
    uv run python provisioning/infrahub_dhcp_device_upsert.py            # upsert baseline
    uv run python provisioning/infrahub_dhcp_device_upsert.py --remove   # delete all
"""

import argparse
import os
import sys
import requests
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.normpath(os.path.join(_HERE, "..", ".env"))

load_dotenv(ENV_FILE)
INFRAHUB_TOKEN = os.getenv("INFRAHUB_TOKEN")
INFRAHUB_URL = "https://sandbox.infrahub.app/graphql"
SITE_NAME = "muc"

if not INFRAHUB_TOKEN:
    print("ERROR: INFRAHUB_TOKEN not set in .env")
    sys.exit(1)

HEADERS = {
    "X-INFRAHUB-KEY": INFRAHUB_TOKEN,
    "Content-Type": "application/json",
}

# Baseline DHCP servers: (device-name, ip-address)
DHCP_SERVERS = [
    ("dhcp-muc-01", "10.0.0.11", "DHCP Server 1 - muc site"),
    ("dhcp-muc-02", "10.0.0.12", "DHCP Server 2 - muc site"),
    ("dhcp-muc-03", "10.0.0.13", "DHCP Server 3 - muc site"),
]

DEVICE_TYPE = "DHCP Server"
DEVICE_ROLE = "edge"
DEVICE_STATUS = "active"


def gql(query: str, variables: dict = None, branch: str = None) -> dict:
    headers = {**HEADERS}
    if branch:
        headers["X-INFRAHUB-BRANCH"] = branch
    resp = requests.post(
        INFRAHUB_URL,
        json={"query": query, "variables": variables or {}},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        for err in data["errors"]:
            print(f"  GraphQL error: {err.get('message')}")
    return data.get("data") or {}


def find_site(name: str) -> str | None:
    data = gql(
        "query FindSite($name: String!) { LocationSite(name__value: $name) { edges { node { id } } } }",
        {"name": name},
    )
    edges = data.get("LocationSite", {}).get("edges", [])
    return edges[0]["node"]["id"] if edges else None


def find_device(name: str, branch: str = None) -> str | None:
    data = gql(
        "query FindDevice($name: String!) { InfraDevice(name__value: $name) { edges { node { id } } } }",
        {"name": name},
        branch=branch,
    )
    edges = data.get("InfraDevice", {}).get("edges", [])
    return edges[0]["node"]["id"] if edges else None


def upsert_device(name: str, ip: str, description: str, site_id: str, branch: str = None) -> None:
    dev_id = find_device(name, branch=branch)
    vars_common = {
        "site_id": site_id,
        "type": DEVICE_TYPE,
        "role": DEVICE_ROLE,
        "status": DEVICE_STATUS,
        "desc": description,
    }

    if dev_id:
        result = gql(
            """
            mutation UpdateDevice(
              $id: String! $site_id: String! $type: String!
              $role: String! $status: String! $desc: String!
            ) {
              InfraDeviceUpdate(data: {
                id: $id  site: { id: $site_id }
                type: { value: $type }  role: { value: $role }
                status: { value: $status }  description: { value: $desc }
              }) { object { id } }
            }
            """,
            {"id": dev_id, **vars_common},
            branch=branch,
        )
        if (result or {}).get("InfraDeviceUpdate", {}).get("object"):
            print(f"  Updated  {name} ({ip})")
        else:
            print(f"  WARNING: update for '{name}' may have failed")
        return

    result = gql(
        """
        mutation CreateDevice(
          $name: String! $site_id: String! $type: String!
          $role: String! $status: String! $desc: String!
        ) {
          InfraDeviceCreate(data: {
            name: { value: $name }  site: { id: $site_id }
            type: { value: $type }  role: { value: $role }
            status: { value: $status }  description: { value: $desc }
          }) { object { id } }
        }
        """,
        {"name": name, **vars_common},
        branch=branch,
    )
    dev_id = (result or {}).get("InfraDeviceCreate", {}).get("object", {}).get("id")
    if dev_id:
        print(f"  Created  {name} ({ip})  id: {dev_id}")
    else:
        print(f"  WARNING: create for '{name}' may have failed")


def remove_device(name: str) -> None:
    dev_id = find_device(name)
    if not dev_id:
        print(f"  {name} not found — skipping")
        return
    result = gql(
        "mutation DeleteDevice($id: String!) { InfraDeviceDelete(data: { id: $id }) { ok } }",
        {"id": dev_id},
    )
    ok = (result or {}).get("InfraDeviceDelete", {}).get("ok", False)
    if ok:
        print(f"  Deleted  {name}")
    else:
        print(f"  WARNING: delete for '{name}' may have failed")


def main(args: argparse.Namespace) -> None:
    if args.remove:
        print(f"Removing {len(DHCP_SERVERS)} DHCP server device(s) from Infrahub ...\n")
        for name, ip, _ in DHCP_SERVERS:
            remove_device(name)
        print("\nDone.")
        return

    site_id = find_site(SITE_NAME)
    if not site_id:
        print(f"ERROR: Site '{SITE_NAME}' not found. Run infrahub_muc_upsert.py first.")
        sys.exit(1)
    print(f"Site '{SITE_NAME}' found (id: {site_id})\n")

    print(f"Upserting {len(DHCP_SERVERS)} DHCP server device(s) on main ...\n")
    for name, ip, description in DHCP_SERVERS:
        upsert_device(name, ip, description, site_id)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upsert DHCP servers as InfraDevice nodes in Infrahub (branch-aware).",
        epilog="Run infrahub_muc_upsert.py first to ensure the muc site exists.",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        default=False,
        help="Delete all managed DHCP server devices from Infrahub",
    )
    main(parser.parse_args())
