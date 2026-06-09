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

The same 12-step workflow is implemented across multiple solution tiers (**no-code**, **low-code**, **pro/py-code**, and **AI-assisted**) so you can see how the framework applies regardless of tooling maturity or team skill level.
