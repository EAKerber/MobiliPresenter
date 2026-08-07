import base64
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"


class Module03SpriteProofTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((PROTOTYPE / "i4-1-assets/manifest.json").read_text())

    def test_topology_gate_is_four_drawers_two_doors(self):
        self.assertEqual(self.manifest["moduleId"], "lower-sink")
        self.assertEqual(self.manifest["topologyGate"], {"drawers": 4, "doors": 2})

    def test_sprite_integrity_matches_manifest(self):
        for key, expected in [
            ("sceneAsset", self.manifest["derived"]["sceneSha256"]),
            ("detailAsset", self.manifest["derived"]["detailSha256"]),
        ]:
            relative = self.manifest[key].removeprefix("./")
            payload = base64.b64decode((PROTOTYPE / relative).read_text().strip())
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected)

    def test_presentation_asset_cannot_supply_metric_dimensions(self):
        policies = self.manifest["policies"]
        self.assertFalse(policies["deriveMetricDimensionsFromPixels"])
        self.assertTrue(policies["fallbackRequiredWhenAssetFails"])

    def test_bootstrap_uses_sprite_proof_not_rectangular_i4_runtime(self):
        app = (PROTOTYPE / "app.js").read_text()
        self.assertIn('./i4-1/module03-sprite.js', app)
        self.assertNotIn('await import("./i4/realistic-reference.js")', app)

    def test_scene_asset_uses_fixed_camera_canvas(self):
        self.assertEqual(self.manifest["canvas"], {"width": 1423, "height": 810})
        placement = self.manifest["scenePlacement"]
        self.assertGreater(placement["width"], placement["height"])
        self.assertGreater(placement["x"], 0)
        self.assertGreater(placement["y"], 0)


if __name__ == "__main__":
    unittest.main()
