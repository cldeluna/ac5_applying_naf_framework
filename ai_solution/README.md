# AI Solution: NAF ACL Lifecycle with AI-Assisted Network Automation

## Overview

This solution demonstrates the NAF ACL lifecycle workflow using AI as the intelligence layer in the pipeline. Rather than scripting every decision explicitly, the AI solution leverages large language models and AI-native tooling to reason about network state, interpret intent, and assist with configuration generation and validation.

NAF framework mapping:

| Component | NAF Block |
|-----------|-----------|
| Natural language intent | INTENT / PRESENTATION |
| AI reasoning and orchestration | ORCHESTRATION |
| AI-generated ACL configuration | EXECUTOR |
| AI-assisted verification | OBSERVABILITY / COLLECTOR |

---

## Reference

This solution draws on the approach described in:

**[SuzieQ MCP: Channeling Sam Kinison — AI Networking](https://gratuitous-arp.net/suzieq-mcp-channeling-sam-kinison-ai-networking/)**

The post demonstrates using SuzieQ (a network observability platform) with an MCP (Model Context Protocol) server to give an AI assistant live, queryable access to network state. This is directly relevant to the NAF OBSERVABILITY and COLLECTOR blocks — instead of writing Netmiko scripts to pull show commands and parse them with TextFSM, the AI can query SuzieQ directly in natural language and reason over the results.

---

## How It Fits the NAF Workflow

| NAF Step | Activity | AI Equivalent |
|----------|----------|---------------|
| 1 | Document required change and scope | Operator describes the change in natural language |
| 2 | Trigger | AI session initiated; intent parsed from conversation |
| 3 | Build configuration artifact | AI generates ACL configuration from intent and current state |
| 4 | Quantify impact | AI queries SuzieQ for device/interface scope |
| 5 | Check current state | AI queries SuzieQ for pre-change ACL state |
| 6 | Create change record | AI drafts ticket narrative from conversation context |
| 7 | Lab validation | AI-assisted topology reasoning |
| 8 | Push to scope | AI-driven push via MCP tools |
| 9 | Verify changes | AI queries SuzieQ post-change and interprets diff |
| 10 | Test across scope | AI validates ACL counters via SuzieQ |
| 11 | Save / commit | AI issues write memory via MCP |
| 12 | Final record update | AI generates closeout summary |

---

## Comparison with Other Solution Tiers

| Capability | AI | No-Code (Tines) | Low-Code (Prefect) | Pro-Code (Python) |
|---|---|---|---|---|
| Trigger | Natural language | Web form or webhook | Infrahub Proposed Change merge | Manual CLI |
| ACL generation | AI-generated | Tines actions | Jinja2 / aerleon | Jinja2 / aerleon |
| Source of truth | SuzieQ / live network | IP list in form | Infrahub InfraDevice | YAML definition files |
| Device push | MCP tools | Manual | Stub (wired to Netmiko in pro-code) | Netmiko |
| Observability | SuzieQ natural language queries | None | None | Netmiko + TextFSM |
| Programming required | None | None | Minimal | Python |
