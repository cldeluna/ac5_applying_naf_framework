# `acl_aerleon/` — Policy Definitions and Source of Truth

## What This Directory Is

This directory holds the **network policy intent** for the Basic Data Services ACL workflow. It is shared across all solution variants in this repository (pro code, low code, no code, AI) and is intentionally kept at the repository root so that every solution reads from the same single source.

It serves two purposes:

1. **Policy generation** — the `def/` YAML files are read by the Jinja2 template engine or passed to the `aerleon` ACL compiler to produce the actual IOS ACL configuration that gets pushed to devices.
2. **Source of truth** — the `def/` files are the authoritative record of *which servers are permitted* by the policy. When a DHCP or DNS server is added or decommissioned, this is the file that changes first. That change, committed to Git, is Step 1 of the workflow.

---

## Design Decision: Why Git + YAML?

This solution was deliberately designed to use version-controlled YAML files as the policy store from the start — not as a permanent answer, but as a **pragmatic and auditable starting point** for teams that do not yet have purpose-built network source-of-truth tooling.

**What this gives you:**

- Every change to policy intent is a Git commit with a timestamp, author, and message
- Diffs are human-readable — you can see exactly which server was added or removed
- The same files can drive multiple solution approaches without duplication
- No additional infrastructure required — just a text editor and a Git client
- Authoritative users can be given write access to the repo (or a branch) through normal Git access controls

**What this does not give you:**

- Fine-grained access control below the repository level — anyone with write access can change any file
- A UI for non-engineers — network engineers or server teams who are authoritative for DNS/DHCP must be comfortable with YAML and Git
- Validation of the data — a typo in an IP address will not be caught until the ACL is generated (or fails to match traffic)
- Real-time queries — the data is static; there is no API to ask "what DNS servers are currently permitted?"

---

## Where Policy Intent Can Live — A Spectrum

The right place to store network policy intent depends on the maturity and tooling of your organisation. The options below are ordered from most pragmatic (low barrier to start) to most capable (requires investment):

### 1. Unstructured Documents *(where most teams start)*

Spreadsheets, Word documents, email threads, Confluence pages. No automation is possible directly from these. Translating them to config is entirely manual and error-prone. The data is often out of date.

**Use when:** You have no automation at all yet and are trying to understand what the current policy even is.

---

### 2. Structured Files Under Version Control *(this solution)*

YAML or JSON files checked into Git. The files have a defined schema, so automation can read them directly. Every change is tracked. This is the approach used in this repository.

```
acl_aerleon/def/
  dns.yaml      ← edit here when a DNS server changes
  dhcp.yaml     ← edit here when a DHCP server changes
  definitions.yaml
```

**Use when:** You are getting started with automation and do not yet have a network SoT platform. This is the minimum viable approach that still supports full automation.

**Limitations:** Static files. Someone authoritative must have Git access and must know to update this file when a server changes. If they forget, the next workflow run will push a stale policy.

---

### 3. Structured Files in a Shared, Accessible Location

The same YAML files, but stored in a location that non-engineers can access and edit — a shared network drive, an internal wiki with structured export, or a managed configuration repository with a web UI (e.g., Gitea, GitLab with a web editor).

**Use when:** The people who own DNS/DHCP server records are not comfortable with local Git workflows but can use a web interface.

---

### 4. Purpose-Built Network Source of Truth

A dedicated system designed to hold network data authoritatively:

| Platform | Best for |
|---|---|
| **NetBox / Nautobot** | IP addresses, prefixes, VLANs, devices, services — the most common open-source choice for network teams |
| **Infoblox / BlueCat** | DNS and DHCP records specifically; if Infoblox is already the authoritative DHCP/DNS system, the server list should come from here |
| **Cisco NSO** | Service models and device configuration intent, especially in Cisco-heavy environments |

With a proper SoT, Step 1 of the workflow becomes: *update NetBox* (or Infoblox, or NSO). The automation then queries the SoT API at runtime and the YAML files in this directory are no longer needed.

**Integration change:** Replace `impact.load_definitions()` with an API client that queries the appropriate endpoint and returns the same dict structure. Everything downstream stays the same.

**Use when:** Your organisation already has NetBox, Infoblox, or a similar platform, or is ready to invest in one. This is the target state for mature network automation.

---

### 5. CMDB or Enterprise Platforms

For organisations with a mature IT service management practice, configuration item (CI) records in a CMDB (ServiceNow, BMC Helix) may already be the authoritative record for servers and services.

**Use when:** Your CMDB is genuinely kept up to date and the network team has API access to it. In practice many CMDBs are not reliable enough to automate from directly.

---

## The Right Answer for Your Organisation

There is no universally correct answer. The decision depends on:

- **Who is authoritative** for DNS/DHCP server records in your organisation? If it is the DNS team using Infoblox, the data should come from Infoblox. If it is a network engineer maintaining a spreadsheet, YAML under version control is already a significant improvement.
- **What tooling already exists?** Do not build a NetBox deployment just to serve this use case unless there is broader organisational value.
- **What is the cost of stale data?** If the YAML file is not updated when a server changes, the next ACL push will either miss a new server or retain a decommissioned one. How often does this data change, and how quickly must the ACL reflect it?

The YAML-in-Git approach used here is a deliberate choice for a team getting started: **low infrastructure cost, full auditability, directly automation-friendly**. As automation maturity grows and a proper SoT platform is adopted, the `load_definitions()` function in `modules/impact.py` is the single integration point to replace.
