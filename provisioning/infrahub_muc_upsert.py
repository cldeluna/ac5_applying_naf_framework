#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: infrahub_muc_upsert.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
Upsert (or remove) the 'muc' site and its devices in Infrahub.

Reads device connection details from lowcode_solution/.netmiko.yml and
pushes them to the Infrahub sandbox as LocationSite + InfraDevice nodes.

Run:
    uv run python provisioning/add_muc_site.py               # upsert site + devices
    uv run python provisioning/add_muc_site.py --remove-devices  # delete devices only
    uv run python provisioning/add_muc_site.py --remove-site     # delete site only
    uv run python provisioning/add_muc_site.py --remove-all      # delete devices then site
"""

import argparse
import os
import sys
import yaml
import requests
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.normpath(os.path.join(_HERE, "..", ".env"))
NETMIKO_YML = os.path.normpath(os.path.join(_HERE, "..", "lowcode_solution", ".netmiko.yml"))

load_dotenv(ENV_FILE)
INFRAHUB_TOKEN = os.getenv("INFRAHUB_TOKEN")
INFRAHUB_URL = "https://sandbox.infrahub.app/graphql"
SITE_NAME = "muc"
DEVICE_STATUS = "active"

# Maps hostname prefix → valid Infrahub role enum value
# Valid values: core, cpe, edge, firewall, leaf, spine
_ROLE_MAP = {
    "core": "core",
    "access": "edge",
    "dist": "edge",
    "spine": "spine",
    "leaf": "leaf",
    "fw": "firewall",
    "firewall": "firewall",
    "cpe": "cpe",
}

def infer_role(hostname: str) -> str:
    h = hostname.lower()
    for prefix, role in _ROLE_MAP.items():
        if h.startswith(prefix):
            return role
    return "edge"

if not INFRAHUB_TOKEN:
    print("ERROR: INFRAHUB_TOKEN not set in .env")
    sys.exit(1)

HEADERS = {
    "X-INFRAHUB-KEY": INFRAHUB_TOKEN,
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# GraphQL helper
# ---------------------------------------------------------------------------

def gql(query: str, variables: dict = None) -> dict:
    resp = requests.post(
        INFRAHUB_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        for err in data["errors"]:
            print(f"  GraphQL error: {err.get('message')}")
        return {}
    return data.get("data") or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_netmiko_devices(path: str) -> list[dict]:
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    device_names = raw.get("DEVICES", [])
    devices = []
    for name in device_names:
        info = raw.get(name, {})
        devices.append({
            "name": name,
            "host": info.get("host", ""),
            "port": info.get("port", 22),
            "device_type": info.get("device_type", ""),
        })
    return devices


def find_site(site_name: str) -> str | None:
    data = gql(
        "query FindSite($name: String!) { LocationSite(name__value: $name) { edges { node { id } } } }",
        {"name": site_name},
    )
    edges = data.get("LocationSite", {}).get("edges", [])
    return edges[0]["node"]["id"] if edges else None


def find_device(name: str) -> str | None:
    data = gql(
        "query FindDevice($name: String!) { InfraDevice(name__value: $name) { edges { node { id } } } }",
        {"name": name},
    )
    edges = data.get("InfraDevice", {}).get("edges", [])
    return edges[0]["node"]["id"] if edges else None


# ---------------------------------------------------------------------------
# Upsert operations
# ---------------------------------------------------------------------------

def upsert_site(site_name: str) -> str:
    site_id = find_site(site_name)
    if site_id:
        print(f"  Site '{site_name}' already exists (id: {site_id}) — updating")
        gql(
            """
            mutation UpdateSite($id: String!, $name: String!) {
              LocationSiteUpdate(data: { id: $id, name: { value: $name } }) {
                object { id }
              }
            }
            """,
            {"id": site_id, "name": site_name},
        )
        return site_id

    create = gql(
        "mutation CreateSite($name: String!) { LocationSiteCreate(data: { name: { value: $name } }) { object { id } } }",
        {"name": site_name},
    )
    site_id = create.get("LocationSiteCreate", {}).get("object", {}).get("id")
    print(f"  Created site '{site_name}' (id: {site_id})")
    return site_id


def upsert_device(device: dict, site_id: str) -> None:
    name = device["name"]
    dev_id = find_device(name)

    vars_common = {
        "site_id": site_id,
        "type": device["device_type"],
        "status": DEVICE_STATUS,
        "role": infer_role(name),
    }

    if dev_id:
        result = gql(
            """
            mutation UpdateDevice(
              $id: String!
              $site_id: String!
              $type: String!
              $status: String!
              $role: String!
            ) {
              InfraDeviceUpdate(data: {
                id:     $id
                site:   { id: $site_id }
                type:   { value: $type }
                status: { value: $status }
                role:   { value: $role }
              }) {
                object { id }
              }
            }
            """,
            {"id": dev_id, **vars_common},
        )
        if result.get("InfraDeviceUpdate", {}).get("object", {}).get("id"):
            print(f"  Updated device '{name}' (id: {dev_id})")
        else:
            print(f"  WARNING: Update for '{name}' returned no id — check Infrahub UI")
        return

    result = gql(
        """
        mutation CreateDevice(
          $name: String!
          $site_id: String!
          $type: String!
          $status: String!
          $role: String!
        ) {
          InfraDeviceCreate(data: {
            name:   { value: $name }
            site:   { id: $site_id }
            type:   { value: $type }
            status: { value: $status }
            role:   { value: $role }
          }) {
            object { id }
          }
        }
        """,
        {"name": name, **vars_common},
    )
    dev_id = result.get("InfraDeviceCreate", {}).get("object", {}).get("id")
    if dev_id:
        print(f"  Created device '{name}' at site '{SITE_NAME}' (id: {dev_id})")
        print(f"    host={device['host']}  port={device['port']}  type={device['device_type']}")
    else:
        print(f"  WARNING: Device '{name}' creation returned no id — check schema")


# ---------------------------------------------------------------------------
# Remove operations
# ---------------------------------------------------------------------------

def remove_devices(device_names: list[str]) -> None:
    for name in device_names:
        dev_id = find_device(name)
        if not dev_id:
            print(f"  Device '{name}' not found — skipping")
            continue
        result = gql(
            "mutation DeleteDevice($id: String!) { InfraDeviceDelete(data: { id: $id }) { ok } }",
            {"id": dev_id},
        )
        if result.get("InfraDeviceDelete", {}).get("ok"):
            print(f"  Deleted device '{name}' (id: {dev_id})")
        else:
            print(f"  WARNING: Delete for '{name}' may have failed — check Infrahub UI")


def remove_site(site_name: str) -> None:
    site_id = find_site(site_name)
    if not site_id:
        print(f"  Site '{site_name}' not found — skipping")
        return
    result = gql(
        "mutation DeleteSite($id: String!) { LocationSiteDelete(data: { id: $id }) { ok } }",
        {"id": site_id},
    )
    if result.get("LocationSiteDelete", {}).get("ok"):
        print(f"  Deleted site '{site_name}' (id: {site_id})")
    else:
        print(f"  WARNING: Delete for site '{site_name}' may have failed — check Infrahub UI")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args: argparse.Namespace) -> None:
    devices = load_netmiko_devices(NETMIKO_YML)
    device_names = [d["name"] for d in devices]
    print(f"Devices from {NETMIKO_YML}: {device_names}\n")

    if args.remove_all:
        print(f"Removing all: devices then site ...")
        remove_devices(device_names)
        remove_site(SITE_NAME)

    elif args.remove_devices:
        print(f"Removing devices: {device_names} ...")
        remove_devices(device_names)

    elif args.remove_site:
        print(f"Removing site '{SITE_NAME}' ...")
        remove_site(SITE_NAME)

    else:
        print(f"Upserting site '{SITE_NAME}' ...")
        site_id = upsert_site(SITE_NAME)

        print(f"\nUpserting devices into site '{SITE_NAME}' ...")
        for device in devices:
            upsert_device(device, site_id)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upsert or remove the muc site and devices in Infrahub.",
        epilog="Default (no flags): upsert site and devices.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--remove-devices", action="store_true", help="Delete muc devices from Infrahub")
    group.add_argument("--remove-site", action="store_true", help="Delete the muc site from Infrahub")
    group.add_argument("--remove-all", action="store_true", help="Delete devices then the muc site")
    main(parser.parse_args())
