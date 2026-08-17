import copy,json,unittest
from unittest import mock
from tools import continuation
from tools import continuation_transition as transition
from tools import transition_protocol as protocol
from tools.continuation_remote import ContinuationRemoteError,GitHubContinuationAuthority,Observation
from tools.coordination_remote import ApiResponse

def base(work_id="task-one"):return transition.create(work_id,"developer-ui",["a","b"],"do a")["candidate"]
class FakeTransport:
    def __init__(self):self.calls=[]
    def request(self,method,endpoint,*,payload=None,include_headers=False):
        self.calls.append((method,endpoint,payload))
        if endpoint.endswith('/git/blobs'):body={'sha':'b'*40}
        elif endpoint.endswith('/git/trees'):body={'sha':'c'*40}
        elif endpoint.endswith('/git/commits'):body={'sha':'d'*40}
        elif method=='PATCH':body={}
        else:raise AssertionError((method,endpoint))
        return ApiResponse(status=200,headers={},body=json.dumps(body))
class WorkTransitionTests(unittest.TestCase):
    def test_rebuild_binds_action_intent_and_candidate(self):
        before=base();plan=transition.handoff(before,'developer-engine','continue b');self.assertEqual(transition.rebuild(plan,before),plan)
        tampered=copy.deepcopy(plan);tampered['candidate']['workerId']='other-worker';tampered['afterStateHash']=protocol.state_hash(tampered['candidate']);tampered['planHash']=protocol.stable_hash({k:v for k,v in tampered.items() if k!='planHash'})
        with self.assertRaisesRegex(RuntimeError,'CONTINUATION_PLAN_STALE'):transition.validate_plan(tampered,before,bind_before=True)
    def test_stale_subject_is_rejected_before_transport_write(self):
        before=base();plan=transition.handoff(before,'developer-engine','continue b');drifted=copy.deepcopy(before);drifted['nextAction']='different';transport=FakeTransport();authority=GitHubContinuationAuthority(transport=transport);observation=Observation('a'*40,'f'*40,{'task-one':drifted})
        with mock.patch.object(authority,'observe',return_value=observation):
            with self.assertRaises(ContinuationRemoteError) as caught:authority.apply(plan,plan['planHash'])
        self.assertEqual(caught.exception.code,'CONTINUATION_PLAN_STALE');self.assertEqual(transport.calls,[])
    def test_unrelated_valid_state_does_not_stale_subject_plan(self):
        before=base();plan=transition.handoff(before,'developer-engine','continue b');unrelated=base('task-two');transport=FakeTransport();authority=GitHubContinuationAuthority(transport=transport);observed=Observation('a'*40,'f'*40,{'task-one':before,'task-two':unrelated});readback=Observation('e'*40,'9'*40,{'task-one':plan['candidate'],'task-two':unrelated})
        with mock.patch.object(authority,'observe',side_effect=[observed,readback]):receipt=authority.apply(plan,plan['planHash'])
        self.assertTrue(receipt['verified']);protocol.validate_receipt(receipt,plan)
    def test_candidate_inventory_conflict_blocks_before_transport_write(self):
        before=base();other=transition.bind_execution(base('task-two'),'work/ui/shared',2)['candidate'];plan=transition.bind_execution(before,'work/ui/shared',1);transport=FakeTransport();authority=GitHubContinuationAuthority(transport=transport);observed=Observation('a'*40,'f'*40,{'task-one':before,'task-two':other})
        with mock.patch.object(authority,'observe',return_value=observed):
            with self.assertRaises(ContinuationRemoteError) as caught:authority.apply(plan,plan['planHash'])
        self.assertEqual(caught.exception.code,'CONTINUATION_PLAN_INVALID');self.assertEqual(transport.calls,[])
    def test_missing_expected_plan_is_rejected_before_observe(self):
        plan=transition.handoff(base(),'developer-engine','continue b');authority=GitHubContinuationAuthority(transport=FakeTransport())
        with mock.patch.object(authority,'observe') as observe:
            with self.assertRaises(ContinuationRemoteError) as caught:authority.apply(plan,None)
        self.assertEqual(caught.exception.code,'TRANSITION_EXPECTED_PLAN_REQUIRED');observe.assert_not_called()
if __name__=='__main__':unittest.main()
