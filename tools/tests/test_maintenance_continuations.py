import unittest
from tools import maintenance_inspect as m

S={"project":{"repository":"EAKerber/MobiliPresenter"},"git":{"activeDevelopmentBranch":None},"development":{"phase":"between-increments","checkpoint":"C","nextTransition":"next","prNumber":None,"blockers":[]}}
V={"ok":True,"checks":[],"remote":None}; G={"worktree":True,"branch":"main","head":"1"*40,"dirty":False}
C={"id":"coordination-leases","policy":"canonical","reviewAction":"NO_EXPERIMENTAL_REVIEW","nextGates":[],"backlogCount":0,"roundsWithoutActiveGates":0,"maxRoundsWithoutActiveGates":3,"deferReason":None,"reviewPlanHash":"a"*64}

def task(status):
    return {"id":"task-one","workerId":"developer-ui","status":status,"branch":None,"prNumber":None,"dependsOn":[],"completed":[],"remaining":["a"],"nextAction":"do a","lastKnownGood":{"sha":None,"checkpoint":None},"blockers":[],"handoffToWorkerId":None,"sourceSchemaVersion":"ContinuationState 0.1","stateHash":"b"*64}
def inspect(items):
    return m.build_inspection(S,V,G,[C],remote_requested=False,pull_requests={"available":False,"reason":"NOT_REQUESTED","items":[]},coordination_state={"available":False,"reason":"NOT_REQUESTED","intents":[],"leases":[]},work_items=items)

class Tests(unittest.TestCase):
    def test_handoff(self):
        t=task("HANDOFF"); t["handoffToWorkerId"]="developer-engine"; self.assertEqual(inspect([t])["recommendation"]["action"],"HANDOFF")
    def test_wait(self):
        t=task("WAITING"); t["blockers"]=["input"]; self.assertEqual(inspect([t])["recommendation"]["action"],"PAUSE")
    def test_runnable(self): self.assertEqual(inspect([task("IN_PROGRESS")])["recommendation"]["reasonCode"],"WORK_RUNNABLE")
    def test_done(self):
        t=task("DONE"); t["remaining"]=[]; t["nextAction"]=None; self.assertEqual(inspect([t])["recommendation"]["reasonCode"],"NEXT_TRANSITION_AVAILABLE")

if __name__=="__main__": unittest.main()
