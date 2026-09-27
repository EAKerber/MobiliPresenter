from __future__ import annotations

import copy
import unittest
from unittest import mock

from tools import hosted_cycle_failure_recovery as recovery
from tools import hosted_cycle_failure_recovery_core as core
from tools import hosted_cycle_own_work_delta_recovery as own_work
from tools.canonical import stable_hash


CYCLE_INSTANCE_ID = "cycle-instance-" + "a" * 24
BRANCH = "work/operations/e5h-own-work-integrated-delta-recovery-r2"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64
SHA = "1" * 40


def _result(action: str, *, binding_hash: str, previous: str | None, planned: str, expires: str, state: str, lease_id: str = "lease:0"):
    return {
        "action": action,
        "binding": {
            "state": state,
            "leaseId": lease_id,
            "expiresAt": expires,
            "previousBindingHash": previous,
            "bindingHash": binding_hash,
        },
        "resultHash": stable_hash({"action": action, "bindingHash": binding_hash}),
        "remoteReceipt": {
            "evidence": {
                "plan": {
                    "intent": {"plannedAt": planned},
                }
            }
        },
    }


def _acquire():
    return _result(
        "acquire",
        binding_hash=HASH_A,
        previous=None,
        planned="2026-09-27T01:00:00Z",
        expires="2026-09-27T02:00:00Z",
        state="ACTIVE",
    )


def _release(*, previous: str = HASH_A, planned: str = "2026-09-27T01:30:00Z"):
    return _result(
        "release",
        binding_hash=HASH_C,
        previous=previous,
        planned=planned,
        expires="2026-09-27T02:00:00Z",
        state="RELEASED",
    )


class OwnWorkLifecycleWindowTests(unittest.TestCase):
    def _window(self, results):
        with mock.patch.object(own_work, "_lifecycle_results", return_value=copy.deepcopy(results)):
            return own_work.lifecycle_window(
                [],
                close_comment_id=100,
                cycle_instance_id=CYCLE_INSTANCE_ID,
                branch=BRANCH,
            )

    def test_acquire_release_window(self):
        value = self._window([_acquire(), _release()])
        self.assertEqual("2026-09-27T01:00:00Z", value["activeFrom"])
        self.assertEqual("2026-09-27T01:30:00Z", value["activeUntil"])
        self.assertEqual(2, len(value["resultHashes"]))

    def test_valid_renew_extends_continuous_window(self):
        renew = _result(
            "renew",
            binding_hash=HASH_B,
            previous=HASH_A,
            planned="2026-09-27T01:45:00Z",
            expires="2026-09-27T03:00:00Z",
            state="ACTIVE",
        )
        value = self._window([
            _acquire(),
            renew,
            _release(previous=HASH_B, planned="2026-09-27T02:30:00Z"),
        ])
        self.assertEqual("2026-09-27T02:30:00Z", value["activeUntil"])
        self.assertEqual(3, len(value["resultHashes"]))

    def test_renew_at_expiry_fails_closed(self):
        renew = _result(
            "renew",
            binding_hash=HASH_B,
            previous=HASH_A,
            planned="2026-09-27T02:00:00Z",
            expires="2026-09-27T03:00:00Z",
            state="ACTIVE",
        )
        with self.assertRaisesRegex(
            own_work.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_GAP",
        ):
            self._window([_acquire(), renew, _release(previous=HASH_B)])

    def test_missing_release_fails_closed(self):
        with self.assertRaisesRegex(
            own_work.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_NOT_RELEASED",
        ):
            self._window([_acquire(), _acquire()])

    def test_binding_hash_discontinuity_fails_closed(self):
        renew = _result(
            "renew",
            binding_hash=HASH_B,
            previous=HASH_D,
            planned="2026-09-27T01:45:00Z",
            expires="2026-09-27T03:00:00Z",
            state="ACTIVE",
        )
        with self.assertRaisesRegex(
            own_work.HostedCycleOwnWorkDeltaRecoveryError,
            "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID",
        ):
            self._window([_acquire(), renew, _release(previous=HASH_B)])


class RecoveryV03CertificateTests(unittest.TestCase):
    def _certificate(self):
        body = {
            "schemaVersion": recovery.RESULT_SCHEMA_V03,
            "requestId": "e5h-recovery-v03-test",
            "cycleInstanceId": CYCLE_INSTANCE_ID,
            "handleHash": HASH_A,
            "beginRequestCommentId": 1,
            "closeRequestCommentId": 2,
            "closeCommandHash": HASH_B,
            "failedCloseResultCommentId": 3,
            "failedCloseFailureHash": HASH_C,
            "writeLifecycleReportHash": HASH_D,
            "authorityHead": SHA,
            "state": "RECOVERED",
            "reasonCodes": [recovery.OWN_WORK_RECOVERY_REASON],
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
            "failedCloseRunId": 123,
            "failedCloseClosureHash": HASH_E,
            "failedCloseReceiptHash": HASH_F,
            "ownWorkIntegrationProofHash": HASH_A,
            "mergeEvidenceHashes": [HASH_B, HASH_C],
            "reconciledClosureHash": HASH_D,
            "reconciledReceiptHash": HASH_E,
        }
        return {**body, "recoveryHash": stable_hash(body)}

    def test_v03_certificate_is_accepted(self):
        value = self._certificate()
        self.assertEqual(value, recovery.validate_certificate(value))

    def test_v03_merge_hashes_must_be_canonical(self):
        value = self._certificate()
        value["mergeEvidenceHashes"] = [HASH_C, HASH_B]
        body = {key: copy.deepcopy(item) for key, item in value.items() if key != "recoveryHash"}
        value["recoveryHash"] = stable_hash(body)
        with self.assertRaisesRegex(
            recovery.HostedCycleFailureRecoveryError,
            "HOSTED_CYCLE_RECOVERY_RESULT_INVALID",
        ):
            recovery.validate_certificate(value)

    def test_v01_v02_validation_still_delegates_to_core(self):
        with mock.patch.object(core, "validate_certificate", return_value={"delegated": True}) as delegated:
            value = {"schemaVersion": core.RESULT_SCHEMA}
            self.assertEqual({"delegated": True}, recovery.validate_certificate(value))
            delegated.assert_called_once_with(value)

    def test_reentry_imports_public_validator(self):
        from tools import hosted_cycle_reentry

        self.assertIs(
            hosted_cycle_reentry.hosted_cycle_failure_recovery.validate_certificate,
            recovery.validate_certificate,
        )


if __name__ == "__main__":
    unittest.main()
