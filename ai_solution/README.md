# AI Solution: NAF ACL Lifecycle with AI-Assisted Network Automation

## Overview

This solution demonstrates the NAF ACL lifecycle workflow using AI as the intelligence layer in the pipeline. Rather than scripting every decision explicitly, the AI solution uses large language models paired with **MCP (Model Context Protocol) servers** to interact directly with the foundational automation services that underpin each NAF framework block.

MCP servers act as bridges between the AI and the tools it needs — the AI does not just generate text, it takes real actions: reading intent from a source of truth, querying live network state, pushing configurations, and verifying results. Each service in the pipeline exposes an MCP interface, giving the AI structured, tool-native access without requiring custom integration code.

NAF framework mapping:

| Component | NAF Block |
|-----------|-----------|
| Natural language intent + Infrahub MCP | INTENT / PRESENTATION |
| AI reasoning and orchestration | ORCHESTRATION |
| AI-generated ACL configuration | EXECUTOR |
| SuzieQ MCP — pre and post-change state | OBSERVABILITY / COLLECTOR |
| Netmiko MCP — push, verify, save | EXECUTOR / COLLECTOR |

---

## MCP Servers in the Pipeline

The key insight of the AI solution is that **each foundational service is accessed through its own MCP server**. The AI assistant selects the right tool for each step just as a network engineer would select the right tool for the job — but without any glue code.

| MCP Server | Service | NAF Block | Role in Workflow |
|---|---|---|---|
| Infrahub MCP | Infrahub (CMDB / SoT) | INTENT | Read current DHCP server records; detect what changed in the Proposed Change |
| SuzieQ MCP | SuzieQ (Network Observability) | OBSERVABILITY / COLLECTOR | Query pre-change ACL state, post-change verification, ACL counter validation |
| Netmiko MCP | Netmiko (Device Connectivity) | EXECUTOR / COLLECTOR | Push ACL configuration, pull show commands, issue write memory |

This is the natural evolution of the pro-code solution: instead of a Python script that calls these services in a fixed sequence, the AI reasons over the situation and calls the appropriate MCP tool at each step — including handling edge cases, rollback decisions, and change record drafting without explicit programming.

---

## Reference

This solution draws on the approach described in:

**[SuzieQ MCP: Channeling Sam Kinison — AI Networking](https://gratuitous-arp.net/suzieq-mcp-channeling-sam-kinison-ai-networking/)**

The post demonstrates using SuzieQ with an MCP server to give an AI assistant live, queryable access to network state. The same pattern extends across the full NAF pipeline: Infrahub for intent, SuzieQ for observability, and Netmiko for execution — each with its own MCP server, all accessible to the AI in a single session.

---

## How It Fits the NAF Workflow

| NAF Step | Activity | AI + MCP Equivalent |
|----------|----------|---------------------|
| 1 | Document required change and scope | Operator describes the change; AI reads current DHCP server records from Infrahub via MCP |
| 2 | Trigger | AI session initiated; intent confirmed against Infrahub SoT |
| 3 | Build configuration artifact | AI generates ACL from Infrahub DHCP server data |
| 4 | Quantify impact | AI queries SuzieQ MCP for device and interface scope |
| 5 | Check current state | AI queries SuzieQ MCP for pre-change ACL configuration |
| 6 | Create change record | AI drafts ticket narrative from session context and SuzieQ data |
| 7 | Lab validation | AI pushes to clab device via Netmiko MCP; queries SuzieQ for result |
| 8 | Push to scope | AI pushes ACL to all in-scope devices via Netmiko MCP |
| 9 | Verify changes | AI queries SuzieQ MCP post-change and interprets diff against pre-change snapshot |
| 10 | Test across scope | AI validates ACL counters via SuzieQ MCP |
| 11 | Save / commit | AI issues write memory on all devices via Netmiko MCP |
| 12 | Final record update | AI generates closeout summary from session context |

---

## Comparison with Other Solution Tiers

| Capability | AI | No-Code (Tines) | Low-Code (Prefect) | Pro-Code (Python) |
|---|---|---|---|---|
| Trigger | Natural language | Web form or webhook | Infrahub Proposed Change merge | Manual CLI |
| ACL generation | AI-generated from Infrahub SoT | Tines actions | Jinja2 / aerleon | Jinja2 / aerleon |
| Source of truth | Infrahub via MCP | IP list in form | Infrahub InfraDevice | YAML definition files |
| Observability | SuzieQ via MCP | None | None | Netmiko + TextFSM |
| Device push | Netmiko via MCP | Manual | Stub (wired to Netmiko in pro-code) | Netmiko |
| Change record | AI-drafted from session context | Copy-paste from output | Prefect run log | JSON + text file |
| Programming required | None | None | Minimal | Python |
