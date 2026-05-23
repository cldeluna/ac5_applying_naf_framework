## Pro/Py Code

| Step | Activity                                     | Maps to Framework Block                    | Solution                                                     |
| ---- | -------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------ |
| 1    | Required change and its scope are documented | INTENT                                     | GItHub Repository<br />Update (commit) to YAML file          |
| 2    | Trigger                                      | ORCHESTRATION <br />PRESENTATION           | Execute a Python Script update_basic_srvs_pol.py <br />Requires a location from inventory.yml<br />option to use Jinja2 or aerleon |
| 3    | Build a new configuration artefact           | INTENT                                     | Python and Jinja2 OR Python and aerleon                      |
| 4    | Quantify Impact                              | OBSERVABILITY                              | Read from YAML File                                          |
| 5    | Check and Document Current State             | OBSERVABILITY                              | Python function - Netmiko pull show commands TextFSM from site/location in inventory file |
| 6    | Create Change Record (CR)                    | INTENT                                     | Python function create text for the ticket (Manual Ticket Creation) |
| 7    | Lab it up (Scale = 1)                        | INTENT<br />COLLECTOR                      | Python functions to create Containerlab topology to test     |
| 8    | Push update to scope                         | EXECUTOR                                   | Python script to push configuration with Netmiko             |
| 9    | Verify Changes across scope                  | OBSERVABILITY<br />COLLECTOR               | Python script Netmiko, TextFSM                               |
| 10   | Test across scope  (Scale = all scope)       | EXECUTOR<br />OBSERVABILITY<br />COLLECTOR | Python script Netmiko, TextFSM                               |
| 11   | Save/Commit across scope                     | EXECUTOR                                   | Python script Netmiko                                        |
| 12   | Final Record updates                         | ORCHESTRATION<br />EXECUTOR                | Python script - text output<br />(Manual ticket close out)   |

<!---->





 uv run aclgen --policy_file policies/pol/basic_services_includes.pol.yaml
I0522 10:27:31.665462 8798790208 aclgen.py:401] finding policies...
I0522 10:27:31.690981 8798790208 plugin_supervisor.py:248] 0 plugins active.
I0522 10:27:31.691051 8798790208 plugin_supervisor.py:249] 33 generators registered.
I0522 10:27:31.696504 8798790208 aclgen.py:336] no files changed, not writing to disk
I0522 10:27:31.696649 8798790208 aclgen.py:460] done.
(ac5-applying-naf-framework) claudiadeluna in ~/Indigo Wire Networks Dropbox/Claudia de Luna/scripts/python/2026/ac5_applying_naf_framework/acl_aerleon on main
% 