# No-Code Solution: NAF ACL Lifecycle with Tines

> **Work in Progress** — This solution is actively being developed. Content and implementation details are subject to change.

## Overview

This solution demonstrates the NAF ACL lifecycle workflow using **Tines** as the no-code orchestration platform. Tines is a security automation tool that lets you build workflows — called Stories — using a visual drag-and-drop canvas with no programming required.

The same 12-step NAF workflow (DNS team updates DHCP server records → ACL configuration is regenerated and pushed to scope) is expressed here as a Tines Story that accepts an IP list and generates a Cisco IOS extended ACL configuration as output.

NAF framework mapping:

| Component | NAF Block |
|-----------|-----------|
| Tines web form or webhook trigger | INTENT / PRESENTATION |
| Tines Story orchestration | ORCHESTRATION |
| Build ACL Lines action | INTENT / EXECUTOR |
| ACL configuration output | EXECUTOR |

---

## The Tines Story

The story file `tines_story_acl-config-generator.json` can be imported directly into any Tines tenant.

A hosted version is also available in the Tines Story Library:

**[Generate ACL Configurations from an IP List](https://www.tines.com/library/stories/1352383/?name=generate-acl-configurations-from-an-ip-list&redirected-from=%2Flibrary%2F%3Fview%3Dall&sort=latest)**

### What the Story does

The story accepts a list of DHCP and DNS server IP addresses and generates a complete Cisco IOS extended ACL configuration. It supports two input methods:

- **Web form** — paste IP addresses directly into a Tines page (no-code, operator-friendly)
- **Webhook API** — send a JSON payload to the story's webhook endpoint (integration-friendly)

For each IP the story builds permit statements covering:
- DHCP relay (UDP port 67)
- DNS (UDP/TCP port 53)
- SSH (TCP port 22)
- HTTPS (TCP port 443)
- ICMP

The generated ACL includes an explicit `deny ip any any log` at the end.

### Story Actions

| Action | Type | Purpose |
|--------|------|---------|
| Receive IP List | Webhook | Entry point for API-driven triggers |
| Web Form Input | Page | Entry point for manual/operator input |
| Build ACL Lines Per IP | Event Transformation | Loops over IPs and builds permit lines |
| Assemble ACL | Event Transformation | Combines header, permit lines, and deny into final config |
| Output / Notify | Action | Delivers the generated ACL to the operator |

---

## How It Fits the NAF Workflow

| NAF Step | Activity | Tines Equivalent |
|----------|----------|-----------------|
| 1 | Document required change and scope | Operator pastes new DHCP server IPs into the web form |
| 2 | Trigger | Web form submit or webhook POST starts the Story |
| 3 | Build configuration artifact | Story generates the Cisco ACL config |
| 4-5 | Quantify impact / check current state | Not implemented — manual step |
| 6 | Create change record | Story output can be copy-pasted into an ITSM ticket |
| 7-11 | Lab validation, push, verify, save | Not implemented — manual steps |
| 12 | Final record update | Manual ticket closeout |

The no-code solution covers the INTENT and ORCHESTRATION blocks and produces the configuration artifact (Step 3). Steps requiring device connectivity (push, verify, save) remain manual in this tier, which is the expected trade-off at this maturity level.

---

## Using the Story

### Import into Tines

1. Log in to your Tines tenant at `https://app.tines.com`
2. Create a new Story
3. Click **Import** and upload `tines_story_acl-config-generator.json`
4. The story is ready to run — no credentials or integrations required

### Web form path (no-code)

1. Open the story and click the **Page** action to get the form URL
2. Paste your DHCP/DNS server IP addresses (one per line) into the text field
3. Submit the form
4. The story runs and outputs the generated ACL configuration

### Webhook path (API)

Send a POST to the story's webhook URL with a JSON body:

```json
{
  "dhcp_ips": ["10.0.0.11", "10.0.0.12", "10.0.0.13"],
  "dns_ips":  ["10.0.0.5", "10.0.0.6"]
}
```

The story returns the generated ACL configuration in the response.

---

## Comparison with Other Solution Tiers

| Capability | No-Code (Tines) | Low-Code (Prefect) | Pro-Code (Python) |
|---|---|---|---|
| Trigger | Web form or webhook | Infrahub Proposed Change merge | Manual CLI |
| ACL generation | Tines actions | Jinja2 / aerleon | Jinja2 / aerleon |
| Source of truth | IP list in form | Infrahub InfraDevice | YAML definition files |
| Device push | Manual | Stub (wired to Netmiko in pro-code) | Netmiko |
| Change record | Copy-paste from output | Prefect run log | JSON + text file |
| Programming required | None | Minimal | Python |

---

## Acknowledgements

Special thanks to **Sif Baksh** for his invaluable help and contributions to this solution.
