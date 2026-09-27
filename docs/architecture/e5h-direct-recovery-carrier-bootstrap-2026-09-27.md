# E5h — direct recovery carrier bootstrap gate

The first post-merge live recovery attempt for E5h failed before semantic recovery evaluation. The Hosted Agent Cycle Recovery workflow executed `python tools/hosted_cycle_failure_recovery.py parse-event ...`; the public wrapper imported `tools` before placing the repository root on `sys.path`, producing `ModuleNotFoundError: No module named 'tools'`.

This checkpoint restores the same repository-root bootstrap used by direct script carriers and adds a subprocess regression that invokes the public recovery carrier as a file path. No recovery proof, certificate, authority, close policy, or external non-interference semantics are changed.

The live gate remains the same exact E5g failed close. A retry is admissible only after the follow-up PR checks are green, and success still requires semantic `HostedAgentCycleRecovery 0.3 / RECOVERED / OWN_WORK_DURABLE_DELTA_RECONCILED` rather than workflow success alone.
