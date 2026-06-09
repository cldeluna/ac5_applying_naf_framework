#!/usr/bin/python -tt
# Project: acl_automated_workflow
# Filename: infrahub_dhcp_upsert.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "3/26/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
INFRAHUB_TOKEN = os.getenv("INFRAHUB_TOKEN")
INFRAHUB_URL = "https://sandbox.infrahub.app/graphql"

if not INFRAHUB_TOKEN:
    print("❌ Error: INFRAHUB_TOKEN not found in .env file.")
    sys.exit(1)

HEADERS = {
    "X-INFRAHUB-KEY": INFRAHUB_TOKEN,
    "Content-Type": "application/json",
}

NAMESPACE_NAME = "Production_DHCP"
IPS_TO_MANAGE = [
    ("10.0.0.11/32", "DHCP Server 1 - muc site"),
    ("10.0.0.12/32", "DHCP Server 2 - muc site"),
    ("10.0.0.13/32", "DHCP Server 3 - muc site"),
]


def run_gql(query, variables=None):
    try:
        response = requests.post(
            INFRAHUB_URL,
            json={"query": query, "variables": variables},
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            for err in data["errors"]:
                print(f"⚠️  GraphQL Error: {err.get('message')}")
        return data.get("data")
    except requests.exceptions.RequestException as e:
        print(f"🚫 Connection Error: {e}")
        return None


def get_or_create_namespace(name: str) -> str:
    ns_data = run_gql(
        "query GetNS($name: String!) { IpamNamespace(name__value: $name) { edges { node { id } } } }",
        {"name": name},
    )
    if ns_data and ns_data["IpamNamespace"]["edges"]:
        ns_id = ns_data["IpamNamespace"]["edges"][0]["node"]["id"]
        print(f"✔  Namespace found (ID: {ns_id})")
        return ns_id

    create_res = run_gql(
        "mutation CreateNS($name: String!) { IpamNamespaceCreate(data: { name: { value: $name } }) { object { id } } }",
        {"name": name},
    )
    if not create_res:
        print("❌ Failed to create namespace.")
        sys.exit(1)
    ns_id = create_res["IpamNamespaceCreate"]["object"]["id"]
    print(f"✚  Created Namespace (ID: {ns_id})")
    return ns_id


def find_ip(addr: str, ns_id: str) -> str | None:
    data = run_gql(
        """
        query GetIP($addr: String!, $ns_id: ID!) {
          IpamIPAddress(address__value: $addr, ip_namespace__ids: [$ns_id]) {
            edges { node { id } }
          }
        }
        """,
        {"addr": addr, "ns_id": ns_id},
    )
    edges = (data or {}).get("IpamIPAddress", {}).get("edges", [])
    return edges[0]["node"]["id"] if edges else None


def upsert_ips(ns_id: str) -> None:
    print(f"\n📋 Upserting {len(IPS_TO_MANAGE)} IP address(es) ...")
    for ip, description in IPS_TO_MANAGE:
        ip_id = find_ip(ip, ns_id)
        if ip_id:
            run_gql(
                """
                mutation UpdateIP($id: String!, $desc: String!) {
                  IpamIPAddressUpdate(data: { id: $id, description: { value: $desc } }) { ok }
                }
                """,
                {"id": ip_id, "desc": description},
            )
            print(f"  ✔  {ip} — updated description: {description!r}")
        else:
            res = run_gql(
                """
                mutation CreateIP($addr: String!, $ns_id: String!, $desc: String!) {
                  IpamIPAddressCreate(data: {
                    address:      { value: $addr }
                    description:  { value: $desc }
                    ip_namespace: { id: $ns_id }
                  }) { ok }
                }
                """,
                {"addr": ip, "ns_id": ns_id, "desc": description},
            )
            if res:
                print(f"  ✚  {ip} — created with description: {description!r}")
            else:
                print(f"  ❌  {ip} — failed to create")


def remove_ips(ns_id: str) -> None:
    print(f"\n🗑️  Removing {len(IPS_TO_MANAGE)} IP address(es) from namespace '{NAMESPACE_NAME}' ...")
    for ip, _ in IPS_TO_MANAGE:
        ip_id = find_ip(ip, ns_id)
        if not ip_id:
            print(f"  —  {ip} not found — skipping")
            continue
        res = run_gql(
            "mutation DeleteIP($id: String!) { IpamIPAddressDelete(data: { id: $id }) { ok } }",
            {"id": ip_id},
        )
        ok = (res or {}).get("IpamIPAddressDelete", {}).get("ok", False)
        if ok:
            print(f"  🗑️  {ip} deleted (id: {ip_id})")
        else:
            print(f"  ❌  {ip} — delete may have failed, check Infrahub UI")


def main(args: argparse.Namespace) -> None:
    print(f"🚀 Namespace: {NAMESPACE_NAME}")
    ns_id = get_or_create_namespace(NAMESPACE_NAME)

    if args.remove:
        remove_ips(ns_id)
    else:
        upsert_ips(ns_id)

    print("\n✅ Process complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upsert or remove DHCP server IPs in the Infrahub Production_DHCP namespace.",
        epilog="Default (no flags): upsert IPs with descriptions.",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        default=False,
        help="Delete the managed IP addresses from Infrahub",
    )
    main(parser.parse_args())
