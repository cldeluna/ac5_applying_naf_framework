#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: impact.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "5/22/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import pathlib
import yaml


def load_definitions(definitions_dir: str) -> dict:
    """Load and merge all YAML files from the definitions directory.

    Args:
        definitions_dir: Path to the aerleon def/ directory.

    Returns:
        Merged dict of all definition YAML content.
    """
    merged = {}
    for path in pathlib.Path(definitions_dir).glob("*.yaml"):
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        for key, value in data.items():
            if key in merged and isinstance(merged[key], dict):
                merged[key].update(value)
            else:
                merged[key] = value
    return merged


def quantify_impact(definitions_dir: str, policy_name: str = "BASIC_SERVICES_POLICY") -> dict:
    """Return scope and service impact for a named policy.

    Args:
        definitions_dir: Path to the aerleon def/ directory.
        policy_name: Key to look up in the scope/service_impact blocks.

    Returns:
        Dict with keys 'scope', 'service_impact', and 'policy_name'.
    """
    defs = load_definitions(definitions_dir)
    scope = defs.get("scope", {}).get(policy_name, [])
    service_impact = defs.get("service_impact", {}).get(policy_name, [])

    return {
        "policy_name": policy_name,
        "scope": scope,
        "service_impact": service_impact,
    }


def format_impact_summary(impact: dict) -> str:
    """Render an impact dict as a printable summary string.

    Args:
        impact: Dict returned by quantify_impact().

    Returns:
        Formatted multi-line string.
    """
    lines = [
        f"Policy : {impact['policy_name']}",
        "",
        "Scope:",
    ]
    for item in impact["scope"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("Service Impact:")
    for item in impact["service_impact"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main():
    """
    Step 4 — Quantify Impact

    Reads scope and service_impact metadata from the aerleon definitions YAML
    files and returns a human-readable impact summary for the change record
    and operator review.
    """
    pass


# Standard call to the main() function.
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Step 4 - Quantify Impact",
                                     epilog="Usage: ' python impact.py' ")
    arguments = parser.parse_args()
    main()
