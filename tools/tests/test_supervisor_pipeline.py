import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SupervisorPipelineBoundaryTests(unittest.TestCase):
    def test_operational_workflows_orchestrate_canonical_artifacts(self):
        agent = (ROOT / ".github/workflows/agent-ops.yml").read_text(encoding="utf-8")
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        combined = agent + "\n" + supervisor
        for forbidden in (
            "maintenance_live.py",
            "scheduler_plan.py --live",
            "maintenance_inspect.py --remote",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("maintenance_inspect.py --input /tmp/project-machine-inspection.json", agent)
        self.assertIn("scheduler_plan.py --input /tmp/maintenance-inspection.json", agent)
        self.assertIn("scheduler_snapshot.py build", supervisor)
        self.assertIn("scheduler_snapshot.py validate", supervisor)
        self.assertIn("/tmp/project-machine-source.json", supervisor)
        self.assertIn("/tmp/project-machine-readback.json", supervisor)

    def test_supervisor_yaml_does_not_implement_artifact_contracts(self):
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        for forbidden in (
            "stable_hash",
            "MaintenanceInspection 0.",
            "SchedulerPlan 0.",
            "SchedulerSnapshot 0.",
            "projectMachineInspectionHash",
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
