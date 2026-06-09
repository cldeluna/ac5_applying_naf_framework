# Low-Code Solution: NAF ACL Lifecycle with Prefect and Infrahub

## Overview

This solution replaces the manual `python update_basic_srvs_pol.py` trigger from the pro-code solution with an event-driven pipeline. Infrahub is the single source of truth for DHCP server data. When a Proposed Change is merged in Infrahub, a webhook fires and Prefect runs the full 12-step ACL lifecycle workflow automatically.

```
Infrahub Proposed Change
    -> merge to main
        -> webhook POST to receiver
            -> Prefect creates flow run
                -> flow queries Infrahub for DHCP IPs
                    -> builds ACL artifact
                        -> Steps 3-12 of NAF workflow
```

NAF framework mapping:

| Component | NAF Block |
|-----------|-----------|
| Infrahub DHCP Server records + Proposed Change | INTENT |
| Infrahub webhook on `proposed_change.merged` | ORCHESTRATION / PRESENTATION |
| `webhook_receiver.py` (FastAPI) | ORCHESTRATION |
| `acl_lifecycle_flow.py` (Prefect) | ORCHESTRATION / EXECUTOR / OBSERVABILITY / COLLECTOR |

---

## Prerequisites

- Python 3.12 and `uv` installed
- Access to `https://sandbox.infrahub.app` with a valid token
- `.env` file at the repo root with at minimum:

```
INFRAHUB_TOKEN=<your-token>
```

A full `.env.example` is at the repo root.

---

## Environment Setup

From the repo root, install all dependencies:

```
uv sync
```

---

## Files

| File | Purpose |
|------|---------|
| `lowcode_solution/acl_lifecycle_flow.py` | Prefect flow — reads DHCP IPs from Infrahub, runs 12-step workflow |
| `lowcode_solution/webhook_receiver.py` | FastAPI server — receives Infrahub webhooks, triggers Prefect |
| `lowcode_solution/test.py` | Smoke test — runs the flow with stub data, no Infrahub or devices needed |
| `lowcode_solution/.netmiko.yml` | Device inventory for the muc site (core01, access01) |
| `provisioning/infrahub_dhcp_upsert.py` | Populates the Production_DHCP namespace with baseline DHCP server IPs |
| `provisioning/infrahub_muc_upsert.py` | Creates the muc site and its devices in Infrahub |
| `provisioning/infrahub_dhcp_propose.py` | Creates a branch, adds new DHCP server, opens a Proposed Change |

---

## Part 1: Smoke Test (no Infrahub required)

Before wiring up Infrahub, verify Prefect is working with stub data:

```
uv run python lowcode_solution/test.py
```

You should see all 12 steps log in sequence and the flow complete. Optionally start the Prefect UI first to see the run graphically:

```
# Terminal 1
uv run prefect server start

# Terminal 2
uv run python lowcode_solution/test.py
```

Then open `http://localhost:4200` to see the flow run.

---

## Part 2: Populate Infrahub

These steps only need to be run once to set up the baseline data. Order matters — the site and devices must exist before IPs can be associated with them.

### 2a. Add the muc site and devices

`provisioning/infrahub_muc_upsert.py` reads `lowcode_solution/.netmiko.yml` and upserts the `muc` site and its devices into Infrahub. It is safe to re-run — if the site or a device already exists it updates it rather than creating a duplicate.

For each device it sets:
- `type` — taken directly from the `device_type` field in `.netmiko.yml` (e.g. `arista_eos`)
- `status` — set to `active`
- `role` — inferred from the hostname prefix using Infrahub's valid enum values (`core, cpe, edge, firewall, leaf, spine`). Examples: `core01` → `core`, `access01` → `edge`

```
uv run python provisioning/infrahub_muc_upsert.py
```

The script also supports cleanup flags if you need to reset and start over:

```
uv run python provisioning/infrahub_muc_upsert.py --remove-devices   # delete core01 and access01
uv run python provisioning/infrahub_muc_upsert.py --remove-site      # delete the muc site
uv run python provisioning/infrahub_muc_upsert.py --remove-all       # delete devices then site
```

Verify in the Infrahub UI at `https://sandbox.infrahub.app` that the site and devices appear before continuing.

### 2b. Populate the Production_DHCP namespace

This creates the `Production_DHCP` IPAM namespace and pushes the baseline DHCP server IPs (10.0.0.11/32, 10.0.0.12/32, 10.0.0.13/32). The muc site's core01 device must already exist (step 2a) so the IPs can be associated with it:

```
uv run python provisioning/infrahub_dhcp_upsert.py
```

---

## Part 3: Run the Full Event-Driven Workflow

This is the live demo. You need three terminals running simultaneously.

### Terminal 1: Start the Prefect server

```
uv run prefect server start
```

Leave this running. The UI is available at `http://localhost:4200`.

### Terminal 2: Register the deployment and start serving

```
uv run python lowcode_solution/acl_lifecycle_flow.py
```

