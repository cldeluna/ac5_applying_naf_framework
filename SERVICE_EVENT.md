# Service Intent Update/Event

Lifecycle of an Access Control List

Trigger:  An update is required.

The DNS team just brought a new DHCP server online and decomissioned an old one.

Workflow

| Step | Activity                                     | Maps to Framework Block                    | Solution |
| ---- | -------------------------------------------- | ------------------------------------------ | -------- |
| 1    | Required change and its scope are documented | INTENT                                     |          |
| 2    | Trigger                                      | ORCHESTRATION <br />PRESENTATION           |          |
| 3    | Build a new configuration artefact           | INTENT                                     |          |
| 4    | Quantify Impact                              | OBSERVABILITY                              |          |
| 5    | Check and Document Current State             | OBSERVABILITY                              |          |
| 6    | Create Change Record (CR)                    | INTENT                                     |          |
| 7    | Lab it up (Scale = 1)                        | INTENT<br />COLLECTOR                      |          |
| 8    | Push update to scope                         | EXECUTOR                                   |          |
| 9    | Verify Changes across scope                  | OBSERVABILITY<br />COLLECTOR               |          |
| 10   | Test across scope  (Scale = all scope)       | EXECUTOR<br />OBSERVABILITY<br />COLLECTOR |          |
| 11   | Save/Commit across scope                     | EXECUTOR                                   |          |
| 12   | Final Record updates                         | ORCHESTRATION<br />EXECUTOR                |          |

<!---->

## Pro/Py Code

| Step | Activity                                     | Maps to Framework Block                    | Solution                                                     |
| ---- | -------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------ |
| 1    | Required change and its scope are documented | INTENT                                     | GItHub Repository<br />Update (commit) to YAML file          |
| 2    | Trigger                                      | ORCHESTRATION <br />PRESENTATION           | Execute a Python Script                                      |
| 3    | Build a new configuration artefact           | INTENT                                     | Python and Jinja2                                            |
| 4    | Quantify Impact                              | OBSERVABILITY                              | YAML File                                                    |
| 5    | Check and Document Current State             | OBSERVABILITY                              | Python function - Netmiko pull show commands TextFSM         |
| 6    | Create Change Record (CR)                    | INTENT                                     | Python function create text for the ticket (Manual Ticket Creation) |
| 7    | Lab it up (Scale = 1)                        | INTENT<br />COLLECTOR                      | Python functions to create Containerlab topology to test     |
| 8    | Push update to scope                         | EXECUTOR                                   | Python script to push configuration with Netmiko             |
| 9    | Verify Changes across scope                  | OBSERVABILITY<br />COLLECTOR               | Python script Netmiko, TextFSM                               |
| 10   | Test across scope  (Scale = all scope)       | EXECUTOR<br />OBSERVABILITY<br />COLLECTOR | Python script Netmiko, TextFSM                               |
| 11   | Save/Commit across scope                     | EXECUTOR                                   | Python script Netmiko                                        |
| 12   | Final Record updates                         | ORCHESTRATION<br />EXECUTOR                | Python script - text output<br />(Manual ticket close out)   |

<!---->


