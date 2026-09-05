import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SupervisorPipelineBoundaryTests(unittest.TestCase):
    def test_operational_workflows_orchestrate_canonical_routine_lineage(self):
        agent = (ROOT / ".github/workflows/agent-ops.yml").read_text(encoding="utf-8")
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        combined = agent + "\n" + supervisor
        for forbidden in (
            "maintenance_live.py",
            "scheduler_plan.py --live",
            "maintenance_inspect.py --remote",
            "routine inspection shadow",
        ):
            self.assertNotIn(forbidden, combined.lower() if forbidden == "routine inspection shadow" else combined)
        self.assertIn("routines.py inspect --input /tmp/project-machine-inspection.json", agent)
        self.assertIn("--routines /tmp/routine-inspection.json", agent)
        self.assertIn("maintenance_inspect.py --input /tmp/project-machine-inspection.json", agent)
        self.assertLess(agent.index("routines.py inspect"), agent.index("maintenance_inspect.py --input"))
        self.assertIn("scheduler_plan.py --input /tmp/maintenance-inspection.json", agent)

        self.assertIn("routines.py inspect --input /tmp/project-machine-source.json", supervisor)
        self.assertIn("maintenance_inspect.py --input /tmp/project-machine-source.json", supervisor)
        self.assertIn("--routines /tmp/routine-inspection.json", supervisor)
        self.assertIn("scheduler_snapshot.py build", supervisor)
        self.assertIn("scheduler_snapshot.py validate", supervisor)
        self.assertIn("/tmp/project-machine-source.json", supervisor)
        self.assertIn("/tmp/routine-inspection.json", supervisor)
        self.assertIn("/tmp/project-machine-readback.json", supervisor)
        self.assertLess(supervisor.index("routines.py inspect"), supervisor.index("maintenance_inspect.py --input"))

    def test_project_machine_failures_preserve_diagnostics_before_propagation(self):
        agent = (ROOT / ".github/workflows/agent-ops.yml").read_text(encoding="utf-8")
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")

        self.assertIn("set +e", agent)
        self.assertIn("/tmp/project-machine-inspection.exit-code", agent)
        self.assertLess(agent.index("Generate Project Machine inspection"), agent.index("Upload Project Machine inspection"))
        self.assertLess(agent.index("Upload Project Machine inspection"), agent.index("Propagate Project Machine disposition"))
        agent_upload = agent.split("- name: Upload Project Machine inspection", 1)[1].split(
            "- name: Propagate Project Machine disposition", 1
        )[0]
        self.assertIn("always()", agent_upload)
        self.assertIn("/tmp/project-machine-inspection.json", agent_upload)
        self.assertIn("/tmp/project-machine-inspection.exit-code", agent_upload)

        self.assertEqual(2, supervisor.count("set +e"))
        for label, artifact, exit_code, propagate in (
            (
                "Observe source Project Machine",
                "Upload source Project Machine diagnostic",
                "/tmp/project-machine-source.exit-code",
                "Propagate source Project Machine disposition",
            ),
            (
                "Observe readback Project Machine",
                "Upload readback Project Machine diagnostic",
                "/tmp/project-machine-readback.exit-code",
                "Propagate readback Project Machine disposition",
            ),
        ):
            self.assertIn(exit_code, supervisor)
            self.assertLess(supervisor.index(label), supervisor.index(artifact))
            self.assertLess(supervisor.index(artifact), supervisor.index(propagate))
            upload = supervisor.split(f"- name: {artifact}", 1)[1].split(f"- name: {propagate}", 1)[0]
            self.assertIn("if: always()", upload)
            self.assertIn(exit_code, upload)

        self.assertNotIn("continue-on-error", agent)
        self.assertNotIn("continue-on-error", supervisor)

    def test_supervisor_snapshot_artifact_contains_routine_lineage_input(self):
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        upload = supervisor.split("name: supervisor-snapshot", 1)[1]
        self.assertIn("/tmp/routine-inspection.json", upload)
        self.assertIn("--routines /tmp/routine-inspection.json", supervisor)

    def test_supervisor_yaml_does_not_implement_artifact_contracts(self):
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        for forbidden in (
            "stable_hash",
            "MaintenanceInspection 0.",
            "SchedulerPlan 0.",
            "SchedulerSnapshot 0.",
            "projectMachineInspectionHash",
            "routineInspectionHash",
            "sourceHeads =",
        ):
            self.assertNotIn(forbidden, supervisor)

    def test_retired_maintenance_live_has_no_runtime_surface(self):
        tools = ROOT / "tools"
        self.assertFalse((tools / "maintenance_live.py").exists())
        offenders = []
        for path in tools.glob("*.py"):
            if path.name == "maintenance_live.py":
                continue
            if "maintenance_live" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
