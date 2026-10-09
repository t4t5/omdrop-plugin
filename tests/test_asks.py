"""The requests `omdrop` shows and answers, as bin/asks.py reads and writes them."""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASKS = ROOT / "bin" / "asks.py"


class AsksTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runtime = tmp.name
        before = os.environ.get("XDG_RUNTIME_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("XDG_RUNTIME_DIR", before) if before
                        else os.environ.pop("XDG_RUNTIME_DIR", None))
        os.environ["XDG_RUNTIME_DIR"] = self.runtime
        sys.path.insert(0, str(ROOT / "bin"))
        self.addCleanup(sys.path.remove, str(ROOT / "bin"))
        import asks
        self.asks = importlib.reload(asks)   # ASK_DIR follows XDG_RUNTIME_DIR
        self.asks.prepare()

    def run_cli(self, *argv):
        return subprocess.run([sys.executable, str(ASKS), *argv], capture_output=True, text=True,
                              env=dict(os.environ, XDG_RUNTIME_DIR=self.runtime))

    def publish(self, files=(), links=(), sender="Ana's iPhone", seconds=60):
        ask = {"SenderComputerName": sender,
               "Files": [{"FileName": n, "FileSize": s} for n, s in files]}
        if links:
            ask.update(TransferType={"links": 1}, Items=list(links))
        return self.asks.publish(self.asks.summarize(ask, 512), seconds)

    def test_what_is_offered_reads_as_a_sentence(self):
        describe = lambda **kw: self.asks.describe(self.asks.summarize(kw, 512))
        self.assertEqual(describe(Files=[{"FileName": "photo.jpg", "FileSize": 2_100_000}]),
                         "photo.jpg (2.1 MB)")
        self.assertEqual(describe(Files=[{"FileName": "a.jpg", "FileSize": 1000},
                                         {"FileName": "b.jpg", "FileSize": 500}]),
                         "a.jpg and 1 more (1.5 KB)")
        # A size the sender did not give is not guessed at.
        self.assertEqual(describe(Files=[{"FileName": "a.jpg"}]), "a.jpg")
        self.assertEqual(describe(TransferType={"links": 1}, Items=["https://example.com/x"]),
                         "https://example.com/x")

    def test_an_answer_reaches_the_receiver_and_only_for_a_waiting_request(self):
        ask_id = self.publish(files=[("a.txt", 1)])
        self.assertIsNone(self.asks.verdict(ask_id))
        self.assertEqual(self.run_cli("answer", ask_id, "accept").returncode, 0)
        self.assertEqual(self.asks.verdict(ask_id), "accept")
        self.asks.withdraw(ask_id)
        self.assertEqual(self.run_cli("answer", ask_id, "accept").returncode, 1)
        self.assertEqual(self.run_cli("answer", "../../etc", "accept").returncode, 1)
        self.assertEqual(self.run_cli("answer", self.publish(), "yes please").returncode, 1)

    def test_expired_requests_are_not_pending(self):
        self.publish(files=[("old.txt", 1)], seconds=-1)
        live = self.publish(files=[("new.txt", 1)])
        self.assertEqual([r["id"] for r in json.loads(self.run_cli("json").stdout)], [live])

    def test_the_toast_escapes_what_the_sender_wrote(self):
        # The shell renders a notification body as markup.
        ask_id = self.publish(files=[("<b>x</b>.txt", 3)], sender="<i>Mac</i>")
        sender, body, left = self.run_cli("toast", ask_id).stdout.splitlines()
        self.assertEqual(sender, "<i>Mac</i>")   # for the headline, which is plain text
        self.assertIn("&lt;b&gt;x&lt;", body)
        self.assertNotIn("<b>", body)
        self.assertGreater(int(left), 0)

    def test_names_lose_control_and_bidi_characters(self):
        ask_id = self.publish(files=[("gpj.\u202eexe", 1)], sender="Evil\nask pending 0123456789abcdef")
        (record,) = self.asks.pending()
        self.assertEqual(record["id"], ask_id)
        self.assertNotIn("\n", record["sender"])
        self.assertEqual(record["files"][0]["name"], "gpj.exe")


if __name__ == "__main__":
    unittest.main()