This registers the `acl-lifecycle` deployment in Prefect and blocks, waiting to pick up flow runs. You should see output like:

```
Your flow 'acl-lifecycle' is being served and polling for scheduled runs!
```

Leave this running.

### Terminal 3: Start the webhook receiver

```
uv run uvicorn lowcode_solution.webhook_receiver:app --port 8000 --reload
```

Verify it is up:

```
curl http://localhost:8000/health
```

Expected response: `{"status":"ok","prefect_api":"http://127.0.0.1:4200/api"}`

---

## Part 4: Trigger the Workflow

### Option A: Full Infrahub trigger (live demo path)

The Infrahub sandbox does not isolate API writes by branch, so the new DHCP server device must be added in the Infrahub UI where branch context is enforced. The script handles setup and teardown; the UI handles the data change.

**Step 1 — Create the branch and Proposed Change:**
```
uv run python provisioning/infrahub_dhcp_propose.py
```

The script prints the branch name and step-by-step UI instructions.

**Step 2 — Add the DHCP server device in the Infrahub UI:**
1. Go to `https://sandbox.infrahub.app`
2. Switch to the branch `add-dhcp-server-CdL-<today's date>` using the branch selector
3. Navigate to Devices and add a new InfraDevice:
   - name: `dhcp-muc-14` (or the next available number)
   - type: `DHCP Server`
   - role: `edge`
   - status: `active`
   - site: `muc`
4. Save the device on the branch

**Step 3 — Merge the Proposed Change:**

Either merge it in the Infrahub UI Proposed Changes view, or from the CLI:
```
uv run python provisioning/infrahub_dhcp_propose.py --merge
```

**What happens next:**
1. Infrahub fires `proposed_change.merged` webhook to `http://localhost:8000/webhook/infrahub`
2. The receiver validates the event and calls the Prefect API
3. A new flow run appears in the Prefect UI at `http://localhost:4200`
4. Steps 3-12 of the NAF workflow execute

**Cleanup (reset branch for next demo run):**
```
uv run python provisioning/infrahub_dhcp_propose.py --delete-branch
```

### Option B: Test trigger (bypass Infrahub)

To test the webhook receiver and Prefect flow without going through Infrahub at all:

```
curl -X POST http://localhost:8000/test/trigger
```

The flow runs immediately.

---

## Configuring the Infrahub Webhook (for a persistent setup)

To have Infrahub automatically call your receiver on every Proposed Change merge, configure an outbound webhook in the Infrahub UI:

1. Go to `https://sandbox.infrahub.app` and navigate to Settings > Webhooks
2. Create a new webhook:
   - URL: `http://<your-host>:8000/webhook/infrahub`
   - Events: `proposed_change.merged`
   - Shared secret: set a value and add it to `.env` as `INFRAHUB_WEBHOOK_SECRET`
3. Save

After this, any Proposed Change merge will trigger the workflow automatically without running `infrahub_dhcp_propose.py`.

---

## Sandbox Limitations

These limitations are specific to `sandbox.infrahub.app` and do not apply to a self-hosted or production Infrahub instance.

**API writes do not respect branch context**
Mutations sent with the `X-INFRAHUB-BRANCH` header go directly to `main` regardless of the branch specified. This was confirmed by testing both `IpamIPAddress` and `InfraDevice` node types. As a result, data changes for the Proposed Change workflow must be made in the Infrahub UI, where branch context is properly enforced.

**IPAM data (`IpamIPAddress`) is not branch-isolated**
Attempts to add IP addresses to a branch via the API landed on `main` immediately. The `acl_lifecycle_flow.py` Step 1 was updated to query `InfraDevice` nodes (type `DHCP Server`) instead of the IPAM namespace for this reason.

**Schema modifications are not permitted**
The `POST /api/schema/load` endpoint returns `403 Forbidden`. A custom `DhcpServer` node type cannot be created on the sandbox. `InfraDevice` is used as the closest available branch-aware node type to represent DHCP servers.

**The sandbox is shared**
Other users can read and modify data in the same namespaces, sites, and devices. If data appears or disappears unexpectedly, another user may have modified it. Device and namespace names should be specific enough to avoid collisions.

---

## Troubleshooting

**"Deployment not found" error from the webhook receiver**
The `acl_lifecycle_flow.py` serve process (Terminal 2) must be running before the webhook fires. Start it first and confirm it prints the "polling for scheduled runs" message.

**Flow runs appear in Prefect UI but Step 1 fails**
Check that `INFRAHUB_TOKEN` is set in `.env` and that `provisioning/infrahub_dhcp_device_upsert.py` has been run to create the baseline DHCP server devices in Infrahub.

**Webhook receiver returns 401**
Either the `INFRAHUB_WEBHOOK_SECRET` in `.env` does not match what is configured in the Infrahub UI, or the header is being sent in an unexpected format. Set `INFRAHUB_WEBHOOK_SECRET=` (empty) in `.env` to disable signature validation during testing.
