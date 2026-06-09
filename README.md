# Applying the NAF Framework

## Example Use Case: ACL Lifecycle

The workflow used throughout this project to showcase the NAF Framework is a real-world network change event: **the DNS team decommissions an old DHCP server and brings a new one online**, requiring an update to Access Control Lists across a set of network devices.

This scenario was chosen because it is a real-world operational event, the kind of change that happens routinely in production environments. It is not a contrived example designed to fit the framework.

One of the key things this workflow illustrates is that **the mapping between steps and framework blocks is not one-to-one**. A single step can invoke multiple parts of the framework simultaneously, and that is completely appropriate. The framework is not a rigid pipeline; it describes capabilities that naturally overlap depending on what a given step needs to accomplish.

### Workflow Steps

| Step | Activity | Framework Block |
|------|----------|-----------------|
| 1 | Document the required change and its scope | INTENT |
| 2 | Trigger the pipeline | ORCHESTRATION / PRESENTATION |
| 3 | Build a new configuration artifact | INTENT |
| 4 | Quantify the impact | OBSERVABILITY |
| 5 | Check and document current device state | OBSERVABILITY |
| 6 | Create a Change Record (CR) | INTENT |
| 7 | Lab it up (test at scale = 1) | INTENT / COLLECTOR |
| 8 | Push the update to all in-scope devices | EXECUTOR |
| 9 | Verify changes across scope | OBSERVABILITY / COLLECTOR |
| 10 | Test across scope | EXECUTOR / OBSERVABILITY / COLLECTOR |
| 11 | Save / commit across scope | EXECUTOR |
| 12 | Final record updates and ticket closeout | ORCHESTRATION / EXECUTOR |

---

## Solution Tiers

The same 12-step workflow is implemented across four solution tiers so you can see how the framework applies regardless of tooling maturity or team skill level.

### No-Code — Tines

[`nocode_solution/`](nocode_solution/)

Uses **Tines** as the no-code orchestration platform. A Tines Story accepts a list of DHCP server IP addresses via web form or webhook and generates a Cisco IOS extended ACL configuration. No programming required — the workflow is built entirely on the Tines visual canvas.

| | |
|---|---|
| Trigger | Web form or webhook |
| ACL generation | Tines actions |
| Source of truth | IP list provided by operator |
| Device push | Manual |

### Low-Code — Prefect + Infrahub

[`lowcode_solution/`](lowcode_solution/)

Uses **Prefect** as the workflow orchestrator and **Infrahub** as the source of truth. When the DNS team adds a new DHCP server device in Infrahub and merges a Proposed Change, Infrahub fires a webhook that triggers the Prefect ACL lifecycle flow automatically. MCP servers bridge the AI assistant to Infrahub and the network devices.

| | |
|---|---|
| Trigger | Infrahub Proposed Change merge webhook |
| ACL generation | Jinja2 / aerleon |
| Source of truth | Infrahub InfraDevice nodes |
| Device push | Netmiko (stubbed; wired in pro-code) |

### Pro-Code — Python

[`procode_solution/`](procode_solution/)

A full Python implementation of all 12 steps using **Netmiko** for device connectivity, **TextFSM** for state parsing, **Jinja2** and **aerleon** for ACL generation, and **ContainerLab** for lab validation. Triggered manually from the CLI.

| | |
|---|---|
| Trigger | Manual CLI (`python update_basic_srvs_pol.py`) |
| ACL generation | Jinja2 / aerleon |
| Source of truth | YAML definition files |
| Device push | Netmiko |

### AI-Assisted — MCP + LLM

[`ai_solution/`](ai_solution/)

Uses an AI assistant with **MCP (Model Context Protocol) servers** as the integration layer. The AI interacts directly with Infrahub (intent / source of truth), SuzieQ (observability), and Netmiko (execution) through their respective MCP servers — reasoning over network state and taking real actions without custom glue code.

| | |
|---|---|
| Trigger | Natural language |
| ACL generation | AI-generated from Infrahub SoT |
| Source of truth | Infrahub via MCP |
| Observability | SuzieQ via MCP |
| Device push | Netmiko via MCP |

---

## Capability Comparison

| Capability | No-Code | Low-Code | Pro-Code | AI |
|---|---|---|---|---|
| Trigger | Web form / webhook | Infrahub PR merge | Manual CLI | Natural language |
| Source of truth | Operator input | Infrahub | YAML files | Infrahub via MCP |
| ACL generation | Tines actions | Jinja2 / aerleon | Jinja2 / aerleon | AI-generated |
| Observability | None | None | Netmiko + TextFSM | SuzieQ via MCP |
| Device push | Manual | Stubbed | Netmiko | Netmiko via MCP |
| Change record | Copy-paste output | Prefect run log | JSON + text file | AI-drafted |
| Programming required | None | Minimal | Python | None |
