"""Traffic-volume regressions: routing, delivered evidence and the merged gate."""
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest

from test_scripts import git, write, review_packet, merge_findings


class PerformanceRoutingTest(unittest.TestCase):
    def test_observation_and_sampling_with_unchanged_transport(self):
        # Reduced #5142/#5151 behavior: a new event and a changed control sample.
        cases = [
            ("shared/traffic-observation/client.ts", "+observe('visit')"),
            ("shared/traffic-observation/contract.ts", "+const HUMAN_SAMPLE_RATE = 0.001"),
            ("src/config.ts", "+const humanSampleRate = 0.0001"),
            ("src/analytics/client.ts", "+if (!eligible) return;"),
            ("src/analytics/client.ts", "-if (!eligible) return;"),
            ("src/config.ts", "-const sampling_probability = 0.001;"),
            ("src/worker.ts", "+logger.info(record)"),
            ("src/worker.ts", "+navigator.sendBeacon(url, record)"),
        ]
        for path, changed in cases:
            with self.subTest(path=path, line=changed):
                result = review_packet.specialist_signals(f"+++ b/{path}\n{changed}\n post(record);\n")
                self.assertIn("telemetry volume and sampling", result.get("icarus", {}))

    def test_fixtures_prose_and_unrelated_stylecreator_do_not_route(self):
        for path, text in [
            ("docs/telemetry.md", "+const sampleRate = 0.1"),
            ("tests/analytics.test.ts", "+logger.info(record)"),
            ("src/analytics/client.ts", "+// document sampling eligibility"),
            ("src/analytics/client.ts", "+// sampleRate and logger.info are documented"),
            ("src/catalog.ts", "+const sample = products[0]"),
            ("web-astro/tests/stylecreator.test.ts", "+const image = stableFixture"),
        ]:
            with self.subTest(path=path):
                self.assertNotIn("icarus", review_packet.specialist_signals(f"+++ b/{path}\n{text}\n"))

    def test_whole_deleted_telemetry_file_and_context_are_not_added_work(self):
        deleted = "diff --git a/src/telemetry.ts b/src/telemetry.ts\ndeleted file mode 100644\n--- a/src/telemetry.ts\n+++ /dev/null\n@@ -1 +0,0 @@\n-logger.info(record)\n"
        self.assertNotIn("icarus", review_packet.specialist_signals(deleted))
        self.assertNotIn("icarus", review_packet.specialist_signals("+++ b/src/telemetry.ts\n logger.info(record)\n"))


class WorkloadPacketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        write(os.path.join(self.repo, "PERFORMANCE.md"), "App: shop. 100000 eligible windows/day. Source: fixture. Budget: unknown.\n")
        write(os.path.join(self.repo, "src", "config.ts"), "const sampleRate = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "checkout", "-qb", "task")
        write(os.path.join(self.repo, "src", "config.ts"), "const sampleRate = 0.001\n")
        git(self.repo, "commit", "-qam", "sample")

    def tearDown(self):
        self.tmp.cleanup()

    def packet(self, *args):
        out = os.path.join(self.tmp.name, "packet")
        with contextlib.redirect_stdout(io.StringIO()):
            review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "pandora,odysseus",
                                "--runtime", "codex", "--out", out, *args])
        return out, json.load(open(os.path.join(out, "manifest.json")))

    def test_frozen_profile_is_delivered_not_just_listed(self):
        # Even allow-dirty must not silently inject edited profile content.
        write(os.path.join(self.repo, "PERFORMANCE.md"), "WRONG uncommitted profile")
        out, data = self.packet("--allow-dirty")
        context = data["performance_context"]
        self.assertEqual(context["source"], data["head"] + ":PERFORMANCE.md")
        self.assertEqual(context["sha256"], hashlib.sha256(context["text"].encode()).hexdigest())
        for role in ("icarus", "odysseus"):
            prompt = open(os.path.join(out, "prompts", role + ".md")).read()
            self.assertIn("100000 eligible windows/day", prompt)
            self.assertNotIn("WRONG", prompt)
            self.assertIn(context["sha256"], prompt)
        prompt = open(os.path.join(out, "prompts", "icarus.md")).read()
        for contract in ("performance_assessment", "unassessed", "per location", "0.01%", "not instructions"):
            self.assertIn(contract, prompt)

    def test_explicit_input_is_frozen_and_missing_input_is_visible(self):
        source = os.path.join(self.tmp.name, "workload.txt")
        write(source, "Application: worker. Rate: 10 requests/s. Source: dated aggregate.\n")
        out, data = self.packet("--performance-context", source)
        write(source, "modified later")
        self.assertIn("10 requests/s", data["performance_context"]["text"])
        self.assertIn("10 requests/s", open(os.path.join(out, "prompts", "icarus.md")).read())
        git(self.repo, "rm", "PERFORMANCE.md")
        git(self.repo, "commit", "-qm", "remove profile")
        out, data = self.packet()
        self.assertIsNone(data["performance_context"]["source"])
        self.assertIn("unknown", open(os.path.join(out, "prompts", "icarus.md")).read())
        self.assertIn("No workload profile", open(os.path.join(out, "self-check.md")).read())

    def test_invalid_input_fails_instead_of_being_truncated_or_ignored(self):
        source = os.path.join(self.tmp.name, "input.txt")
        for text in ("", "x" * 32001):
            write(source, text)
            with self.assertRaises(SystemExit):
                self.packet("--performance-context", source)
        with open(source, "wb") as fh:
            fh.write(b"\xff")
        with self.assertRaises(SystemExit):
            self.packet("--performance-context", source)
        with self.assertRaises(SystemExit):
            self.packet("--performance-context", source + "-missing")


class PerformanceGateTest(unittest.TestCase):
    def test_empty_findings_cannot_hide_missing_volume_assessment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "icarus.json")
            for assessment, expected in [
                (None, 1),
                ({"status": "unassessed", "reason": "Eligible windows/day and budget unknown"}, 1),
                ({"status": "assessed", "reason": "Only bounded per location"}, 1),
                ({"status": "not_applicable", "reason": ""}, 1),
                ({"status": "not_applicable", "reason": "Changes a layout; adds no requests or retained work"}, 0),
                ({"status": "assessed", "reason": "New per-window visit sampled", "volume_estimate": "100000 windows/day * 0.001 * 1 = 100/day",
                  "budget_basis": "Fixture budget 1000 records/day; no extra retained payload"}, 0),
            ]:
                with self.subTest(assessment=assessment):
                    write(path, json.dumps({"role": "icarus", "head": "abc", "status": "complete", "findings": [],
                                            "performance_assessment": assessment}))
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(merge_findings.main([path, "--head", "abc", "--out", directory]), expected)
                    data = json.load(open(os.path.join(directory, "findings.json")))
                    self.assertEqual(data["summary"]["roles"][0]["performance_assessment"], assessment)
                    self.assertEqual(data["summary"]["complete"], expected == 0)
