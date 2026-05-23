# `acl_aerleon/` — Policy Definitions and Source of Truth

## What This Directory Is

This directory holds the **network policy intent** for the Basic Data Services ACL workflow. It was initially shared across all solution variants in this repository (pro code, low code, no code, AI) and kept at the repository root so every solution read from the same single source.

> **Going forward, [InfraHub](https://www.opsmill.com/infrahub/) is the designated source of truth for IP address data in this repository.** The `def/` YAML files remain in place as the policy template layer and for the Jinja2/aerleon artifact engines, but the authoritative records for DNS servers, DHCP servers, and other network objects will be held and queried from InfraHub.

This directory serves two purposes:

1. **Policy generation** — the `def/` YAML files are read by the Jinja2 template engine or passed to the `aerleon` ACL compiler to produce the actual IOS ACL configuration that gets pushed to devices.
2. **Source of truth (historical / fallback)** — the `def/` files were the authoritative record of *which servers are permitted* by the policy. With InfraHub adoption, Step 1 of the workflow becomes: update the InfraHub object, and the automation queries InfraHub at runtime to populate the network groups.

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

| Platform | Best for | Notes |
|---|---|---|
| **InfraHub** (OpsMill) | IP addresses, prefixes, devices, services — graph-based SoT with Git-like version control, schema validation, and a GraphQL API | **Designated SoT for this repository going forward.** Combines the auditability of Git with the queryability of a proper SoT platform. |
| **NetBox / Nautobot** | IP addresses, prefixes, VLANs, devices, services — the most common open-source choice for network teams | Mature ecosystem, REST and GraphQL APIs |
| **Infoblox / BlueCat** | DNS and DHCP records specifically; if Infoblox is already the authoritative DHCP/DNS system, the server list should come from here | Authoritative for DNS/DHCP if already deployed |
| **Cisco NSO** | Service models and device configuration intent, especially in Cisco-heavy environments | Best when devices are already managed via NSO |

With a proper SoT, Step 1 of the workflow becomes: *update the SoT* (add the new DHCP server in InfraHub, NetBox, or Infoblox). The automation then queries the SoT API at runtime and the YAML files in this directory are no longer the authoritative source.

**Integration change:** Replace `impact.load_definitions()` with an API client that queries the appropriate endpoint and returns the same dict structure. For InfraHub, this means a GraphQL query against the InfraHub API to retrieve the relevant IP address objects and populate `DNS_SERVERS`, `DHCP_SERVERS`, and `WEB_SERVERS` network groups. Everything downstream stays the same.

**Use when:** Your organisation already has one of these platforms or is ready to invest in one. This is the target state for mature network automation. For this repository, InfraHub is the designated target.

---

### 5. CMDB or Enterprise Platforms

For organisations with a mature IT service management practice, configuration item (CI) records in a CMDB (ServiceNow, BMC Helix) may already be the authoritative record for servers and services.

**Use when:** Your CMDB is genuinely kept up to date and the network team has API access to it. In practice many CMDBs are not reliable enough to automate from directly.

---

## The Right Answer for Your Organisation

There is no universally correct answer — but for this project, the direction is clear.

**For this repository:** InfraHub is the designated source of truth for IP address data. The YAML files in `def/` remain as the policy template layer (they define the structure that aerleon and Jinja2 use), but the IP addresses themselves will be sourced from InfraHub via its GraphQL API. The single integration point to update is `load_definitions()` in `modules/impact.py`.

**For your organisation more broadly**, the decision depends on:

- **Who is authoritative** for DNS/DHCP server records? If it is the DNS team using Infoblox, the data should come from Infoblox. If it is a network engineer maintaining a spreadsheet, YAML under version control is already a significant improvement.
- **What tooling already exists?** Do not deploy InfraHub or NetBox just to serve this one use case unless there is broader organisational value.
- **What is the cost of stale data?** If the YAML file is not updated when a server changes, the next ACL push will either miss a new server or retain a decommissioned one. A live SoT API eliminates this risk entirely.

The YAML-in-Git approach documented here represents the **starting point**: low infrastructure cost, full auditability, directly automation-friendly. InfraHub represents the **next step**: all of those properties plus a live queryable API, schema-enforced data quality, and a purpose-built interface for the people who own the data.
