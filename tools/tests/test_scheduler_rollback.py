import subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TARGET=ROOT/'tools/scheduler_plan.py'
class RollbackTests(unittest.TestCase):
    def test_control_plane_survives_planner_removal(self):
        moved=TARGET.with_suffix('.py.rollback-test')
        try:
            TARGET.rename(moved)
            for command in ([sys.executable,'tools/agent.py','doctor','--json'],[sys.executable,'tools/agent.py','verify','--json'],[sys.executable,'tools/maintenance_inspect.py','--json'],[sys.executable,'tools/continuation.py','verify','--json']):
                proc=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=False)
                self.assertEqual(proc.returncode,0,msg=f'{command}: {proc.stdout}\n{proc.stderr}')
        finally:
            if moved.exists():moved.rename(TARGET)
if __name__=='__main__':unittest.main()
