import copy, tempfile, unittest, json
from pathlib import Path
from tools import capability_gates as gates
from tools import capability_transition as tx
from tools import capability_evidence as ev
from tools import capability_apply
from tools import capability_gates_ci as ci


def base():
    return {"schemaVersion":"CapabilityGates 0.1","id":"example","policy":"experimental","gates":{"backlog":[{"id":"a","test":"A"},{"id":"b","test":"B"}],"next":["a"]},"roundsWithoutActiveGates":0,"maxRoundsWithoutActiveGates":2,"deferReason":None}


class CapabilityLifecycle02Tests(unittest.TestCase):
    def test_pass_fail_require_active_evidence(self):
        with self.assertRaisesRegex(RuntimeError,"PASS_REQUIRES_EVIDENCE"): tx.passed(base(),"a",[])
        with self.assertRaisesRegex(RuntimeError,"GATE_NOT_ACTIVE"): tx.passed(base(),"b",["run:1"])
        failed=tx.failed(base(),"a",["run:red"]); self.assertEqual(failed["beforeStateHash"],failed["afterStateHash"])

    def test_pass_never_auto_promotes(self):
        plan=tx.passed(base(),"a",["run:green"]); self.assertEqual(plan["after"]["policy"],"experimental")

    def test_defer_and_limit_are_bounded(self):
        value=base(); value["gates"]["next"]=[]
        value=tx.defer(value,"representative case unavailable")["after"]; value=tx.defer(value,"still unavailable")["after"]
        with self.assertRaisesRegex(RuntimeError,"EMPTY_ROUND_LIMIT_REACHED"): tx.defer(value,"again")
        revised=tx.review_limit(value,4,"blocker remains concrete")["after"]; self.assertEqual(revised["maxRoundsWithoutActiveGates"],4); self.assertEqual(revised["roundsWithoutActiveGates"],2)

    def test_new_gate_reactivates_review(self):
        value=base(); value["gates"]["next"]=[]; value["roundsWithoutActiveGates"]=2; value["deferReason"]="old blocker"
        after=tx.gate_add(value,"c","C")["after"]; self.assertIn("c",after["gates"]["next"]); self.assertEqual(after["roundsWithoutActiveGates"],0); self.assertIsNone(after["deferReason"])

    def test_promote_is_explicit_and_requires_clean_state(self):
        with self.assertRaisesRegex(RuntimeError,"PROMOTE_REQUIRES_EMPTY_BACKLOG"): tx.promote(base(),["decision:yes"])
        value=base(); value["gates"]={"backlog":[],"next":[]}
        with self.assertRaisesRegex(RuntimeError,"PROMOTE_REQUIRES_EVIDENCE"): tx.promote(value,[])
        self.assertEqual(tx.promote(value,["decision:yes"])["after"]["policy"],"canonical")

    def test_stale_plan_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"PLAN_HASH_MISMATCH"): capability_apply.apply(tx.failed(base(),"a",["run:red"]),"wrong")

    def test_guard_replays_valid_evidence_and_rejects_forgery(self):
        before=base(); plan=tx.passed(before,"a",["run:green"]); record=ev.record(plan)
        self.assertEqual(tx.state_hash(ci.replay(before,plan["after"],[record])),plan["afterStateHash"])
        forged=copy.deepcopy(plan["after"]); forged["policy"]="canonical"
        with self.assertRaisesRegex(RuntimeError,"HEAD_STATE_NOT_EXPLAINED"): ci.replay(before,forged,[record])

    def test_full_synthetic_lifecycle(self):
        p0=tx.init("synthetic",[{"id":"a","test":"A"}],max_empty_rounds=1); s0=p0["after"]
        pf=tx.failed(s0,"a",["run:red"]); p1=tx.passed(s0,"a",["run:green"]); s1=p1["after"]
        p2=tx.defer(s1,"environment unavailable"); s2=p2["after"]; p3=tx.review_limit(s2,2,"still unavailable"); s3=p3["after"]
        p4=tx.gate_add(s3,"b","B"); s4=p4["after"]; p5=tx.passed(s4,"b",["run:b"]); s5=p5["after"]; p6=tx.promote(s5,["review:approved"])
        records=[ev.record(p) for p in (p0,pf,p1,p2,p3,p4,p5,p6)]
        self.assertEqual(ci.replay(None,p6["after"],records)["policy"],"canonical")

    def test_apply_writes_state_and_evidence_with_readback(self):
        old=(capability_apply.ROOT,capability_apply.CAPABILITY_DIR,gates.CAPABILITY_DIR)
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td); capdir=root/"ops/capabilities"; capdir.mkdir(parents=True)
                capability_apply.ROOT=root; capability_apply.CAPABILITY_DIR=capdir; gates.CAPABILITY_DIR=capdir
                (capdir/"example.json").write_text(json.dumps(base()),encoding="utf-8")
                plan=tx.passed(base(),"a",["run:green"]); result=capability_apply.apply(plan,plan["planHash"])
                self.assertTrue(result["applied"]); self.assertTrue((root/plan["evidencePath"]).exists())
        finally: capability_apply.ROOT,capability_apply.CAPABILITY_DIR,gates.CAPABILITY_DIR=old


if __name__=="__main__": unittest.main()
