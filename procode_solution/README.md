# Pro Code Solution — `update_basic_srvs_pol.py`

## Overview

This is a Python-based network automation solution that implements the full 12-step ACL lifecycle workflow for updating **Basic Data Services ACLs** (`BASIC_DATA_SRVC_IN` / `BASIC_DATA_SRVC_OUT`) on Layer 3 switches across a site location.

The trigger for this workflow is a service event — for example, a new DHCP server being brought online, or a DNS server being decommissioned — that requires all Data SVI ACLs to be updated to reflect the change.

The solution is built around a single orchestrator script (`update_basic_srvs_pol.py`) that coordinates a set of purpose-built modules. SSH connectivity to network devices is handled entirely via **Netmiko**. ACL policy is generated from either **Jinja2** templates or the **aerleon** engine, using structured YAML definitions as the source of truth.

### 12-Step Workflow

| Step | Activity | Framework Block | Implementation |
|------|----------|----------------|----------------|
| 1 | Document the required change and scope | INTENT | Git commit to YAML definitions (`acl_aerleon/def/`) |
| 2 | Trigger | ORCHESTRATION / PRESENTATION | `python update_basic_srvs_pol.py --location <LOCATION>` |
| 3 | Build configuration artifact | INTENT | Jinja2 template render **or** aerleon `aclgen` |
| 4 | Quantify impact | OBSERVABILITY | Read `scope`/`service_impact` blocks from YAML definitions |
| 5 | Check and document current state | OBSERVABILITY | Netmiko — `show running-config | section interface Vlan`, `show ip access-lists` |
| 6 | Create change record | INTENT | Python generates structured text file for manual ticket entry |
| 7 | Lab validation (Scale = 1) | INTENT / COLLECTOR | ContainerLab single-node topology; Netmiko push + verify |
| 8 | Push to production scope | EXECUTOR | Netmiko `send_config_set` per L3 device |
| 9 | Verify changes | OBSERVABILITY / COLLECTOR | Post-change state capture (stub — extendable) |
| 10 | Test across scope | EXECUTOR / OBSERVABILITY | `show ip access-lists` counter check via Netmiko |
| 11 | Save / commit | EXECUTOR | `write memory` via Netmiko (stub — extendable) |
| 12 | Final record update | ORCHESTRATION / EXECUTOR | Consolidated JSON push record + ServiceNow ticket narrative |

### Key Design Decisions

- **L3 devices only** — only devices with `role: core`, `distribution`, `spine`, or `leaf` in `inventory.yml` are included. Access switches, firewalls, and WLCs are automatically excluded and logged.
- **Data SVIs only** — only VLAN interfaces with `data` (case-insensitive) in their description are targeted.
- **Standardisation over preservation** — both standard ACL names are always applied unconditionally. If a non-standard ACL name is found, it is logged as technical debt removal and replaced.
- **Single connection per device** — pre-state capture, config push, and post-state capture all occur in one Netmiko session (Steps 7 and 8).
- **Smart rollback** — rollback restores the original ACL configuration captured at push time, handles three scenarios (same-name update, different-name replacement, no prior ACL), and is skipped automatically if no changes were detected.
- **Consolidated output** — a single `<location>_<ts>_push_record.json` and `<location>_<ts>_ticket_notes.txt` are produced per run.

---

## Usage

```bash
# List available locations
python update_basic_srvs_pol.py

# Dry run — stops before push, reviews artifact only
python update_basic_srvs_pol.py UWACO_PacificHQ_TEST --dry-run

# Full run with aerleon engine
python update_basic_srvs_pol.py UWACO_PacificHQ --engine aerleon
```

### Environment Variables (`.env`)

```
NET_DEVICE_USERNAME=<ssh_user>
NET_DEVICE_PASSWORD=<ssh_password>
NET_DEVICE_PORT=22

CLAB_HOST=<containerlab_mgmt_ip>
CLAB_PORT=<ssh_port>
CLAB_USER=<clab_ssh_user>
CLAB_PASSWORD=<clab_ssh_password>
```

---

## Assumptions

