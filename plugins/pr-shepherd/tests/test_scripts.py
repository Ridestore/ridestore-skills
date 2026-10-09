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
        self.assertEqual(roles["felix"]["definition"], "pr-shepherd-luna-xhigh")

    def test_dsh_runtime_uses_its_deepseek_tools(self):
        out = os.path.join(self.tmp.name, "dsh")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,nora",
                                             "--runtime", "dsh", "--out", out]), 0)
        roles = json.load(open(os.path.join(out, "manifest.json")))["roles"]
        self.assertEqual([roles["maya"][k] for k in ("model", "effort", "definition")],
                         ["deepseek-flash", "high", "pr_shepherd_flash"])
        self.assertEqual(roles["nora"]["definition"], "pr_shepherd_flash")
        self.assertEqual((roles["maya"]["label"], roles["nora"]["label"]),
                         ("Maya · Bugs review · Flash high", "Nora · Types review · Flash high"))

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
        self.assertEqual(manifest["roles"]["remy"]["effort"], "high")
        self.assertEqual(manifest["roles"]["remy"]["label"], "Remy · Security review (sensitive) · Sol high")
        self.assertIn("Remy uses the `remy+` row: authentication", open(os.path.join(out, "self-check.md")).read())

    def test_performance_signals_require_ruby(self):
        spec = lambda diff, extra=None: review_packet.specialist_signals(diff, extra)
        found = spec("diff --git a/src/hook.ts b/src/hook.ts\n--- a/src/hook.ts\n+++ b/src/hook.ts\n@@ -1 +1,4 @@\n"
                     "+app.post('/webhook', async (req, res) => {\n+  for (const repo of repos) {\n"
                     "+    await pool.query('SELECT 1 FROM t WHERE repo = $1', [repo]);\n+  }\n")
        self.assertIn("ruby", found)
        for name in ("request and event handlers", "database query", "query, call or await inside a loop"):
            self.assertIn(name, found["ruby"])
        self.assertIn("caching", spec("+++ b/src/cache.py\n+@functools.lru_cache(maxsize=128)\n")["ruby"])
        self.assertIn("concurrency and resource limits", spec("+++ b/src/db.ts\n+export const pool = new Pool({ max: 4 })\n")["ruby"])
        self.assertIn("module-level collection", spec("+++ b/src/state.ts\n+const seen = new Map<string, number>();\n")["ruby"])
        self.assertIn("blocking call", spec("+++ b/src/server.js\n+const body = fs.readFileSync(path)\n")["ruby"])
        self.assertIn("schema and indexes", spec("+++ b/db/migrations/014_idx.sql\n+CREATE INDEX idx_repo ON runs (repo);\n")["ruby"])
        self.assertIn("frontend rendering and loading", spec("+++ b/web/Cart.tsx\n+const total = useMemo(() => sum(items), [items])\n")["ruby"])
        # Repositories can name their own hot paths.
        self.assertIn("repo: bff", spec("+++ b/src/x.ts\n+bffClient.get(id)\n", {"ruby": {"bff": r"\bbffClient\."}})["ruby"])

    def test_docs_tests_and_plain_logic_need_no_specialist(self):
        spec = review_packet.specialist_signals
        self.assertEqual(spec("+++ b/docs/perf.md\n+Add a cache with a 30 s TTL and a semaphore.\n"), {})
        self.assertEqual(spec("+++ b/tests/test_db.py\n+cursor.execute('SELECT 1 FROM t')\n"), {})
        self.assertEqual(spec("+++ b/src/a.py\n+EFFORT = 'high'\n+total = price * qty\n"), {})
        # A release bump in package.json is not a build change.
        self.assertEqual(spec('+++ b/web/package.json\n+  "version": "0.3.598",\n+  "autoLastDeveloperCommit": "abc",\n'), {})
        self.assertIn("build and package config", spec('+++ b/web/package.json\n+    "zod": "^4.1.0",\n')["iris"])
        # A template literal is not shell parameter expansion.
        self.assertEqual(spec("+++ b/src/url.ts\n+const u = `${base}/${path}`\n"), {})

    def test_complexity_signals_require_oscar(self):
        spec = review_packet.specialist_signals
        big = "diff --git a/src/big.py b/src/big.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/big.py\n@@ -0,0 +1,300 @@\n" + \
              "".join(f"+x{i} = {i}\n" for i in range(300))
        names = spec(big)["oscar"]
        self.assertTrue(any(n.startswith("large change") for n in names))
        self.assertTrue(any(n.startswith("large new file") for n in names))
        deep = "+++ b/src/deep.py\n" + "".join("+" + " " * 24 + f"y{i} = {i}\n" for i in range(5))
        self.assertTrue(any(n.startswith("deep nesting") for n in spec(deep)["oscar"]))
        # Markup nests by design: the same depth in TSX is not deep.
        self.assertEqual(spec("+++ b/web/A.tsx\n" + "".join("+" + " " * 24 + f"<b>{i}</b>\n" for i in range(5))), {})
        wide = "".join(f"+++ b/src/m{i}.py\n+v = {i}\n" for i in range(10))
        self.assertTrue(any(n.startswith("wide change") for n in spec(wide)["oscar"]))
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.ts\n+const x = y as any\n")["oscar"])

    def test_language_signals_require_iris(self):
        spec = review_packet.specialist_signals
        self.assertIn("shell", spec("+++ b/scripts/deploy.sh\n+rm -rf \"$DIR\"\n")["iris"])
        self.assertIn("container", spec("+++ b/Dockerfile\n+RUN npm ci\n")["iris"])
        self.assertIn("ci and automation yaml", spec("+++ b/.github/workflows/ci.yml\n+  run: make\n")["iris"])
        self.assertIn("regular expressions", spec("+++ b/src/a.py\n+PAT = re.compile(r'x+')\n")["iris"])
        self.assertIn("dates, time zones and numbers", spec("+++ b/src/a.ts\n+const t = new Date('2026-10-10')\n")["iris"])
        mixed = spec("+++ b/src/a.py\n+x = 1\n+++ b/src/b.go\n+var x = 1\n")["iris"]
        self.assertTrue(any(n.startswith("several languages") for n in mixed))
        # TypeScript and JavaScript are one family.
        self.assertEqual(spec("+++ b/src/a.ts\n+x = 1\n+++ b/src/b.js\n+y = 2\n"), {})
        self.assertEqual(spec("+++ b/src/a.h\n+int x;\n+++ b/src/a.cpp\n+int y;\n"), {})

    # One added line per documented signal; each must route its role.
    SIGNAL_CASES = [
        ("ruby", "database query", "src/a.ts", "const r = await db.query('SELECT id FROM runs WHERE repo = $1', [repo])"),
        ("ruby", "network call", "src/a.py", "resp = requests.get(url, timeout=5)"),
        ("ruby", "concurrency and resource limits", "src/a.ts", "const limit = pLimit(4)"),
        ("ruby", "parallel and batch work", "src/a.ts", "await Promise.all(ids.map(load))"),
        ("ruby", "caching", "src/a.py", "@lru_cache(maxsize=1)"),
        ("ruby", "caching", "src/a.py", "@cache"),
        ("ruby", "timeouts, retries and polling", "src/a.ts", "const id = setInterval(tick, 1000)"),
        ("ruby", "blocking call", "src/a.js", "const body = fs.readFileSync(path)"),
        ("ruby", "large data and streaming", "src/a.ts", "const buf = await res.arrayBuffer()"),
        ("ruby", "large data and streaming", "src/a.sql.ts", "const q = `SELECT * FROM t LIMIT 100`"),
        ("ruby", "schema and indexes", "src/a.ts", "await knex.raw('CREATE INDEX idx_repo ON runs (repo)')"),
        ("ruby", "frontend rendering and loading", "web/A.tsx", "const Chart = dynamic(() => import('./Chart'))"),
        ("ruby", "request and event handlers", "src/a.py", '@app.get("/items")'),
        ("ruby", "request and event handlers", "src/a.ts", "app.post('/webhook', handler)"),
        ("ruby", "module-level collection", "src/a.ts", "const seen = new Map<string, number>();"),
        ("ruby", "module-level collection", "src/a.py", "REGISTRY = defaultdict(list)"),
        ("oscar", "escape hatches and dynamic code", "src/a.ts", "const x = y as any"),
        ("oscar", "escape hatches and dynamic code", "src/a.py", "    global counter"),
        ("iris", "shell", "bin/run", "#!/usr/bin/env bash"),
        ("iris", "regular expressions", "src/a.py", "PAT = re.compile(r'x+')"),
        ("iris", "dates, time zones and numbers", "src/a.ts", "const t = new Date('2026-10-10')"),
        ("iris", "encoding and unicode", "src/a.ts", "const s = name.normalize('NFC')"),
        ("iris", "encoding and unicode", "src/a.ts", "const k = name.normalize('NFKC')"),
        ("iris", "error handling and resource cleanup", "src/a.go", "\tdefer f.Close()"),
        ("iris", "error handling and resource cleanup", "src/a.cs", "using var stream = File.OpenRead(p);"),
        ("iris", "async semantics", "src/a.ts", "process.nextTick(flush)"),
        ("iris", "type system edges", "src/a.rs", "unsafe { ptr.read() }"),
        ("iris", "type system edges", "src/a.go", "var v interface{}"),
        ("iris", "module system", "src/a.mjs", "const here = import.meta.url"),
        ("iris", "error handling and resource cleanup", "src/a.ts", "process.on('SIGTERM', shutdown)"),
    ]
    # Ordinary lines the reviewers named; none may route a specialist.
    ORDINARY = [
        ("web/Button.tsx", '<button className="cursor-pointer ring-offset-2">'),
        ("web/A.tsx", "style={{ cursor: 'pointer', outlineOffset: 2 }}"),
        ("web/Page.tsx", "export default function Page() {"),
        ("src/a.js", "const x = require('y')"),
        ("src/a.py", "async def handler(request):"),
        ("src/a.py", "n = items.count(x) + names.index(y)"),
        ("web/Slider.tsx", "<Slider min={0} max={100} />"),
        ("web/Slider.tsx", "const range = { min: 1, max: 10 }"),
        ("src/a.ts", "const m = re.exec(s)"),
        ("src/a.ts", "const mask = 'XXX-XXX-XXXX'"),
        ("web/Select.tsx", "label: 'Select a size from the list'"),
        ("src/url.ts", "const u = `${base}/${path}`"),
        ("src/a.ts", "const ids = rows.filter(r => r.ok).map(r => r.id)"),
        ("config/app.toml", "tags = []"),
        ("web/package.json", '  "version": "0.3.598",'),
        ("web/package.json", '  "autoLastDeveloperCommit": "abc",'),
        ("web/components/charts/Line.tsx", "return <Line data={d} />"),
        ("locales/en.json", '  "module": "Module", "retry": "Try again",'),
        ("src/main.rs", "let rest: Vec<_> = std::env::args().skip(1).collect();"),
        ("web/index.html", '<script defer src="/a.js"></script>'),
        ("src/a.ts", "// treat as any other request"),
    ]

    def test_every_documented_signal_routes_its_role(self):
        for role, name, path, line in self.SIGNAL_CASES:
            with self.subTest(signal=name, line=line):
                found = review_packet.specialist_signals(f"+++ b/{path}\n+{line}\n")
                self.assertIn(name, found.get(role, {}))

    def test_ordinary_lines_route_no_specialist(self):
        for path, line in self.ORDINARY:
            with self.subTest(line=line):
                self.assertEqual(review_packet.specialist_signals(f"+++ b/{path}\n+{line}\n"), {})

    def test_loop_signal_follows_the_loop_body(self):
        spec = review_packet.specialist_signals
        hunk = lambda *lines: "+++ b/src/a.ts\n@@ -0,0 +1,%d @@\n" % len(lines) + "".join(f"+{l}\n" for l in lines)
        name = "query, call or await inside a loop"
        self.assertIn(name, spec(hunk("for (const r of repos) {", "  await save(r)", "}")).get("ruby", {}))
        self.assertIn(name, spec(hunk("ids.forEach(async (id) => {", "  await fetch(url + id)", "})")).get("ruby", {}))
        # After the loop has closed, or after a one-line .map, an await is sequential code.
        self.assertNotIn(name, spec(hunk("const ids = rows.map(r => r.id)", "await save(ids)")).get("ruby", {}))
        self.assertNotIn(name, spec(hunk("for (const x of xs) { total += x }", "const r = await load()")).get("ruby", {}))

    def test_nesting_uses_the_files_own_indent_unit(self):
        spec = review_packet.specialist_signals
        lines = lambda path, pad: f"+++ b/{path}\n" + "".join(f"+{pad}y{i} = {i}\n" for i in range(5))
        deep = lambda found: any(n.startswith("deep nesting") for n in found.get("oscar", {}))
        self.assertTrue(deep(spec(lines("src/deep.py", " " * 24))))
        # 4-space TypeScript three levels in, tabs three levels in, and YAML are not deep.
        self.assertFalse(deep(spec(lines("src/a.ts", " " * 12))))
        self.assertFalse(deep(spec(lines("src/a.ts", "\t" * 3))))
        self.assertFalse(deep(spec(lines("deploy/app.yaml", " " * 18))))

    def test_lockfiles_generated_files_and_test_conventions_are_skipped(self):
        spec = review_packet.specialist_signals
        lock = "+++ b/package-lock.json\n" + "".join(f'+    "lru-cache-{i}": "^1.0.0",\n' for i in range(400))
        self.assertEqual(spec(lock), {})
        for path in ("pkg/handler_test.go", "tests/conftest.py", "e2e/cart.ts", "dist/app.min.js", "src/__snapshots__/a.snap"):
            with self.subTest(path=path):
                self.assertEqual(spec(f"+++ b/{path}\n+resp = requests.get(url)\n"), {})
        release = "".join(f'+++ b/packages/p{i}/package.json\n+  "version": "1.2.{i}",\n' for i in range(12))
        self.assertEqual(spec(release), {})

    def test_several_languages_counts_files_with_added_lines(self):
        spec = review_packet.specialist_signals
        deletions = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +0,0 @@\n-x = 1\n"
                     "diff --git a/b.go b/b.go\n--- a/b.go\n+++ b/b.go\n@@ -1,1 +0,0 @@\n-var x = 1\n"
                     "diff --git a/c.json b/c.json\n--- a/c.json\n+++ b/c.json\n@@ -0,0 +1,1 @@\n+{}\n")
        self.assertEqual(spec(deletions), {})  # no crash, and no language without an added line
        mixed = spec("+++ b/src/a.py\n+x = 1\n+++ b/src/b.go\n+var x = 1\n")["iris"]
        self.assertTrue(any(n.startswith("several languages") for n in mixed))
        self.assertEqual(spec("+++ b/src/a.ts\n+x = 1\n+++ b/src/b.js\n+y = 2\n"), {})

    def test_diff_parsing_is_not_fooled_by_content_or_paths(self):
        spec, tier = review_packet.specialist_signals, review_packet.security_tier
        # A content line that starts with '++ ' is not a new file header.
        sneaky = ("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -0,0 +1,2 @@\n"
                  "+++ b/docs/x.md\n+resp = requests.get(url)\n")
        self.assertIn("network call", spec(sneaky)["ruby"])
        self.assertEqual(tier(sneaky.replace("requests.get(url)", "token = jwt.sign(user)"))[0], "remy+")
        # Names with spaces (git adds a tab) and quoted non-ASCII names keep their path.
        self.assertEqual(spec('+++ b/docs/Release notes.md\t\n+Add a cache and a semaphore.\n'), {})
        quoted = spec('+++ "b/src/caf\\303\\251.py"\n+resp = requests.get(url)\n')
        self.assertEqual(quoted["ruby"]["network call"], ["src/café.py"])

    def test_long_lines_do_not_backtrack(self):
        import time
        started = time.time()
        # The patterns themselves are bounded, even on uncapped input...
        review_packet.PERFORMANCE_RX["database query"].search("SELECT " + " " * 50000 + "x")
        review_packet.LOOP_COST.search("SELECT " + " " * 50000 + "x")
        review_packet._stores_data("select " + " " * 50000 + "x")
        for rx in list(review_packet.PERFORMANCE_RX.values()) + list(review_packet.LANGUAGE_RX.values()):
            rx.search("a" + " " * 20000 + "(" * 2000)
        # ...and the scanners stay fast on a long minified line.
        review_packet.specialist_signals("+++ b/src/bundle.js\n+SELECT " + " " * 50000 + "x\n")
        review_packet.security_tier("+++ b/src/bundle.js\n+email select " + " " * 50000 + "x\n")
        self.assertLess(time.time() - started, 2)

    def test_security_scans_whole_lines(self):
        line = "+const cfg = {cert: '" + "A" * 2500 + "', apiKey: process.env.X}\n"
        self.assertEqual(review_packet.security_tier("+++ b/src/config.ts\n" + line)[0], "remy+")

    def test_deleted_renamed_and_binary_files(self):
        spec, tier = review_packet.specialist_signals, review_packet.security_tier
        deleted = ("diff --git a/db/migrations/012.sql b/db/migrations/012.sql\ndeleted file mode 100644\n"
                   "--- a/db/migrations/012.sql\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-CREATE INDEX i ON t (c);\n")
        self.assertEqual(spec(deleted), {})
        renamed = ("diff --git a/api/x.ts b/auth/session.ts\nsimilarity index 100%\n"
                   "rename from api/x.ts\nrename to auth/session.ts\n")
        self.assertEqual(tier(renamed)[0], "remy+")
        binary = "diff --git a/Dockerfile.png b/Dockerfile\nnew file mode 100644\nBinary files /dev/null and b/Dockerfile differ\n"
        self.assertIn("container", spec(binary)["iris"])

    def test_container_ci_and_prose_lines_route_no_ruby_or_oscar(self):
        spec = review_packet.specialist_signals
        for path, line in (("Dockerfile", "RUN apk add --no-cache curl"), ("Dockerfile", "HEALTHCHECK --timeout=3s --retries=3 CMD x"),
                           ("docker-compose.yml", "      retries: 5"), (".github/workflows/ci.yml", "      cache: npm"),
                           (".github/workflows/ci.yml", "    timeout-minutes: 10")):
            with self.subTest(line=line):
                self.assertNotIn("ruby", spec(f"+++ b/{path}\n+{line}\n"))
        for path, line in (("scripts/entry.sh", 'exec "$@"'), ("src/a.ts", "// keep the global flag off"),
                           ("src/a.py", "flags = {n: any(p.match(n) for p in pats) for n in names}"),
                           ("src/a.ts", 'throw new Error("Invalid input: any of a, b required")'),
                           ("db/migrations/1.sql", "-- FIXME: split later"), ("web/a.scss", "/* HACK */")):
            with self.subTest(line=line):
                self.assertNotIn("oscar", spec(f"+++ b/{path}\n+{line}\n"))
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.ts\n+function f(x: any) {}\n")["oscar"])
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.py\n+    global counter\n")["oscar"])

    def test_package_json_keys_and_requirements(self):
        spec = review_packet.specialist_signals
        self.assertIn("module system", spec('+++ b/package.json\n+  "exports": {\n')["iris"])
        self.assertEqual(spec('+++ b/locales/en.json\n+  "main": "Main menu",\n'), {})
        self.assertIn("build and package config", spec("+++ b/requirements.txt\n+httpx==0.28.1\n")["iris"])
        # Output dirs are skipped only at a repo or package root.
        self.assertEqual(spec("+++ b/packages/web/dist/app.js\n+fetch(url)\n"), {})
        self.assertIn("ruby", spec("+++ b/tools/build/bundle.ts\n+await fetch(url)\n"))

    def test_odd_indents_and_hunks_do_not_skew_nesting_or_loops(self):
        spec = review_packet.specialist_signals
        jsdoc = "+++ b/src/a.ts\n+    /**\n+     * @param id\n+     */\n" + "".join(f"+            y{i}();\n" for i in range(5))
        self.assertFalse(any(n.startswith("deep nesting") for n in spec(jsdoc).get("oscar", {})))
        two_hunks = ("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1,2 +1,2 @@\n"
                     "     for row in rows:\n         total += row.n\n@@ -90,1 +90,2 @@\n         x = 1\n+        data = await self.load()\n")
        self.assertNotIn("query, call or await inside a loop", spec(two_hunks).get("ruby", {}))
        async_for = "+++ b/src/a.py\n@@ -0,0 +1,2 @@\n+    async for row in rows:\n+        await send(row)\n"
        self.assertIn("query, call or await inside a loop", spec(async_for)["ruby"])
        crlf = "+++ b/src/a.py\n+REGISTRY = defaultdict(list)\r\n"
        self.assertIn("module-level collection", spec(crlf)["ruby"])

    def test_lone_carriage_return_does_not_shift_hunks(self):
        path = os.path.join(self.repo, "src", "cr.py")
        with open(path, "wb") as fh:
            fh.write(b'q = "\r"\ntok = 1\n++ b/docs/x.md\nresp = requests.get(url)\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "cr")
        out = os.path.join(self.tmp.name, "cr")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude", "--out", out])
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertIn("network call", manifest["specialists"]["ruby"]["signals"])

    def test_repository_signals_add_and_never_replace(self):
        extra = review_packet.compile_extra_signals(["ruby:database query=(?!)"], review_packet.SPECIALISTS)
        found = review_packet.specialist_signals("+++ b/src/a.ts\n+await db.query('x')\n", extra)
        self.assertIn("database query", found["ruby"])
        self.assertEqual(review_packet.security_tier("+++ b/api/s.ts\n+const jwt = sign(user)\n",
                                                     {"authentication": "(?!)"})[0], "remy+")
        for bad in ("ruby:x=(", "maya:x=y", "ruby:=y", "ruby:x=a{99999999999}"):
            with self.subTest(item=bad), self.assertRaises(SystemExit):
                review_packet.compile_extra_signals([bad], review_packet.SPECIALISTS)
        for bad in ("api=(", "api"):
            with self.subTest(item=bad), self.assertRaises(SystemExit) as raised:
                self.run_packet("--security-signal", bad)
            self.assertIn("--security-signal", str(raised.exception))

    def test_packet_adds_signalled_specialists_to_the_plan(self):
        write(os.path.join(self.repo, "src", "hook.py"),
              "import requests\n\ndef handle(repos):\n    for r in repos:\n        requests.get(r)\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "hook")
        out = os.path.join(self.tmp.name, "spec")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,felix",
                                             "--runtime", "claude", "--out", out]), 0)
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertIn("ruby", manifest["roles"])
        self.assertTrue(manifest["specialists"]["ruby"]["added"])
        self.assertIn("network call", manifest["specialists"]["ruby"]["signals"])
        self.assertTrue(os.path.isfile(os.path.join(out, "prompts", "ruby.md")))
        self.assertIn("Ruby (performance) (added to the plan): ", open(os.path.join(out, "self-check.md")).read())
        # A fix check routes on the changes since the reviewed head only.
        head = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        write(os.path.join(self.repo, "src", "a.py"), "EFFORT = 'xhigh'\n")
        git(self.repo, "commit", "-qam", "fix")
        out2 = os.path.join(self.tmp.name, "spec2")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude",
                            "--previous-head", head, "--out", out2])
        manifest2 = json.load(open(os.path.join(out2, "manifest.json")))
        self.assertEqual(list(manifest2["roles"]), ["maya"])
        self.assertEqual(manifest2["specialists"], {})

    def test_specialist_signal_flag_is_validated(self):
        with self.assertRaises(SystemExit):
            self.run_packet("--specialist-signal", "maya:x=y")
        code, out = self.run_packet("--specialist-signal", "oscar:effort constant=EFFORT")
        self.assertEqual(code, 0)
        self.assertIn("repo: effort constant", json.load(open(os.path.join(out, "manifest.json")))["specialists"]["oscar"]["signals"])

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
        self.assertTrue(os.path.islink(os.path.join(root, "pr-shepherd-luna-xhigh.md")))

    def test_deepseek_replaces_models_when_no_gpt_or_claude(self):
        report, root = self.run_install({"DEEPSEEK_API_KEY": "y"}, '{"provider": {"zhipuai": {}}}')
        self.assertEqual(report["opencode"]["profile"], "deepseek")
        opus = open(os.path.join(root, "pr-shepherd-opus.md")).read()
        luna = open(os.path.join(root, "pr-shepherd-luna-xhigh.md")).read()
        self.assertIn("model: deepseek/deepseek-flash", opus)
        self.assertIn("model: deepseek/deepseek-flash", open(os.path.join(root, "pr-shepherd-sol-high.md")).read())
        self.assertIn("model: deepseek/deepseek-flash", luna)
        self.assertNotIn("reasoningEffort", luna)
        self.assertIn("pr-shepherd-managed-copy", luna)

    def test_glm_only_when_no_gpt_claude_or_deepseek(self):
        report, root = self.run_install({}, '{"provider": {"zhipuai": {"options": {}}}}')
        self.assertEqual(report["opencode"]["profile"], "glm")
        self.assertIn("model: zhipuai/glm-5.3", open(os.path.join(root, "pr-shepherd-luna-xhigh.md")).read())
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

    def test_new_home_patch_gets_normal_file_mode(self):
        self.assertEqual(self.run_install()[1], "patched")
        umask = os.umask(0)
        os.umask(umask)
        self.assertEqual(os.stat(self.patch).st_mode & 0o777, 0o666 & ~umask)

    def test_end_marker_at_end_of_file_without_newline(self):
        write(self.patch, "- id: hmr\n# >>> pr-shepherd (managed by install.py) >>>\n- insert: []\n# <<< pr-shepherd <<<")
        self.assertEqual(self.run_install()[:2], (0, "patched"))
        self.assertTrue(open(self.patch).read().endswith("# <<< pr-shepherd <<<\n"))

    def test_keeps_crlf_and_allows_id_overrides_of_managed_rows(self):
        write(self.patch, "- id: hmr\r\n  disabled: true\r\n")
        self.assertEqual(self.run_install()[1], "patched")
        with open(self.patch, newline="") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("- id: hmr\r\n  disabled: true\r\n# >>> pr-shepherd"))
        self.assertEqual(text.count("\n"), text.count("\r\n"))
        override = text + "- id: pr-shepherd-flash  # tuned\r\n  config:\r\n    toolName: pr_shepherd_flash\r\n"
        with open(self.patch, "w", newline="") as fh:
            fh.write(override)
        self.assertEqual(self.run_install()[:2], (0, "patched"))

    def test_refuses_override_before_the_managed_block(self):
        write(self.patch, "- id: pr-shepherd-flash\n  disabled: true\n")
        self.assertEqual(self.run_install()[:2], (2, "collision"))
        self.assertEqual(open(self.patch).read(), "- id: pr-shepherd-flash\n  disabled: true\n")

    def test_refuses_flow_lists_and_foreign_pr_shepherd_rows(self):
        for content in ("[]\n", "  - id: hmr\n    disabled: true\n", "- insert:\n    - id: pr-shepherd-flash\n",
                        "- insert:\n    - name: x\n      id: 'pr-shepherd-flash'\n",
                        "- insert:\n    - id: mine\n      config: {toolName: pr_shepherd_flash}\n"):
            write(self.patch, content)
            self.assertEqual(self.run_install()[:2], (2, "collision"))
            self.assertEqual(open(self.patch).read(), content)


