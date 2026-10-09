"""Tests for the pr-shepherd helper scripts (standard library only)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "pr-shepherd", "scripts")
sys.path.insert(0, SCRIPTS)

import check_matrix  # noqa: E402
import merge_findings  # noqa: E402
import review_packet  # noqa: E402


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class ReviewPacketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        write(os.path.join(self.repo, "AGENTS.md"), "Update docs with code.\n")
        write(os.path.join(self.repo, "src", "a.py"), "EFFORT = 'medium'\n")
        write(os.path.join(self.repo, "docs", "notes.md"), "Luna runs at medium.\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "task")
        write(os.path.join(self.repo, "src", "a.py"), "EFFORT = 'high'\n")
        git(self.repo, "commit", "-qam", "raise effort")

    def tearDown(self):
        self.tmp.cleanup()

    def run_packet(self, *extra):
        out = os.path.join(self.tmp.name, "packet")
        code = review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,felix",
                                   "--runtime", "claude", "--criteria", "Effort is high.", "--out", out, *extra])
        return code, out

    def test_writes_diff_manifest_and_role_prompts(self):
        code, out = self.run_packet()
        self.assertEqual(code, 0)
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["files"], ["src/a.py"])
        self.assertEqual(manifest["instructions"], ["AGENTS.md"])
        self.assertEqual(manifest["roles"]["maya"]["definition"], "opus-reviewer-medium")
        self.assertIn("+EFFORT = 'high'", open(os.path.join(out, "diff.patch")).read())
        maya = open(os.path.join(out, "prompts", "maya.md")).read()
        self.assertIn(manifest["head"], maya)
        self.assertIn("Leave to others:", maya)
        self.assertIn("Effort is high.", maya)
        self.assertIn("no other reviewer's findings", open(os.path.join(out, "prompts", "felix.md")).read())

    def test_opencode_runtime_uses_its_own_agents(self):
        out = os.path.join(self.tmp.name, "oc")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,felix",
                                             "--runtime", "opencode", "--out", out]), 0)
        roles = json.load(open(os.path.join(out, "manifest.json")))["roles"]
        # Felix double-checks on a different model family than Maya.
        self.assertTrue(roles["maya"]["model"].startswith("anthropic/"))
        self.assertTrue(roles["felix"]["model"].startswith("openai/"))
        self.assertEqual(roles["felix"]["definition"], "pr-shepherd-sol")

    def test_dsh_runtime_uses_its_deepseek_tools(self):
        out = os.path.join(self.tmp.name, "dsh")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,nora",
                                             "--runtime", "dsh", "--out", out]), 0)
        roles = json.load(open(os.path.join(out, "manifest.json")))["roles"]
        self.assertEqual([roles["maya"][k] for k in ("model", "effort", "definition")],
                         ["deepseek-flash", "high", "pr_shepherd_flash"])
        self.assertEqual(roles["nora"]["definition"], "pr_shepherd_flash_max")

    def test_remy_model_follows_security_signals(self):
        _, routine = review_packet.security_tier("+++ b/src/form.py\n+value = int(request.args['n'])\n")
        self.assertEqual(review_packet.security_tier("+++ b/src/form.py\n+value = clean(x)\n")[0], "remy")
        self.assertEqual(routine, {})
        # LLM tokens and config policies are not security signals.
        self.assertEqual(review_packet.security_tier("+++ b/src/llm.ts\n+const tokens = usage.output_tokens; policy.version\n")[0], "remy")
        tier, found = review_packet.security_tier(
            "+++ b/api/session.ts\n+const jwt = sign(user)\n+++ b/.github/workflows/ci.yml\n+permissions:\n")
        self.assertEqual(tier, "remy+")
        self.assertIn("authentication", found)
        self.assertIn("infra permissions", found)
        self.assertIn("cross-service", found)

    def test_production_apis_payments_and_stored_personal_data_are_sensitive(self):
        tier = lambda diff, extra=None: review_packet.security_tier(diff, extra)[0]
        self.assertEqual(tier("+++ b/src/cart.ts\n+import { createApiBuilderFromCtpClient } from '@commercetools/platform-sdk'\n"), "remy+")
        self.assertEqual(tier("+++ b/src/pay.ts\n+const intent = await stripe.paymentIntents.create(x)\n"), "remy+")
        self.assertEqual(tier("+++ b/db/migrations/012_users.sql\n+ALTER TABLE users ADD COLUMN email text;\n"), "remy+")
        self.assertEqual(tier("+++ b/src/repo.ts\n+await db.insert(newsletter).values({ email })\n"), "remy+")
        # Mentioning an email outside storage is not a signal.
        self.assertEqual(tier("+++ b/src/ui/Footer.tsx\n+<a href={`mailto:${email}`}>Contact</a>\n"), "remy")
        # Repositories can name their own production API.
        self.assertEqual(tier("+++ b/src/bff.ts\n+await bffClient.orders.get(id)\n", {"production api": r"\bbffClient\b"}), "remy+")

    def test_packet_records_the_security_tier(self):
        write(os.path.join(self.repo, "src", "auth.py"), "def login(password): ...\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "auth")
        out = os.path.join(self.tmp.name, "sec")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "remy", "--runtime", "codex", "--out", out])
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["security"]["tier"], "remy+")
        self.assertEqual(manifest["roles"]["remy"]["model"], "gpt-6.1-sol")
        self.assertEqual(manifest["roles"]["remy"]["effort"], "xhigh")
        self.assertIn("Remy uses the `remy+` row: authentication", open(os.path.join(out, "self-check.md")).read())

    def test_stale_terms_fail_the_self_check(self):
        code, out = self.run_packet("--stale", "runs at medium")
        self.assertEqual(code, 1)
        self.assertIn("docs/notes.md:1", open(os.path.join(out, "self-check.md")).read())

    def test_refuses_dirty_worktree_and_unknown_roles(self):
        write(os.path.join(self.repo, "src", "a.py"), "dirty\n")
        with self.assertRaises(SystemExit):
            self.run_packet()
        git(self.repo, "checkout", "--", ".")
        with self.assertRaises(SystemExit):
            review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "nobody", "--runtime", "codex",
                                "--out", os.path.join(self.tmp.name, "x")])


class MergeFindingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def result(self, name, body, prose=True):
        path = os.path.join(self.tmp.name, f"{name}.txt")
        text = json.dumps(body)
        write(path, f"Here is my review:\n```json\n{text}\n```\n" if prose else text)
        return path

    def test_groups_nearby_findings_and_reports_blocking(self):
        a = self.result("finn", {"role": "guidelines", "head": "abc", "status": "complete", "findings": [
            {"file": "/repo/AGENTS.md", "line": 10, "severity": "important", "impact": "stale sentence"}]})
        b = self.result("jasper", {"role": "comments", "head": "abc", "status": "complete", "findings": [
            {"file": "AGENTS.md", "line": 12, "severity": "minor", "impact": "same sentence"},
            {"file": "src/x.ts", "line": 3, "severity": "nit", "impact": "typo"}]}, prose=False)
        code = merge_findings.main([a, b, "--head", "abc", "--repo-root", "/repo", "--out", self.tmp.name])
        data = json.load(open(os.path.join(self.tmp.name, "findings.json")))
        self.assertEqual(code, 1)
        self.assertEqual(data["summary"]["groups"], 2)
        first = data["groups"][0]
        self.assertEqual((first["file"], first["severity"], first["roles"]), ("AGENTS.md", "important", ["comments", "guidelines"]))
        self.assertIn("| G1 | important |", open(os.path.join(self.tmp.name, "findings.md")).read())

    def test_incomplete_or_stale_roles_block_the_gate(self):
        a = self.result("maya", {"role": "bugs", "head": "old", "status": "complete", "findings": []})
        b = self.result("nora", {"role": "types", "head": "abc", "status": "incomplete", "findings": []})
        self.assertEqual(merge_findings.main([a, b, "--head", "abc", "--out", self.tmp.name]), 1)
        summary = json.load(open(os.path.join(self.tmp.name, "findings.json")))["summary"]
        self.assertFalse(summary["complete"])
        self.assertEqual(len(summary["problems"]), 2)

    def test_clean_complete_review_passes(self):
        a = self.result("maya", {"role": "bugs", "head": "abc", "status": "complete", "findings": []})
        self.assertEqual(merge_findings.main([a, "--head", "abc", "--out", self.tmp.name]), 0)


class OpenCodeProfileTest(unittest.TestCase):
    def run_install(self, env_keys, config=None, *extra):
        home = tempfile.mkdtemp()
        if config is not None:
            write(os.path.join(home, ".config", "opencode", "opencode.json"), config)
        root = os.path.join(home, "agents")
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        env.update({"HOME": home, **env_keys})
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "install.py"), "--install",
                               "--codex-root", os.path.join(home, "c"), "--claude-root", os.path.join(home, "d"),
                               "--claude-agents-root", os.path.join(home, "a"), "--opencode-root", root, *extra],
                              capture_output=True, text=True, env=env)
        report = json.loads(proc.stdout)
        return report, root

    def test_gpt_or_claude_keeps_the_default_links(self):
        report, root = self.run_install({"OPENAI_API_KEY": "x", "DEEPSEEK_API_KEY": "y"})
        self.assertEqual(report["opencode"]["profile"], "default")
        self.assertTrue(os.path.islink(os.path.join(root, "pr-shepherd-sol.md")))

    def test_deepseek_replaces_models_when_no_gpt_or_claude(self):
        report, root = self.run_install({"DEEPSEEK_API_KEY": "y"}, '{"provider": {"zhipuai": {}}}')
        self.assertEqual(report["opencode"]["profile"], "deepseek")
        opus = open(os.path.join(root, "pr-shepherd-opus.md")).read()
        sol = open(os.path.join(root, "pr-shepherd-sol.md")).read()
        self.assertIn("model: deepseek/deepseek-flash", opus)
        self.assertIn("model: deepseek/deepseek-flash", open(os.path.join(root, "pr-shepherd-sol-xhigh.md")).read())
        self.assertIn("model: deepseek/deepseek-flash", sol)
        self.assertNotIn("reasoningEffort", sol)
        self.assertIn("pr-shepherd-managed-copy", sol)

    def test_glm_only_when_no_gpt_claude_or_deepseek(self):
        report, root = self.run_install({}, '{"provider": {"zhipuai": {"options": {}}}}')
        self.assertEqual(report["opencode"]["profile"], "glm")
        self.assertIn("model: zhipuai/glm-5.3", open(os.path.join(root, "pr-shepherd-sol.md")).read())
        # A later run with GPT connected replaces nothing it does not own and reports the copies.
        again, _ = self.run_install({}, '{"provider": {"zhipuai": {}}}')
        self.assertTrue(all(t["status"] == "copied" for t in again["targets"] if "pr-shepherd-" in t["path"] and t["path"].endswith(".md") and "/agents/" in t["path"]))


class DshInstallTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.patch = os.path.join(self.home, "dsh", "cordis.patch.yml")

    def run_install(self, mode="--install"):
        h = self.home
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "install.py"), mode,
                               "--codex-root", os.path.join(h, "c"), "--claude-root", os.path.join(h, "d"),
                               "--claude-agents-root", os.path.join(h, "a"), "--dsh-home", os.path.join(h, "dsh")],
                              capture_output=True, text=True)
        status = {t["path"]: t["status"] for t in json.loads(proc.stdout)["targets"]}
        return proc.returncode, status.get(self.patch), status.get(os.path.join(h, "dsh", "skills", "pr-shepherd"))

    def test_appends_block_keeps_user_rows_and_is_idempotent(self):
        write(self.patch, "- id: hmr\n  disabled: true\n")
        self.assertEqual(self.run_install(), (0, "patched", "linked"))
        text = open(self.patch).read()
        self.assertTrue(text.startswith("- id: hmr\n  disabled: true\n# >>> pr-shepherd"))
        self.assertIn("toolName: pr_shepherd_flash_max", text)
        self.assertEqual(self.run_install(), (0, "patched", "linked"))
        self.assertEqual(open(self.patch).read(), text)

    def test_outdated_block_is_replaced_in_place(self):
        write(self.patch, "# >>> pr-shepherd (managed by install.py) >>>\n- insert: []\n# <<< pr-shepherd <<<\n- id: hmr\n")
        self.assertEqual(self.run_install("--check")[:2], (1, "outdated"))
        self.assertEqual(self.run_install()[1], "patched")
        text = open(self.patch).read()
        self.assertTrue(text.endswith("# <<< pr-shepherd <<<\n- id: hmr\n"))
        self.assertNotIn("- insert: []", text)

    def test_refuses_flow_lists_and_foreign_pr_shepherd_rows(self):
        for content in ("[]\n", "- insert:\n    - id: pr-shepherd-flash\n"):
            write(self.patch, content)
            self.assertEqual(self.run_install()[:2], (2, "collision"))
            self.assertEqual(open(self.patch).read(), content)


class CheckMatrixTest(unittest.TestCase):
    def test_shipped_matrix_matches_definitions_and_manifest(self):
        manifest = os.path.join(ROOT, ".claude-plugin", "plugin.json")
        self.assertEqual(check_matrix.main(["--plugin-manifest", manifest, "--today", "2026-10-09"]), 0)

    def test_old_verification_fails_only_in_strict_mode(self):
        self.assertEqual(check_matrix.main(["--today", "2027-06-01"]), 0)
        self.assertEqual(check_matrix.main(["--today", "2027-06-01", "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