- **ContainerLab is available** for Step 7 lab validation. The `CLAB_*` environment variables must be set and the ContainerLab node must be running before execution. If the variables are absent, Step 7 is skipped with a warning and the operator is prompted to validate manually.
- **Cisco IOS target devices** — all production devices are assumed to be `cisco_ios` Netmiko device type. No multi-vendor support is implemented.
- **Data SVIs are identified by description** — any VLAN interface with the word `data` (case-insensitive) in its description is treated as a Data SVI. This convention must be maintained in device configurations.
- **At least one SVI already has an ACL** — the workflow is designed to *update* an existing policy, not introduce one for the first time. At least one Data SVI at the target location must already have an inbound or outbound ACL applied.
- **Device inventory has explicit `role` fields** — `inventory.yml` must include a `role` key for each device. Devices without a role field are included with a warning.
- **SSH reachability** — devices are assumed to be reachable on the configured SSH port. There is no pre-flight ping or connectivity check.
- **Credentials are consistent across a location** — a single username/password pair is used for all production devices at a location. Per-device credentials are not supported.
- **ACL names are the standard** — the solution enforces `BASIC_DATA_SRVC_IN` (inbound) and `BASIC_DATA_SRVC_OUT` (outbound) as the canonical names. Any deviation is treated as technical debt to be corrected.

---

## Guardrails

### What We Trap For

| Guard | Behaviour |
|-------|-----------|
| No L3 devices at location | `sys.exit(1)` with list of available locations |
| Missing credentials | Early abort before any SSH connection attempt |
| No Data SVIs found | Abort with list of all SVIs found for operator review |
| No SVI has any pre-existing ACL | Abort — adding an ACL to a previously unconstrained interface is high-risk |
| Non-standard ACL names found | Logged clearly as technical debt removal before the push proceeds |
| ContainerLab push failure | Operator is prompted to continue or abort before production push |
| No changes detected after push | Rollback prompt is suppressed — "rollback not applicable" is printed |
| Per-device no-diff on rollback | That device is skipped automatically within the rollback loop |
| SSH/connection error per device | Error is captured in the result dict and printed; loop continues to remaining devices |
| aerleon build failure | `RuntimeError` raised with exit code and stderr output |

### What We Are NOT Checking (Known Gaps)

- **No pre-flight reachability test** — if a device is unreachable, the workflow discovers this at SSH connection time, not before.
- **No IOS version or platform validation** — `cisco_ios` device type is assumed for all devices; no check is performed.
- **No ACL semantic validation** — the generated ACL is pushed as-is with no check for duplicate entries, conflicting rules, or inadvertent permit-any-any.
- **No VLAN existence check** — `interface VlanX` commands are pushed without verifying the VLAN is defined on the device.
- **Steps 9 and 11 are stubs** — `verify_scope()` and `save_scope()` write placeholder output but do not perform real post-change verification or `write memory` via Netmiko. Both are marked `TODO`.
- **No automatic rollback on failed push** — if a device fails mid-push, the operator must intervene manually. The rollback offer only appears after a successful push completes.
- **No partial-scope retry** — if some devices fail and others succeed, there is no mechanism to retry only the failed devices.
- **No concurrent execution** — devices are pushed sequentially, one at a time.
- **ContainerLab topology is not deployed automatically** — `build_topology()` writes the YAML file, but `containerlab deploy` must be run separately by the operator.

---

## Spec-Driven Design

The following specification describes the complete solution in enough detail to be given to an LLM to build or rebuild the implementation from scratch.

---

### Specification: ACL Lifecycle Automation — Pro Code

**Context**

A network operations team maintains a standard Basic Data Services ACL policy applied to all Data SVIs on Layer 3 switches. When a service dependency changes (e.g., a new DHCP server, a decommissioned DNS server), all ACLs referencing those services must be updated across every eligible device at every managed location.

**Objective**

Build a Python CLI script (`update_basic_srvs_pol.py`) that automates the full ACL update lifecycle — from artifact generation through lab validation, production push, verification, and record keeping — following a strict 12-step workflow.

**Inputs**

- `inventory.yml` — YAML file mapping location names to lists of devices, each with `hostname`, `address`, and `role` fields.
- `acl_aerleon/def/*.yaml` — YAML definition files containing `networks` (DNS_SERVERS, DHCP_SERVERS, WEB_SERVERS, RFC1918) and policy metadata (`scope`, `service_impact`).
- `templates/basic_services_acl.j2` — Jinja2 template that renders the ACL from the definitions.
- `.env` — environment file with SSH credentials and ContainerLab connection details.

**ACL Policy**

