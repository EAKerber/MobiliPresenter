import copy
import unittest

from tools import agent_cycle, runtime_capabilities
from tools.semantics import brief


def unknown_runtime():
    return runtime_capabilities.build_inspection(
        {"schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA, "providers": {}}
    )


def connector_runtime():
    return runtime_capabilities.build_inspection(
        {
            "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": {
                "github-connector": {
                    "status": "PASS",
                    "features": [
                        "artifact-read", "blob-create", "ci-read",
                        "commit-create-with-parent", "content-read",
                        "content-readback", "non-force-ref-update", "pr-read",
                        "ref-read", "repository-read", "tree-create",
                        "trusted-remote-time",
                    ],
                    "reason": None,
                }
            },
        }
    )


class AgentSemanticBriefTests(unittest.TestCase):
    def test_begin_profile_builds_deterministic_brief(self):
        profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
        context = brief.normalize_context(
            role="manager-gitops",
            declared_intent="inspect-and-plan",
            lifecycle_phase=profile["lifecyclePhase"],
            objects=profile["objects"],
            operations=profile["operations"],
            scopes=profile["scope"],
        )
        runtime = unknown_runtime()
        left = brief.build_brief(context, runtime)
        right = brief.build_brief(context, runtime)
        self.assertEqual(left, right)
        self.assertFalse(left["authorizesMutation"])
        self.assertFalse(left["semanticAuthority"])
        self.assertLessEqual(len(left["maxims"]), 3)
        self.assertEqual(left["capabilityProjection"]["missingCoverage"], [])
        self.assertIn("project.inspect", left["capabilityProjection"]["required"])
        self.assertIn("routine.inspect", left["capabilityProjection"]["required"])

    def test_required_capability_remains_visible_when_scope_is_missing(self):
        context = brief.normalize_context(
            role="manager-gitops",
            declared_intent="inspect-and-plan",
            lifecycle_phase="bootstrap",
            objects=["project-state", "repository"],
            operations=["inspection"],
            scopes=["workflow:read"],
        )
        projection = brief.build_projection(context, unknown_runtime())
        self.assertIn("project.inspect", projection["required"])
        self.assertIn("project.inspect", projection["requiredUnavailable"])

    def test_provider_change_marks_existing_brief_stale(self):
        profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
        context = brief.normalize_context(
            role="manager-gitops",
            declared_intent="inspect-and-plan",
            lifecycle_phase=profile["lifecyclePhase"],
            objects=profile["objects"],
            operations=profile["operations"],
            scopes=profile["scope"],
        )
        built = brief.build_brief(context, unknown_runtime())
        freshness = brief.inspect_freshness(built, connector_runtime())
        self.assertEqual(freshness["status"], "STALE")
        self.assertIn(
            "INPUT_CHANGED:runtimeCapabilityInspectionHash",
            freshness["reasonCodes"],
        )

    def test_tampering_is_not_reclassified_as_stale(self):
        profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
        context = brief.normalize_context(
            role="manager-gitops",
            declared_intent="inspect-and-plan",
            lifecycle_phase=profile["lifecyclePhase"],
            objects=profile["objects"],
            operations=profile["operations"],
            scopes=profile["scope"],
        )
        built = brief.build_brief(context, unknown_runtime())
        tampered = copy.deepcopy(built)
        tampered["capabilityProjection"]["required"] = []
        freshness = brief.inspect_freshness(tampered, unknown_runtime())
        self.assertEqual(freshness["status"], "TAMPERED")


if __name__ == "__main__":
    unittest.main()
