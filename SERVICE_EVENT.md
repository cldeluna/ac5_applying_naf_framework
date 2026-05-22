# Service Intent Update/Event

Lifecycle of an Access Control List

Trigger:  An update is required.

The DNS team just brought a new DHCP server online and decomissioned an old one.

Workflow

| Step | Activity                                     | Maps to Framework Block    | Solution |
| ---- | -------------------------------------------- | -------------------------- | -------- |
| 1    | Required change and its scope are documented | INTENT                     |          |
| 2    | Trigger                                      | ORCHESTRATION PRESENTATION |          |
| 3    | Build a new configuration artefact           | INTENT                     |          |
| 4    | Quantify Impact                              | OBSERVABILITY              |          |
| 5    | Check and Document Current State             | COLLECTOR                  |          |
| 6    | Create Change Record (CR)                    | INTENT                     |          |
| 7    | Lab it up (Scale = 1)                        | INTENT                     |          |
| 8    | Push update to scope                         | EXECUTOR                   |          |
| 9    | Verify Changes across scope                  | OBSERVABILITY              |          |
| 10   | Test across scope  (Scale = all scope)       | EXECUTOR                   |          |
| 11   | Save/Commit across scope                     | EXECUTOR                   |          |
| 12   | Final Record updates                         | EXECUTOR                   |          |






