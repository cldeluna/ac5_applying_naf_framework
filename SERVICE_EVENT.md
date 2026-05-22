# Service Intent Update/Event

Lifecycle of an Access Control List

Trigger:  An update is required.

The DNS team just brought a new DHCP server online and decomissioned an old one.

Workflow

| Step | Activity                                     | Maps to Framework Block    | Solution                                                 |
| ---- | -------------------------------------------- | -------------------------- | -------------------------------------------------------- |
| 1    | Required change and its scope are documented | INTENT                     | GItHub Repository<br />Update (commit) to YAML file      |
| 2    | Trigger                                      | ORCHESTRATION PRESENTATION | Execute a Python Script                                  |
| 3    | Build a new configuration artefact           | INTENT                     | Python and Jinja2                                        |
| 4    | Quantify Impact                              | OBSERVABILITY              | TBD                                                      |
| 5    | Check and Document Current State             | COLLECTOR                  | Python function - Netmiko pull show commands TextFSM     |
| 6    | Create Change Record (CR)                    | INTENT                     | Python function create text for the ticket               |
| 7    | Lab it up (Scale = 1)                        | INTENT                     | Python functions to create Containerlab topology to test |
| 8    | Push update to scope                         | EXECUTOR                   | Python script to push configuration with Netmiko         |
| 9    | Verify Changes across scope                  | OBSERVABILITY              | Python script Netmiko, TextFSM                           |
| 10   | Test across scope  (Scale = all scope)       | EXECUTOR                   | Python script Netmiko, TextFSM                           |
| 11   | Save/Commit across scope                     | EXECUTOR                   | Python script Netmiko                                    |
| 12   | Final Record updates                         | EXECUTOR                   | Python script - text output                              |






