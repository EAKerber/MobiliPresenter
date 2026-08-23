from __future__ import annotations

import copy
import inspect

import pytest

from tools import coordination, coordination_transition, continuation_transition
from tools import remote_canonical

HEAD = "a" * 40
NOW = "2026-08-23T15:00:00Z"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-primary",
    "sessionId": "rp1a-test-session",
}
OWNER = {
    "role": "manager-gitops",
    "session": "rp1a-test-session",
    "branch": "work/operations/m12-rp1a-remote-request-contract-0.1",
    "pr": None,
}


def _coordination_request(**overrides):
    payload = {
        "owner": OWNER,
        "resources": ["file:tools/remote_canonical.py"],
        "reason": "verify remote canonical planning",
        "transitionId": "rp1a-coordination-test",
        "ttlSeconds": 600,
    }
    values = {
        "request_id": "rp1a-coordination-request",
        "domain": "coordination",
        "action": "intent",
        "subject": {"kind": "coordination", "id": "leases"},
        "declared_intent": {"goal": "plan-only"},
        "actor": ACTOR,
        "expected_authorities": [
            {"authority": remote_canonical.COORDINATION_AUTHORITY, "revision": HEAD}
        ],
        "allowed_authorities": [remote_canonical.COORDINATION_AUTHORITY],
        "forbidden_authorities": [],
        "planner": {
            "id": "tools.coordination_transition",
            "contract": "TransitionPlan 0.1",
        },
        "required_capabilities": ["coordination.mutate"],
        "payload": payload,
    }
    values.update(overrides)
    return remote_canonical.build_request(**values)


def _coordination_observation(head=HEAD):
    return {
        "authority": remote_canonical.COORDINATION_AUTHORITY,
        "revision": head,
        "state": coordination.empty_state(HEAD),
        "authorityNow": NOW,
    }


def _continuation_request():
    cid = "m12-rp1a-test-work"
    return remote_canonical.build_request(
        request_id="rp1a-continuation-request",
        domain="continuation",
        action="create",
        subject={"kind": "continuation", "id": cid},
        declared_intent={"goal": "create recoverable work"},
        actor=ACTOR,
        expected_authorities=[
            {"authority": remote_canonical.CONTINUATION_AUTHORITY, "revision": HEAD}
        ],
        allowed_authorities=[remote_canonical.CONTINUATION_AUTHORITY],
        forbidden_authorities=[remote_canonical.COORDINATION_AUTHORITY],
        planner={
            "id": "tools.continuation_transition",
            "contract": "TransitionPlan 0.1",
        },
        required_capabilities=["work.lifecycle.mutate"],
        payload={
            "workerId": "manager-gitops-primary",
            "remaining": ["implement-rp1a"],
            "nextAction": "implement-rp1a",
            "branch": "work/operations/m12-rp1a-remote-request-contract-0.1",
            "prNumber": None,
            "dependsOn": [],
        },
    )


def test_request_hash_is_deterministic_and_read_only():
    left = _coordination_request()
    right = _coordination_request(
        declared_intent={"goal": "plan-only"},
        expected_authorities=[
            {
                "revision": HEAD,
                "authority": {
                    "locator": {
                        "path": "ops/coordination/leases.json",
                        "branch": "coordination/leases",
                        "repository": "EAKerber/MobiliPresenter",
                    },
                    "kind": "git-authority",
                },
            }
        ],
    )
    assert left == right
    assert left["semanticAuthority"] is False
    assert left["authorizesMutation"] is False


def test_tampered_request_is_rejected():
    request = _coordination_request()
    request["declaredIntent"]["goal"] = "changed-after-hash"
    with pytest.raises(RuntimeError, match="REMOTE_REQUEST_HASH_MISMATCH"):
        remote_canonical.validate_request(request)


def test_coordination_bridge_is_semantically_identical_to_direct_planner():
    request = _coordination_request()
    observation = _coordination_observation()
    bridged = remote_canonical.plan_request(request, [observation])
    direct = coordination_transition.plan_intent(
        observation["state"],
        authority_head=HEAD,
        authority_now=NOW,
        owner=OWNER,
        resources=["file:tools/remote_canonical.py"],
        reason="verify remote canonical planning",
        transition_id="rp1a-coordination-test",
        ttl_seconds=600,
    )
    assert bridged == direct


def test_continuation_bridge_is_semantically_identical_to_direct_planner():
    request = _continuation_request()
    observation = {
        "authority": remote_canonical.CONTINUATION_AUTHORITY,
        "revision": HEAD,
        "state": {},
        "authorityNow": None,
    }
    bridged = remote_canonical.plan_request(request, [observation])
    payload = request["payload"]
    direct = continuation_transition.create(
        request["subject"]["id"],
        payload["workerId"],
        payload["remaining"],
        payload["nextAction"],
        payload["branch"],
        payload["prNumber"],
        depends_on=payload["dependsOn"],
    )
    assert bridged == direct


def test_unknown_route_fails_closed():
    request = _coordination_request(
        domain="unknown-domain",
        planner={"id": "tools.coordination_transition", "contract": "TransitionPlan 0.1"},
    )
    with pytest.raises(RuntimeError, match="REMOTE_DOMAIN_PLANNER_UNAVAILABLE"):
        remote_canonical.plan_request(request, [_coordination_observation()])


def test_planner_identity_mismatch_fails_closed():
    request = _coordination_request(
        planner={"id": "tools.continuation_transition", "contract": "TransitionPlan 0.1"}
    )
    with pytest.raises(RuntimeError, match="REMOTE_PLANNER_MISMATCH"):
        remote_canonical.plan_request(request, [_coordination_observation()])


def test_authority_drift_fails_before_planning():
    request = _coordination_request()
    with pytest.raises(RuntimeError, match="REMOTE_AUTHORITY_DRIFT"):
        remote_canonical.plan_request(request, [_coordination_observation("b" * 40)])


def test_observation_set_must_be_closed():
    request = _coordination_request()
    extra = {
        "authority": remote_canonical.CONTINUATION_AUTHORITY,
        "revision": HEAD,
        "state": {},
        "authorityNow": None,
    }
    with pytest.raises(RuntimeError, match="REMOTE_OBSERVATION_SET_MISMATCH"):
        remote_canonical.plan_request(request, [_coordination_observation(), extra])


def test_scope_cannot_silently_widen_beyond_expected_authorities():
    with pytest.raises(RuntimeError, match="REMOTE_SCOPE_MUST_MATCH_EXPECTED_AUTHORITIES"):
        _coordination_request(
            allowed_authorities=[
                remote_canonical.COORDINATION_AUTHORITY,
                remote_canonical.CONTINUATION_AUTHORITY,
            ]
        )


def test_rp1a_has_no_executor_or_remote_transport_dependency():
    source = inspect.getsource(remote_canonical)
    assert "coordination_remote" not in source
    assert "continuation_remote" not in source
    assert "project_state_apply" not in source
