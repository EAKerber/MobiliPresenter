from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-write-lease-dispatch.yml"


class AgentWriteLifecycleSemanticHostWorkflowTests(unittest.TestCase):
    def test_carrier_checkout_and_semantic_host_are_distinct(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        # The current workflow revision is still the executable carrier.
        self.assertIn("ref: ${{ github.event.workflow_run.head_sha }}", text)

        # The lifecycle protocol remains bound to the semantic host that
        # produced the dispatch, even if main advanced after the cycle began.
        self.assertIn("sha=source.get('semanticHostSha')", text)
        self.assertIn('echo "semantic_host_sha=$SEMANTIC_HOST_SHA"', text)
        self.assertIn('--host-sha "$SEMANTIC_HOST_SHA"', text)
        self.assertIn(
            "HOST_SHA: ${{ steps.protocol.outputs.semantic_host_sha }}",
            text,
        )

        # Do not silently collapse carrier identity back into semantic identity.
        self.assertNotIn(
            "HOST_SHA: ${{ github.event.workflow_run.head_sha }}",
            text,
        )


if __name__ == "__main__":
    unittest.main()
