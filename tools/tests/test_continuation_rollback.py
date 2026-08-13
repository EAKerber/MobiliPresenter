import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REMOTE_FILES=[ROOT/"tools/continuation_remote.py",ROOT/"tools/continuation_live.py",ROOT/"tools/maintenance_live.py",ROOT/"tools/continuation_probe.py"]

class ContinuationRollbackTests(unittest.TestCase):
    def test_canonical_gitops_and_base_sensor_survive_remote_continuation_removal(self):
        moved=[]
        try:
            for path in REMOTE_FILES:
                if path.exists():
                    target=path.with_suffix(path.suffix+".rollback-test"); path.rename(target); moved.append((path,target))
            for command in ([sys.executable,"tools/agent.py","doctor","--json"],[sys.executable,"tools/agent.py","verify","--json"],[sys.executable,"tools/maintenance_inspect.py","--json"]):
                proc=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=False)
                self.assertEqual(proc.returncode,0,msg=f"{command}: {proc.stdout}\n{proc.stderr}")
        finally:
            for path,target in reversed(moved):
                if target.exists(): target.rename(path)

if __name__=="__main__": unittest.main()