class RetiredAgentTest(unittest.TestCase):
    def test_removes_retired_claude_xhigh_links(self):
        home = tempfile.mkdtemp()
        agents = os.path.join(home, "a")
        os.makedirs(agents)
        dest = os.path.join(agents, "opus-reviewer-xhigh.md")
        os.symlink(os.path.join(os.path.dirname(SCRIPTS), "agents", "opus-reviewer-xhigh.md"), dest)
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "install.py"), "--install", "--codex-root",
                        os.path.join(home, "c"), "--claude-root", os.path.join(home, "d"), "--claude-agents-root", agents],
                       capture_output=True, check=True)
        self.assertFalse(os.path.lexists(dest))
        self.assertTrue(os.path.islink(os.path.join(agents, "sonnet-reviewer-medium.md")))
        # A user's own Claude agent is kept even if it carries the managed-copy marker.
        write(dest, "---\n# pr-shepherd-managed-copy (deepseek)\nname: mine\n---\n")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "install.py"), "--install", "--codex-root",
                        os.path.join(home, "c"), "--claude-root", os.path.join(home, "d"), "--claude-agents-root", agents],
                       capture_output=True, check=True)
        self.assertTrue(os.path.isfile(dest))

    def test_removes_our_retired_sol_agent_link(self):
        home = tempfile.mkdtemp()
        root = os.path.join(home, "oc")
        os.makedirs(root)
        dest = os.path.join(root, "pr-shepherd-sol.md")
        os.symlink(os.path.join(os.path.dirname(SCRIPTS), "agents", "opencode", "pr-shepherd-sol.md"), dest)
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "install.py"), "--install", "--codex-root", os.path.join(home, "c"),
                        "--claude-root", os.path.join(home, "d"), "--claude-agents-root", os.path.join(home, "a"),
                        "--opencode-root", root, "--opencode-profile", "default"], capture_output=True, check=True)
        self.assertFalse(os.path.lexists(dest))
        self.assertTrue(os.path.islink(os.path.join(root, "pr-shepherd-luna-xhigh.md")))

    def test_removes_our_retired_sol_managed_copy_but_keeps_a_users_file(self):
        home = tempfile.mkdtemp()
        root = os.path.join(home, "oc")
        dest = os.path.join(root, "pr-shepherd-sol.md")
        args = [sys.executable, os.path.join(SCRIPTS, "install.py"), "--codex-root", os.path.join(home, "c"),
                "--claude-root", os.path.join(home, "d"), "--claude-agents-root", os.path.join(home, "a"),
                "--opencode-root", root, "--opencode-profile", "deepseek"]
        write(dest, "---\n# pr-shepherd-managed-copy (deepseek)\nmodel: deepseek/deepseek-flash\n---\n")
        self.assertEqual(subprocess.run(args + ["--check"], capture_output=True).returncode, 1)
        subprocess.run(args + ["--install"], capture_output=True, check=True)
        self.assertFalse(os.path.lexists(dest))
        self.assertIn("model: deepseek/deepseek-flash", open(os.path.join(root, "pr-shepherd-luna-xhigh.md")).read())
        write(dest, "---\nmodel: mine\n---\n")
        subprocess.run(args + ["--install"], capture_output=True, check=True)
        self.assertTrue(os.path.isfile(dest))

    def test_removes_only_our_retired_astra_agent(self):
        home = tempfile.mkdtemp()
        root = os.path.join(home, "oc")
        os.makedirs(root)
        source_agents = os.path.join(os.path.dirname(SCRIPTS), "agents", "opencode")
        os.symlink(os.path.join(source_agents, "pr-shepherd-astra.md"), os.path.join(root, "pr-shepherd-astra.md"))
        args = [sys.executable, os.path.join(SCRIPTS, "install.py"), "--codex-root", os.path.join(home, "c"),
                "--claude-root", os.path.join(home, "d"), "--claude-agents-root", os.path.join(home, "a"),
                "--opencode-root", root, "--opencode-profile", "default"]
        self.assertEqual(subprocess.run(args + ["--check"], capture_output=True).returncode, 1)
        subprocess.run(args + ["--install"], capture_output=True, check=True)
        self.assertFalse(os.path.lexists(os.path.join(root, "pr-shepherd-astra.md")))
        write(os.path.join(root, "pr-shepherd-astra.md"), "my own agent\n")
        self.assertEqual(subprocess.run(args + ["--check"], capture_output=True).returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(root, "pr-shepherd-astra.md")))