Two ACLs are managed: `BASIC_DATA_SRVC_IN` (inbound) and `BASIC_DATA_SRVC_OUT` (outbound). These names are constants. Any SVI found with a different ACL name is treated as non-standard; the standard names are applied and the replacement is logged as technical debt removal.

**Device Targeting**

Only devices with `role` in `{core, distribution, spine, leaf}` are included. Within those devices, only VLAN interfaces with the word `data` (case-insensitive) in their description are targeted. The workflow aborts if no Data SVIs exist or if none have a pre-existing ACL.

**Workflow Steps**

1. Parse CLI args: positional `location`, `--engine {jinja2,aerleon}`, `--dry-run`, `--username`, `--password`.
2. Load inventory, filter to L3 devices for the given location, log skipped non-L3 devices.
3. Generate ACL artifact via Jinja2 template render or aerleon `aclgen` subprocess.
4. Quantify impact by reading `scope` and `service_impact` from YAML definitions.
5. Capture pre-change state via Netmiko: `show running-config | section interface Vlan` to find Data SVIs and their current ACL names; `show ip access-lists <name>` for each ACL found. Save snapshot JSON and per-device rollback ACL text files. Accepts `port` parameter.
6. Generate change record text file with scope, impact, device list, Data SVIs, and ACL artifact.
7. Generate ContainerLab single-node topology YAML for a representative L3 device (prefer core > distribution > spine by `role` field). Connect to the clab node via Netmiko on `CLAB_PORT`: capture pre-state, push config, capture post-state, diff. If no changes detected, suppress rollback prompt. Otherwise offer rollback.
8. Push to all production L3 devices via Netmiko using the same pre/push/post/diff function (`push_and_verify_device`). Store `pre_config` (running-config section per ACL) for rollback. Offer rollback if changes detected; suppress prompt if none.
9. Capture post-change state and diff against pre-change snapshot (stub, extendable).
10. Check ACL hit counters via `show ip access-lists` on all devices. Accepts `port` parameter.
11. Save running config to startup via `write memory` on all devices (stub, extendable).
12. Write consolidated `<location>_<ts>_push_record.json` (all push data, `pre_config` for rollback, diffs) and `<location>_<ts>_ticket_notes.txt` (plain-text ServiceNow narrative covering scope, technical debt removal, lab validation, production push diffs, rollback status). Print narrative to stdout.

**Rollback Logic (per device, per ACL)**

- *Same ACL name updated*: `no ip access-list extended <name>` then re-push original content from `pre_config`. Interface binding unchanged.
- *Different ACL name was present*: restore original interface binding, remove new ACL definition.
- *No prior ACL*: remove new ACL definition and remove interface binding.
- *No diff detected on device*: skip rollback for that device automatically (idempotency).

**Output Files** (all written to `output/`)

| File | Contents |
|------|----------|
| `<location>_prechange_state_<ts>.json` | Pre-change device state snapshot |
| `<location>_<host>_<acl>_rollback.txt` | Per-device ACL text for emergency rollback |
| `<location>_change_record_<ts>.txt` | Change ticket text |
| `<location>_clab_topology.yml` | ContainerLab topology YAML |
| `<location>_<ts>_push_record.json` | Consolidated push data including `pre_config` |
| `<location>_<ts>_ticket_notes.txt` | ServiceNow narrative |

**Module Structure**

| Module | Responsibility |
|--------|---------------|
| `modules/state.py` | Pre-change state capture, Data SVI parsing from running-config |
| `modules/push.py` | `push_and_verify_device()` — single-connection pre/push/post/diff |
| `modules/verify.py` | Post-change verification and ACL counter testing |
| `modules/save.py` | Save running config to startup (`write memory`) |
| `modules/impact.py` | Load YAML definitions, quantify impact, format summary |
| `modules/change_record.py` | Generate change record text file |
| `modules/containerlab.py` | Topology YAML generation, representative device selection by role |

**Coding Constraints**

- Python 3.10+. All imports at top of file. No imports inside functions.
- Full module imports only (`import netmiko`, not `from netmiko import ConnectHandler`).
- Every SSH-touching function accepts a `port: int = 22` parameter.
- No dead code, no pass-through shims.
- All output files written to `output/` with timestamps in filenames.
- Each module includes a `main()` stub and `if __name__ == "__main__"` block.
