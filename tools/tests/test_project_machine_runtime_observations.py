import copy
import unittest
from unittest import mock

from tools import project_machine, project_sensors, runtime_observations


def state():
    return {
        "schemaVersion": "ProjectState 2.1",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"controlBranch": "main", "protectedBranches": []},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next"},
    }


def common_sensors():
    verification = {"status": "PASS", "ok": True, "complete": True, "checks": [], "remote": None}
    capability = {
        "id": "coordination-leases",
        "policy": "canonical",
        "supervisorParticipation": "active",
        "reviewAction": "NO_EXPERIMENTAL_REVIEW",
        "nextGates": [],
        "backlogCount": 0,
        "roundsWithoutActiveGates": 0,
        "maxRoundsWithoutActiveGates": 3,
        "deferReason": None,
        "reviewPlanHash": "a" * 64,
    }
    return {
        "projectState": project_sensors.sensor("PASS", data={"verification": verification, "checks": []}, authority={"kind": "repository", "path": "ops/state/project.json"}),
        "publication": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "path": "ops/published/current.json"}),
        "git": project_sensors.sensor("PASS", data={"observed": {"worktree": True, "branch": "work/operations/provider-neutral-live-observation", "head": "9" * 40, "dirty": False}, "checks": []}, authority={"kind": "worktree"}),
        "repository": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "name": "EAKerber/MobiliPresenter"}),
        "capabilities": project_sensors.sensor("PASS", data={"items": [capability]}, authority={"kind": "repository", "path": "ops/capabilities"}),
    }


def observation(status, provider, capability, data, code=None):
    return {"status": status, "code": code, "source": {"providerId": provider, "capability": capability}, "data": data}


def bundle(provider="provider-a", *, coordination_status="PASS", coordination_code=None, remote_time="2026-08-20T00:00:00Z"):
    return runtime_observations.build_bundle(
        "EAKerber/MobiliPresenter",
        {
            "control": observation("PASS", provider, "ref.read", {"branch": "main", "sha": "1" * 40}),
            "pullRequests": observation("PASS", provider, "pr-ci.read", {"items": []}),
            "coordination": observation(
                coordination_status,
                provider,
                "coordination.read",
                {
                    "authorityBranch": "coordination/leases",
                    "authorityHead": "3" * 40,
                    "state": {"schemaVersion": "CoordinationState 0.1", "revision": "r", "intents": [], "leases": []},
                    "trustedRemoteTime": remote_time,
                },
                code=coordination_code,
            ),
            "continuations": observation("PASS", provider, "work.read", {"authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": []}),
        },
    )


class ProjectMachineRuntimeObservationTests(unittest.TestCase):
    def inspect(self, value):
        with mock.patch.object(project_machine, "_load_state", return_value=state()), mock.patch.object(
            project_machine, "_common_sensors", side_effect=lambda _: copy.deepcopy(common_sensors())
        ):
            return project_machine.inspect_live(value)

    def test_same_facts_from_different_providers_produce_same_machine_hash(self):
        a = self.inspect(bundle("provider-a"))
        b = self.inspect(bundle("provider-b"))
        self.assertEqual(a, b)
        self.assertEqual(a["inspectionHash"], b["inspectionHash"])

    def test_bundle_path_never_calls_legacy_live_adapters(self):
        with mock.patch.object(project_machine, "_load_state", return_value=state()), mock.patch.object(
            project_machine, "_common_sensors", side_effect=lambda _: copy.deepcopy(common_sensors())
        ), mock.patch.object(project_sensors, "observe_control_head", side_effect=AssertionError("legacy control called")), mock.patch.object(
            project_sensors, "observe_pull_requests", side_effect=AssertionError("legacy PR called")
        ), mock.patch.object(project_sensors, "observe_coordination", side_effect=AssertionError("legacy coordination called")), mock.patch.object(
            project_sensors, "observe_continuations_live", side_effect=AssertionError("legacy work called")
        ):
            value = project_machine.inspect_live(bundle())
        self.assertEqual(value["trust"]["status"], "PASS")

    def test_explicit_unknown_coordination_stays_unknown_without_fallback(self):
        value = self.inspect(
            bundle(
                coordination_status="UNKNOWN",
                coordination_code="TRUSTED_REMOTE_TIME_UNAVAILABLE",
                remote_time=None,
            )
        )
        self.assertEqual(value["sensors"]["control"]["status"], "PASS")
        self.assertEqual(value["sensors"]["pullRequests"]["status"], "PASS")
        self.assertEqual(value["sensors"]["continuations"]["status"], "PASS")
        self.assertEqual(value["sensors"]["coordination"]["status"], "UNKNOWN")
        self.assertEqual(value["sourceHeads"]["coordination"]["sha"], "3" * 40)
        self.assertEqual(value["trust"]["status"], "UNKNOWN")

    def test_bundle_provenance_does_not_appear_in_project_machine(self):
        value = self.inspect(bundle("external-provider-x"))
        rendered = str(value)
        self.assertNotIn("external-provider-x", rendered)
        self.assertNotIn("providerId", rendered)


if __name__ == "__main__":
    unittest.main()
