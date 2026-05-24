#!/usr/bin/python -tt
# Project: acl_automated_workflow
# Filename: infrahub_upsert.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "3/26/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import requests

import os
import requests
import sys
from dotenv import load_dotenv

# 1. Load credentials from .env
load_dotenv()
INFRAHUB_TOKEN = os.getenv("INFRAHUB_TOKEN")
INFRAHUB_URL = "https://sandbox.infrahub.app/graphql"

if not INFRAHUB_TOKEN:
    print("❌ Error: INFRAHUB_API_TOKEN not found in .env file.")
    sys.exit(1)

HEADERS = {
    "X-INFRAHUB-KEY": INFRAHUB_TOKEN,
    "Content-Type": "application/json"
}


def run_gql(query, variables=None):
    """Helper to handle HTTP and GraphQL-specific errors."""
    try:
        response = requests.post(
            INFRAHUB_URL,
            json={'query': query, 'variables': variables},
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            # We print the error but still return the data in case of partial success
            for err in data["errors"]:
                print(f"⚠️ GraphQL Error: {err.get('message')}")

        return data.get("data")

    except requests.exceptions.RequestException as e:
        print(f"🚫 Connection Error: {e}")
        return None


def main():
    namespace_name = "Production_DHCP"
    ips_to_push = ["10.0.0.11/32", "10.0.0.12/32", "10.0.0.13/32"]

    print(f"🚀 Starting upsert for Namespace: {namespace_name}")

    # --- STEP 1: GET OR CREATE NAMESPACE ---
    find_ns_query = """
    query GetNS($name: String!) {
      IpamNamespace(name__value: $name) {
        edges { node { id } }
      }
    }
    """
    ns_data = run_gql(find_ns_query, {"name": namespace_name})

    if ns_data and ns_data["IpamNamespace"]["edges"]:
        ns_id = ns_data["IpamNamespace"]["edges"][0]["node"]["id"]
        print(f"✔ Namespace found (ID: {ns_id})")
    else:
        create_ns_mutation = """
        mutation CreateNS($name: String!) {
          IpamNamespaceCreate(data: { name: { value: $name } }) {
            object { id }
          }
        }
        """
        create_res = run_gql(create_ns_mutation, {"name": namespace_name})
        if not create_res: return
        ns_id = create_res["IpamNamespaceCreate"]["object"]["id"]
        print(f"✚ Created Namespace (ID: {ns_id})")

    # --- STEP 2: UPSERT IP ADDRESSES ---
    for ip in ips_to_push:
        # QUERY: Uses String! for the list filter
        find_ip_query = """
        query GetIP($addr: String!, $ns_str: String!) {
          IpamIPAddress(address__value: $addr, ip_namespace__ids: [$ns_str]) {
            edges { node { id } }
          }
        }
        """
        ip_check = run_gql(find_ip_query, {"addr": ip, "ns_str": ns_id})

        # We only push if the query found 0 results
        if ip_check and ip_check["IpamIPAddress"]["edges"]:
            print(f"  ✔ {ip} already exists. Skipping.")
        else:
            # MUTATION: Uses ID! for the object relationship
            create_ip_mutation = """
            mutation CreateIP($addr: String!, $ns_id: ID!) {
              IpamIPAddressCreate(data: { 
                address: { value: $addr }, 
                ip_namespace: { id: $ns_id } 
              }) { ok }
            }
            """
            mutate_res = run_gql(create_ip_mutation, {"addr": ip, "ns_id": ns_id})
            if mutate_res:
                print(f"  ✚ Successfully pushed {ip}")
            else:
                print(f"  ❌ Failed to push {ip}")

    print("\n✅ Process complete.")


# Standard call to the main() function.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script Description",
                                     epilog="Usage: ' python infrahub_upsert.py' ")

    # parser.add_argument('all', help='Execute all exercises in week 4 assignment')
    # parser.add_argument('-a', '--all', help='Execute all exercises in week 4 assignment', action='store_true',default=False)
    arguments = parser.parse_args()
    main()
