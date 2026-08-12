import subprocess
import unittest
from unittest import mock

from tools import coordination_remote
from tools.coordination_remote import CoordinationRemoteError, GhApiTransport


class CoordinationRemoteTimeoutTests(unittest.TestCase):
    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(CoordinationRemoteError) as caught:
            GhApiTransport(timeout_seconds=0)
        self.assertEqual(caught.exception.code, "COORDINATION_REMOTE_CONFIG_INVALID")

    def test_stalled_gh_api_fails_closed(self):
        transport = GhApiTransport(timeout_seconds=3)
        with mock.patch.object(coordination_remote.shutil, "which", return_value="/usr/bin/gh"):
            with mock.patch.object(
                coordination_remote.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd=["gh", "api"], timeout=3),
            ):
                with self.assertRaises(CoordinationRemoteError) as caught:
                    transport.request("GET", "repos/EAKerber/MobiliPresenter/git/ref/heads/coordination%2Fleases")
        self.assertEqual(caught.exception.code, "COORDINATION_REMOTE_TIMEOUT")
        self.assertIn("exceeded 3s", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