class CheckMatrixTest(unittest.TestCase):
    def test_shipped_matrix_matches_definitions_and_manifest(self):
        manifest = os.path.join(ROOT, ".claude-plugin", "plugin.json")
        self.assertEqual(check_matrix.main(["--plugin-manifest", manifest, "--today", "2026-10-09"]), 0)

    def test_dsh_tools_must_match_matrix_and_stay_read_only(self):
        skill = os.path.join(ROOT, "skills", "pr-shepherd")
        mutations = {"reasoningEffort: max": "reasoningEffort: low", "maxDepth: 1": "maxDepth: 2",
                     "allow: [read, grep, glob]": "allow: [read, grep, glob, bash]",
                     "provider: deepseek-official": "provider: openai",
                     "reasoningEffort: high": "reasoningEffort: medium",
                     "toolName: pr_shepherd_flash_max": "toolName: pr_shepherd_flash",
                     "maxDepth: 1\n        persona": "maxDepth: 1\n        modelSelectionSettings: true\n        persona"}
        for old, new in mutations.items():
            with tempfile.TemporaryDirectory() as tmp:
                copy = os.path.join(tmp, "pr-shepherd")
                subprocess.run(["cp", "-R", skill, copy], check=True)
                patch = os.path.join(copy, "agents", "dsh", "cordis.patch.yml")
                text = open(patch).read()
                self.assertIn(old, text)
                write(patch, text.replace(old, new))
                self.assertEqual(check_matrix.main(["--skill-dir", copy, "--today", "2026-10-09"]), 1, new)

    def test_old_verification_fails_only_in_strict_mode(self):
        self.assertEqual(check_matrix.main(["--today", "2027-06-01"]), 0)
        self.assertEqual(check_matrix.main(["--today", "2027-06-01", "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
