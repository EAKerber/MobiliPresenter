import copy
import unittest

from tools import project_sensors, runtime_observation_sensors, runtime_observations


def state():
    return {
        "schemaVersion": "ProjectState 2.1",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"controlBranch": "main", "protectedBranches": []},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next"},
    }


def observation(status, provider, capability, data, code=None):
    return {
        "status": status,
        "code": code,
        "source": {"providerId": provider, "capability": capability},
        "data": data,
    }


def bundle(provider="provider-a", *, coordination_time="2026-08-20T00:00:00Z"):
    observations = {
        "control": observation("PASS", provider, "ref.read", {"branch": "main", "sha": "1" * 40}),
        "pullRequests": observation(
            "PASS",
            provider,
            "pr-ci.read",
            {
                "items": [
                    {
                        "number": 7,
                        "draft": False,
                        "headRef": "work/ui/example",
                        "headSha": "2" * 40,
                        "baseRef": "main",
                        "ci": "green",
                        "ciObserved": True,
                        "workflows": [
                            {"name": "verify", "status": "completed", "conclusion": "success", "id": 9}
                        ],
                    }
                ]
            },
        ),
        "coordination": observation(
            "PASS",
            provider,
            "coordination.read",
            {
                "authorityBranch": "coordination/leases",
                "authorityHead": "3" * 40,
                "state": {"schemaVersion": "CoordinationState 0.1", "revision": "r", "intents": [], "leases": []},
                "trustedRemoteTime": coordination_time,
            },
        ),
        "continuations": observation(
            "PASS",
            provider,
            "work.read",
            {"authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": []},
        ),
    }
    return runtime_observations.build_bundle("EAKerber/MobiliPresenter", observations)


class RuntimeObservationBundleTests(unittest.TestCase):
    def test_provider_identity_is_open_not_central_enum(self):
        value = bundle("provider-we-have-never-heard-of")
        self.assertEqual(
            value["observations"]["control"]["source"]["providerId"],
            "provider-we-have-never-heard-of",
        )
        self.assertEqual(runtime_observations.validate_bundle(value), value)

    def test_missing_observation_is_rejected(self):
        value = bundle()
        body = {k: copy.deepcopy(v) for k, v in value.items() if k != "bundleHash"}
        del body["observations"]["coordination"]
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_OBSERVATION_COVERAGE_INVALID"):
            runtime_observations.build_bundle(body["repository"], body["observations"])

    def test_tampered_bundle_is_rejected_even_when_shape_survives(self):
        value = bundle()
        value["observations"]["control"]["data"]["sha"] = "9" * 40
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_OBSERVATION_BUNDLE_MISMATCH"):
            runtime_observations.validate_bundle(value)

    def test_unknown_is_explicit_not_missing(self):
        value = bundle()
        observations = copy.deepcopy(value["observations"])
        observations["coordination"] = observation(
            "UNKNOWN",
            "provider-a",
            "coordination.read",
            {
                "authorityBranch": "coordination/leases",
                "authorityHead": "3" * 40,
                "state": {"schemaVersion": "CoordinationState 0.1", "revision": "r", "intents": [], "leases": []},
                "trustedRemoteTime": None,
            },
            code="TRUSTED_REMOTE_TIME_UNAVAILABLE",
        )
        explicit = runtime_observations.build_bundle("EAKerber/MobiliPresenter", observations)
        sensors = runtime_observation_sensors.observe_bundle(state(), explicit)
        self.assertEqual(sensors["coordination"]["status"], "UNKNOWN")
        self.assertEqual(sensors["coordination"]["code"], "TRUSTED_REMOTE_TIME_UNAVAILABLE")

    def test_pass_coordination_without_remote_time_is_downgraded_not_local_clocked(self):
        value = bundle(coordination_time=None)
        sensors = runtime_observation_sensors.observe_bundle(state(), value)
        self.assertEqual(sensors["coordination"]["status"], "UNKNOWN")
        self.assertEqual(sensors["coordination"]["code"], "TRUSTED_REMOTE_TIME_UNAVAILABLE")

    def test_invalid_observed_evidence_is_fail_not_unknown(self):
        value = bundle()
        observations = copy.deepcopy(value["observations"])
        observations["control"]["data"]["sha"] = "not-a-sha"
        invalid = runtime_observations.build_bundle("EAKerber/MobiliPresenter", observations)
        sensors = runtime_observation_sensors.observe_bundle(state(), invalid)
        self.assertEqual(sensors["control"]["status"], "FAIL")
        self.assertEqual(sensors["control"]["code"], "CONTROL_HEAD_INVALID")

    def test_provider_identity_does_not_leak_into_project_sensors(self):
        a = runtime_observation_sensors.observe_bundle(state(), bundle("provider-a"))
        b = runtime_observation_sensors.observe_bundle(state(), bundle("provider-b"))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
