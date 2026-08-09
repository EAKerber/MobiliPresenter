import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dxf_inventory import inventory

DXF = """0
SECTION
2
ENTITIES
0
3DFACE
8
MOD06
10
0
20
0
30
0
11
1200
21
0
31
0
12
1200
22
400
32
800
13
0
23
400
33
800
0
LINE
8
GLASS
10
1200
20
0
30
0
11
1208
21
400
31
2601.6
0
ENDSEC
0
EOF
"""


class TestDxfInventory(unittest.TestCase):
    def test_inventory_is_deterministic_and_metric(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dxf"
            path.write_text(DXF, encoding="ascii")
            first = inventory(path)
            second = inventory(path)
            self.assertEqual(first, second)
            self.assertEqual(first["entityCount"], 2)
            self.assertEqual(first["layers"]["MOD06"]["size"], [1200.0, 400.0, 800.0])
            self.assertEqual(first["layers"]["GLASS"]["size"], [8.0, 400.0, 2601.6])


if __name__ == "__main__":
    unittest.main()
