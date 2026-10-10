"""Tests for the pr-shepherd helper scripts (standard library only)."""

import json
import os
import re
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
        code = review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "pandora,odysseus",
                                   "--runtime", "claude", "--criteria", "Effort is high.", "--out", out, *extra])
        return code, out

    def test_writes_diff_manifest_and_role_prompts(self):
        code, out = self.run_packet()
        self.assertEqual(code, 0)
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["files"], ["src/a.py"])
        self.assertEqual(manifest["instructions"], ["AGENTS.md"])
        self.assertEqual(manifest["roles"]["pandora"]["definition"], "opus-reviewer-medium")
        self.assertIn("+EFFORT = 'high'", open(os.path.join(out, "diff.patch")).read())
        pandora = open(os.path.join(out, "prompts", "pandora.md")).read()
        self.assertIn(manifest["head"], pandora)
        self.assertIn("Leave to others:", pandora)
        self.assertIn("Effort is high.", pandora)
        self.assertIn("no other reviewer's findings", open(os.path.join(out, "prompts", "odysseus.md")).read())

    def test_opencode_runtime_uses_its_own_agents(self):
        out = os.path.join(self.tmp.name, "oc")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "pandora,odysseus",
                                             "--runtime", "opencode", "--out", out]), 0)
        roles = json.load(open(os.path.join(out, "manifest.json")))["roles"]
        # Odysseus double-checks on a different model family than Pandora.
        self.assertTrue(roles["pandora"]["model"].startswith("anthropic/"))
        self.assertTrue(roles["odysseus"]["model"].startswith("openai/"))
        self.assertEqual(roles["odysseus"]["definition"], "pr-shepherd-luna-xhigh")

    def test_dsh_runtime_uses_its_deepseek_tools(self):
        out = os.path.join(self.tmp.name, "dsh")
        self.assertEqual(review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "pandora,proteus",
                                             "--runtime", "dsh", "--out", out]), 0)
        roles = json.load(open(os.path.join(out, "manifest.json")))["roles"]
        self.assertEqual([roles["pandora"][k] for k in ("model", "effort", "definition")],
                         ["deepseek-flash", "high", "pr_shepherd_flash"])
        self.assertEqual(roles["proteus"]["definition"], "pr_shepherd_flash")
        self.assertEqual((roles["pandora"]["label"], roles["proteus"]["label"]),
                         ("Pandora · Bugs review · Flash high", "Proteus · Types review · Flash high"))

    def test_security_model_follows_security_signals(self):
        _, routine = review_packet.security_tier("+++ b/src/form.py\n+value = int(request.args['n'])\n")
        self.assertEqual(review_packet.security_tier("+++ b/src/form.py\n+value = clean(x)\n")[0], "artemis")
        self.assertEqual(routine, {})
        # LLM tokens and config policies are not security signals.
        self.assertEqual(review_packet.security_tier("+++ b/src/llm.ts\n+const tokens = usage.output_tokens; policy.version\n")[0], "artemis")
        tier, found = review_packet.security_tier(
            "+++ b/api/session.ts\n+const jwt = sign(user)\n+++ b/.github/workflows/ci.yml\n+permissions:\n")
        self.assertEqual(tier, "athena")
        self.assertIn("authentication", found)
        self.assertIn("infra permissions", found)
        self.assertIn("cross-service", found)

    def test_production_apis_payments_and_stored_personal_data_are_sensitive(self):
        tier = lambda diff, extra=None: review_packet.security_tier(diff, extra)[0]
        self.assertEqual(tier("+++ b/src/cart.ts\n+import { createApiBuilderFromCtpClient } from '@commercetools/platform-sdk'\n"), "athena")
        self.assertEqual(tier("+++ b/src/pay.ts\n+const intent = await stripe.paymentIntents.create(x)\n"), "athena")
        self.assertEqual(tier("+++ b/db/migrations/012_users.sql\n+ALTER TABLE users ADD COLUMN email text;\n"), "athena")
        self.assertEqual(tier("+++ b/src/repo.ts\n+await db.insert(newsletter).values({ email })\n"), "athena")
        # Mentioning an email outside storage is not a signal.
        self.assertEqual(tier("+++ b/src/ui/Footer.tsx\n+<a href={`mailto:${email}`}>Contact</a>\n"), "artemis")
        # Repositories can name their own production API.
        self.assertEqual(tier("+++ b/src/bff.ts\n+await bffClient.orders.get(id)\n", {"production api": r"\bbffClient\b"}), "athena")

    def test_packet_records_the_security_tier(self):
        write(os.path.join(self.repo, "src", "auth.py"), "def login(password): ...\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "auth")
        out = os.path.join(self.tmp.name, "sec")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "artemis", "--runtime", "codex", "--out", out])
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["security"]["tier"], "athena")
        self.assertEqual(manifest["roles"]["athena"]["model"], "gpt-6.1-sol")
        self.assertEqual(manifest["roles"]["athena"]["effort"], "high")
        self.assertEqual(manifest["roles"]["athena"]["label"], "Athena · Security review (sensitive) · Sol high")
        self.assertIn("Athena uses the `athena` row: authentication", open(os.path.join(out, "self-check.md")).read())

    def test_legacy_names_produce_new_packet_identities_without_renaming_models(self):
        out = os.path.join(self.tmp.name, "legacy")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya,theo,luna,remy+,pandora",
                            "--runtime", "codex", "--out", out])
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["security"]["tier"], "athena")
        roles = manifest["roles"]
        self.assertEqual(list(roles), ["pandora", "daedalus", "ariadne", "athena"])
        self.assertEqual(roles["ariadne"]["model"], "gpt-6-luna")
        self.assertEqual(roles["athena"]["model"], "gpt-6.1-sol")
        self.assertTrue(os.path.isfile(os.path.join(out, "prompts", "pandora.md")))
        self.assertFalse(os.path.exists(os.path.join(out, "prompts", "maya.md")))

    def test_performance_signals_require_icarus(self):
        spec = lambda diff, extra=None: review_packet.specialist_signals(diff, extra)
        found = spec("diff --git a/src/hook.ts b/src/hook.ts\n--- a/src/hook.ts\n+++ b/src/hook.ts\n@@ -1 +1,4 @@\n"
                     "+app.post('/webhook', async (req, res) => {\n+  for (const repo of repos) {\n"
                     "+    await pool.query('SELECT 1 FROM t WHERE repo = $1', [repo]);\n+  }\n")
        self.assertIn("icarus", found)
        for name in ("request and event handlers", "database query", "query, network call or await inside a loop"):
            self.assertIn(name, found["icarus"])
        self.assertIn("caching", spec("+++ b/src/cache.py\n+@functools.lru_cache(maxsize=128)\n")["icarus"])
        self.assertIn("concurrency and resource limits", spec("+++ b/src/db.ts\n+export const pool = new Pool({ max: 4 })\n")["icarus"])
        self.assertIn("module-level collection", spec("+++ b/src/state.ts\n+const seen = new Map<string, number>();\n")["icarus"])
        self.assertIn("blocking call", spec("+++ b/src/server.js\n+const body = fs.readFileSync(path)\n")["icarus"])
        self.assertIn("schema and indexes", spec("+++ b/db/migrations/014_idx.sql\n+CREATE INDEX idx_repo ON runs (repo);\n")["icarus"])
        self.assertIn("frontend rendering and loading", spec("+++ b/web/Cart.tsx\n+const total = useMemo(() => sum(items), [items])\n")["icarus"])
        # Repositories can name their own hot paths.
        self.assertIn("repo: bff", spec("+++ b/src/x.ts\n+bffClient.get(id)\n", {"icarus": {"bff": r"\bbffClient\."}})["icarus"])

    def test_docs_tests_and_plain_logic_need_no_specialist(self):
        spec = review_packet.specialist_signals
        self.assertEqual(spec("+++ b/docs/perf.md\n+Add a cache with a 30 s TTL and a semaphore.\n"), {})
        self.assertEqual(spec("+++ b/tests/test_db.py\n+cursor.execute('SELECT 1 FROM t')\n"), {})
        self.assertEqual(spec("+++ b/src/a.py\n+EFFORT = 'high'\n+total = price * qty\n"), {})
        # A release bump in package.json is not a build change.
        self.assertEqual(spec('+++ b/web/package.json\n+  "version": "0.3.598",\n+  "autoLastDeveloperCommit": "abc",\n'), {})
        self.assertIn("build and package config", spec('+++ b/web/package.json\n+    "zod": "^4.1.0",\n')["palamedes"])
        # A template literal routes nothing.
        self.assertEqual(spec("+++ b/src/url.ts\n+const u = `${base}/${path}`\n"), {})

    def test_complexity_signals_require_hephaestus(self):
        spec = review_packet.specialist_signals
        big = "diff --git a/src/big.py b/src/big.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/big.py\n@@ -0,0 +1,300 @@\n" + \
              "".join(f"+x{i} = {i}\n" for i in range(300))
        names = spec(big)["hephaestus"]
        self.assertTrue(any(n.startswith("large change") for n in names))
        self.assertTrue(any(n.startswith("large new file") for n in names))
        deep = "+++ b/src/deep.py\n" + "".join("+" + " " * 24 + f"y{i} = {i}\n" for i in range(5))
        self.assertTrue(any(n.startswith("deep nesting") for n in spec(deep)["hephaestus"]))
        # Markup nests by design: the same depth in TSX is not deep.
        self.assertEqual(spec("+++ b/web/A.tsx\n" + "".join("+" + " " * 24 + f"<b>{i}</b>\n" for i in range(5))), {})
        wide = "".join(f"+++ b/src/m{i}.py\n+v = {i}\n" for i in range(10))
        self.assertTrue(any(n.startswith("wide change") for n in spec(wide)["hephaestus"]))
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.ts\n+const x = y as any\n")["hephaestus"])

    def test_language_signals_require_palamedes(self):
        spec = review_packet.specialist_signals
        self.assertIn("shell", spec("+++ b/scripts/deploy.sh\n+rm -rf \"$DIR\"\n")["palamedes"])
        self.assertIn("container", spec("+++ b/Dockerfile\n+RUN npm ci\n")["palamedes"])
        self.assertIn("ci and automation yaml", spec("+++ b/.github/workflows/ci.yml\n+  run: make\n")["palamedes"])
        self.assertIn("regular expressions", spec("+++ b/src/a.py\n+PAT = re.compile(r'x+')\n")["palamedes"])
        self.assertIn("dates, time zones and numbers", spec("+++ b/src/a.ts\n+const t = new Date('2026-10-10')\n")["palamedes"])
        mixed = spec("+++ b/src/a.py\n+x = 1\n+++ b/src/b.go\n+var x = 1\n")["palamedes"]
        self.assertTrue(any(n.startswith("several languages") for n in mixed))
        # TypeScript and JavaScript are one family.
        self.assertEqual(spec("+++ b/src/a.ts\n+x = 1\n+++ b/src/b.js\n+y = 2\n"), {})
        self.assertEqual(spec("+++ b/src/a.h\n+int x;\n+++ b/src/a.cpp\n+int y;\n"), {})

    # One added line per documented line signal; each must route its role. Path
    # signals are in PATH_CASES, and every built-in signal name must have a case.
    SIGNAL_CASES = [
        ("icarus", "database query", "src/a.ts", "const r = await db.query('SELECT id FROM runs WHERE repo = $1', [repo])"),
        ("icarus", "network call", "src/a.py", "resp = requests.get(url, timeout=5)"),
        ("icarus", "concurrency and resource limits", "src/a.ts", "const limit = pLimit(4)"),
        ("icarus", "parallel and batch work", "src/a.ts", "await Promise.all(ids.map(load))"),
        ("icarus", "caching", "src/a.py", "@lru_cache(maxsize=1)"),
        ("icarus", "caching", "src/a.py", "@cache"),
        ("icarus", "timeouts, retries and polling", "src/a.ts", "const id = setInterval(tick, 1000)"),
        ("icarus", "blocking call", "src/a.js", "const body = fs.readFileSync(path)"),
        ("icarus", "large data and streaming", "src/a.ts", "const buf = await res.arrayBuffer()"),
        ("icarus", "large data and streaming", "src/a.sql.ts", "const q = `SELECT * FROM t LIMIT 100`"),
        ("icarus", "schema and indexes", "src/a.ts", "await knex.raw('CREATE INDEX idx_repo ON runs (repo)')"),
        ("icarus", "frontend rendering and loading", "web/A.tsx", "const Chart = dynamic(() => import('./Chart'))"),
        ("icarus", "request and event handlers", "src/a.py", '@app.get("/items")'),
        ("icarus", "request and event handlers", "src/a.ts", "app.post('/webhook', handler)"),
        ("icarus", "module-level collection", "src/a.ts", "const seen = new Map<string, number>();"),
        ("icarus", "module-level collection", "src/a.py", "REGISTRY = defaultdict(list)"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "const x = y as any"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "const u = data as any as User;"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "type Props = { cb: any }"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "x as any // legacy"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "export function load(): any {"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "const f: () => any = g"),
        ("palamedes", "error handling and resource cleanup", "src/a.ts", "using file = openFile(p);"),
        ("palamedes", "error handling and resource cleanup", "src/a.ts", "using res: Disposable = getRes();"),
        ("palamedes", "error handling and resource cleanup", "src/a.cs", "using (StreamReader r = new StreamReader(p)) {"),
        ("palamedes", "error handling and resource cleanup", "src/a.cs", "using FileStream f = File.Open(p);"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.ts", "type Pair = [any, string]"),
        ("icarus", "network call", "app/a.rb", "res = Net::HTTP.get(uri)"),
        ("palamedes", "error handling and resource cleanup", "src/a.cs", "using (var conn = new SqlConnection(cs)) {"),
        ("hephaestus", "escape hatches and dynamic code", "src/a.py", "    global counter"),
        ("palamedes", "shell", "bin/run", "#!/usr/bin/env bash"),
        ("palamedes", "regular expressions", "src/a.py", "PAT = re.compile(r'x+')"),
        ("palamedes", "dates, time zones and numbers", "src/a.ts", "const t = new Date('2026-10-10')"),
        ("palamedes", "encoding and unicode", "src/a.ts", "const s = name.normalize('NFC')"),
        ("palamedes", "encoding and unicode", "src/a.ts", "const k = name.normalize('NFKC')"),
        ("palamedes", "error handling and resource cleanup", "src/a.go", "\tdefer f.Close()"),
        ("palamedes", "error handling and resource cleanup", "src/a.cs", "using var stream = File.OpenRead(p);"),
        ("palamedes", "async semantics", "src/a.ts", "process.nextTick(flush)"),
        ("palamedes", "type system edges", "src/a.rs", "unsafe { ptr.read() }"),
        ("palamedes", "type system edges", "src/a.go", "var v interface{}"),
        ("palamedes", "module system", "src/a.mjs", "const here = import.meta.url"),
        ("palamedes", "error handling and resource cleanup", "src/a.ts", "process.on('SIGTERM', shutdown)"),
    ]
    PATH_CASES = [
        ("icarus", "schema and indexes", "db/migrations/014_idx.sql"),
        ("icarus", "runtime and build limits", "wrangler.toml"),
        ("palamedes", "shell", "scripts/deploy.sh"),
        ("palamedes", "sql", "prisma/schema.prisma"),
        ("palamedes", "container", "Dockerfile"),
        ("palamedes", "ci and automation yaml", ".github/workflows/ci.yml"),
        ("palamedes", "infrastructure code", "infra/main.tf"),
        ("palamedes", "styles", "web/app.scss"),
    ]

    def test_every_documented_path_signal_routes_its_role(self):
        for role, name, path in self.PATH_CASES:
            with self.subTest(signal=name, path=path):
                self.assertIn(name, review_packet.specialist_signals(f"+++ b/{path}\n+x\n").get(role, {}))
        covered = {name for _, name, *_ in self.SIGNAL_CASES + self.PATH_CASES}
        builtin = set(review_packet.PERFORMANCE_SIGNALS) | set(review_packet.LANGUAGE_LINES) | set(review_packet.LANGUAGE_PATHS)
        self.assertEqual(builtin - covered, set())

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
        ("src/a.ts", "const note = 'pick any of these'"),
        ("src/a.cs", "using Json = System.Text.Json;"),
        ("src/a.ts", "const hint = 'Log in as any user'"),
        ("web/A.tsx", '<input placeholder="Brand (any)" />'),
        ("web/A.tsx", "<p>Pick a size, any size works</p>"),
        ("src/a.ts", "const label = { title: 'Size: any' }"),
        ("src/a.ts", "const q = sql`select * from a join b using (id)`"),
        ("src/a.py", "# by using (for example) the store"),
        ("src/a.ts", "const hint = 'Size: any, colour: any'"),
        ("src/a.ts", "const n = 1 // returns: any"),
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
        name = "query, network call or await inside a loop"
        self.assertIn(name, spec(hunk("for (const r of repos) {", "  await save(r)", "}")).get("icarus", {}))
        self.assertIn(name, spec(hunk("ids.forEach(async (id) => {", "  await fetch(url + id)", "})")).get("icarus", {}))
        php = "+++ b/src/a.php\n@@ -0,0 +1,3 @@\n+foreach ($ids as $id) {\n+    $rows[] = $pdo->query($sql);\n+}\n"
        self.assertIn(name, spec(php).get("icarus", {}))
        rb = "+++ b/app/a.rb\n@@ -0,0 +1,3 @@\n+ids.each do |id|\n+  Net::HTTP.get(uri)\n+end\n"
        self.assertIn(name, spec(rb).get("icarus", {}))
        self.assertIn(name, spec(rb.replace("ids.each do", "User.find_each do")).get("icarus", {}))
        self.assertNotIn(name, spec(hunk("if (course.teacher) {", "  const u = await load(course.teacher.id)", "}")).get("icarus", {}))
        self.assertNotIn(name, spec(hunk("if (checkout.step === 'payment') {", "  await createPaymentIntent(order)", "}")).get("icarus", {}))
        self.assertNotIn(name, spec(hunk("if (quota.reached) {", "  await notify(user)", "}")).get("icarus", {}))
        self.assertNotIn(name, spec(hunk("  until: {", "    date: await nextSlot(),", "  },")).get("icarus", {}))
        long_body = ["for (const item of items) {"] + [f"  const v{i} = item.f{i};" for i in range(60)] + ["  await processItem(item)", "}"]
        self.assertIn(name, spec(hunk(*long_body)).get("icarus", {}))
        rb_until = "+++ b/app/a.rb\n@@ -0,0 +1,3 @@\n+until (row = cursor.fetch).nil?\n+  db.execute(sql)\n+end\n"
        self.assertIn(name, spec(rb_until).get("icarus", {}))
        self.assertIn(name, spec(hunk("const t = await items.reduce(async (acc, x) => {", "  return acc + await load(x)", "}, 0)")).get("icarus", {}))
        for head in ("await Promise.all(rows.map((row: Row) => {", "$.each(items, function () {", "_.each(xs, (x) => {",
                     "rows.map(function (r) {"):
            with self.subTest(head=head):
                self.assertIn(name, spec(hunk(head, "  return db.query(sql)", "})")).get("icarus", {}))
        self.assertIn(name, spec("+++ b/app/a.rb\n@@ -0,0 +1,3 @@\n+3.times do |i|\n+  db.execute(sql)\n+end\n").get("icarus", {}))
        self.assertNotIn(name, spec(hunk("return Promise.reject({", "  err: await describe(e),", "})")).get("icarus", {}))
        # After the loop has closed, or after a one-line .map, an await is sequential code.
        self.assertNotIn(name, spec(hunk("const ids = rows.map(r => r.id)", "await save(ids)")).get("icarus", {}))
        self.assertNotIn(name, spec(hunk("for (const x of xs) { total += x }", "const r = await load()")).get("icarus", {}))

    def test_nesting_uses_the_files_own_indent_unit(self):
        spec = review_packet.specialist_signals
        lines = lambda path, pad: f"+++ b/{path}\n" + "".join(f"+{pad}y{i} = {i}\n" for i in range(5))
        deep = lambda found: any(n.startswith("deep nesting") for n in found.get("hephaestus", {}))
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
        mixed = spec("+++ b/src/a.py\n+x = 1\n+++ b/src/b.go\n+var x = 1\n")["palamedes"]
        self.assertTrue(any(n.startswith("several languages") for n in mixed))
        self.assertEqual(spec("+++ b/src/a.ts\n+x = 1\n+++ b/src/b.js\n+y = 2\n"), {})

    def test_diff_parsing_is_not_fooled_by_content_or_paths(self):
        spec, tier = review_packet.specialist_signals, review_packet.security_tier
        # A content line that starts with '++ ' is not a new file header.
        sneaky = ("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -0,0 +1,2 @@\n"
                  "+++ b/docs/x.md\n+resp = requests.get(url)\n")
        self.assertIn("network call", spec(sneaky)["icarus"])
        self.assertEqual(tier(sneaky.replace("requests.get(url)", "token = jwt.sign(user)"))[0], "athena")
        # Names with spaces (git adds a tab) and quoted non-ASCII names keep their path.
        self.assertEqual(spec('+++ b/docs/Release notes.md\t\n+Add a cache and a semaphore.\n'), {})
        quoted = spec('+++ "b/src/caf\\303\\251.py"\n+resp = requests.get(url)\n')
        self.assertEqual(quoted["icarus"]["network call"], ["src/café.py"])

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
        self.assertEqual(review_packet.security_tier("+++ b/src/config.ts\n" + line)[0], "athena")

    def test_deleted_renamed_and_binary_files(self):
        spec, tier = review_packet.specialist_signals, review_packet.security_tier
        deleted = ("diff --git a/db/migrations/012.sql b/db/migrations/012.sql\ndeleted file mode 100644\n"
                   "--- a/db/migrations/012.sql\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-CREATE INDEX i ON t (c);\n")
        self.assertEqual(spec(deleted), {})
        renamed = ("diff --git a/api/x.ts b/auth/session.ts\nsimilarity index 100%\n"
                   "rename from api/x.ts\nrename to auth/session.ts\n")
        self.assertEqual(tier(renamed)[0], "athena")
        binary = "diff --git a/Dockerfile b/Dockerfile\nnew file mode 100644\nBinary files /dev/null and b/Dockerfile differ\n"
        self.assertIn("container", spec(binary)["palamedes"])
        spaced = "diff --git a/auth b/key.png b/auth b/key.png\nBinary files a/auth b/key.png and b/auth b/key.png differ\n"
        self.assertIn("auth b/key.png", tier(spaced)[1].get("authentication", []))
        quoted = ('diff --git a/x.ts "b/auth/s\\303\\251ssion.ts"\nsimilarity index 100%\n'
                  'rename from x.ts\nrename to "auth/s\\303\\251ssion.ts"\n')
        self.assertEqual(tier(quoted)[1]["authentication"], ["auth/séssion.ts"])
        # Pasted diffs without 'diff --git': a new file does not make the next one new.
        pasted = "--- /dev/null\n+++ b/a.py\n+x = 1\n--- a/b.py\n+++ b/b.py\n" + "".join(f"+y{i} = {i}\n" for i in range(300))
        self.assertFalse(any(n.startswith("large new file") for n in spec(pasted).get("hephaestus", {})))
        after_delete = "--- a/old.sh\n+++ /dev/null\n-x\n--- a/Dockerfile\n+++ b/Dockerfile\n+RUN true\n"
        self.assertIn("container", spec(after_delete)["palamedes"])

    def test_container_ci_and_prose_lines_route_no_ruby_or_oscar(self):
        spec = review_packet.specialist_signals
        for path, line in (("Dockerfile", "RUN apk add --no-cache curl"), ("Dockerfile", "HEALTHCHECK --timeout=3s --retries=3 CMD x"),
                           ("docker-compose.yml", "      retries: 5"), (".github/workflows/ci.yml", "      cache: npm"),
                           (".github/workflows/ci.yml", "    timeout-minutes: 10")):
            with self.subTest(line=line):
                self.assertNotIn("icarus", spec(f"+++ b/{path}\n+{line}\n"))
        for path, line in (("scripts/entry.sh", 'exec "$@"'), ("src/a.ts", "// keep the global flag off"),
                           ("src/a.py", "flags = {n: any(p.match(n) for p in pats) for n in names}"),
                           ("src/a.ts", 'throw new Error("Invalid input: any of a, b required")'),
                           ("db/migrations/1.sql", "-- FIXME: split later"), ("web/a.scss", "/* HACK */")):
            with self.subTest(line=line):
                self.assertNotIn("hephaestus", spec(f"+++ b/{path}\n+{line}\n"))
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.ts\n+function f(x: any) {}\n")["hephaestus"])
        self.assertIn("escape hatches and dynamic code", spec("+++ b/src/a.py\n+    global counter\n")["hephaestus"])

    def test_package_json_keys_and_requirements(self):
        spec = review_packet.specialist_signals
        self.assertIn("module system", spec('+++ b/package.json\n+  "exports": {\n')["palamedes"])
        self.assertEqual(spec('+++ b/locales/en.json\n+  "main": "Main menu",\n'), {})
        self.assertIn("build and package config", spec("+++ b/requirements.txt\n+httpx==0.28.1\n")["palamedes"])
        for path in ("docs/requirements.txt", "tests/fixtures/app/package.json", "src/generated/graphql.ts",
                     "engines/billing/spec/support/api.rb", "src/i18n/de.json"):
            with self.subTest(path=path):
                self.assertEqual(spec(f"+++ b/{path}\n+  \"zod\": \"^4\", x = await fetch(url)\n"), {})
        self.assertIn("dates, time zones and numbers", spec("+++ b/src/i18n/format.ts\n+const f = new Intl.NumberFormat(l)\n")["palamedes"])
        # Output dirs are skipped only at a repo or package root.
        self.assertEqual(spec("+++ b/packages/web/dist/app.js\n+fetch(url)\n"), {})
        self.assertIn("icarus", spec("+++ b/tools/build/bundle.ts\n+await fetch(url)\n"))

    def test_odd_indents_and_hunks_do_not_skew_nesting_or_loops(self):
        spec = review_packet.specialist_signals
        jsdoc = "+++ b/src/a.ts\n+    /**\n+     * @param id\n+     */\n" + "".join(f"+            y{i}();\n" for i in range(5))
        self.assertFalse(any(n.startswith("deep nesting") for n in spec(jsdoc).get("hephaestus", {})))
        two_hunks = ("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1,2 +1,2 @@\n"
                     "     for row in rows:\n         total += row.n\n@@ -90,1 +90,2 @@\n         x = 1\n+        data = await self.load()\n")
        self.assertNotIn("query, network call or await inside a loop", spec(two_hunks).get("icarus", {}))
        async_for = "+++ b/src/a.py\n@@ -0,0 +1,2 @@\n+    async for row in rows:\n+        await send(row)\n"
        self.assertIn("query, network call or await inside a loop", spec(async_for)["icarus"])
        crlf = "+++ b/src/a.py\n+REGISTRY = defaultdict(list)\r\n"
        self.assertIn("module-level collection", spec(crlf)["icarus"])

    def test_binary_attribute_and_key_signals(self):
        binary = lambda p: f"diff --git a/{p} b/{p}\nindex 1..2 100644\nBinary files a/{p} and b/{p} differ\n"
        for path in ("src/x.ts", "web/index.html", "Dockerfile", "deploy/app.yaml", "e2e/global-setup.ts", "vendor/analytics.js",
                     "conftest.py", "pkg/a_test.go", "dist/index.js", "package-lock.json", "public/app.min.js", "ios/Podfile.lock", "bun.lockb"):
            with self.subTest(path=path):
                self.assertIn("hidden source content", review_packet.security_tier(binary(path))[1])
        for path in ("web/logo.png", "fonts/a.woff2", "public/app.js.map", "src/generated/api.ts", "docs/spec.xlsx",
                     "tests/fixtures/model.onnx", "data/sample.parquet"):
            with self.subTest(path=path):
                self.assertNotIn("hidden source content", review_packet.security_tier(binary(path))[1])
        # Only attributes that can hide or collapse source count (HARMLESS_ATTRIBUTES, asset suffixes and comments do not).
        for line in ("* text=auto eol=lf", "CHANGELOG.md merge=union", "*.psd filter=lfs diff=lfs merge=lfs -text",
                     "*.png binary", "# binary files", "yarn.lock linguist-generated", "*.min.js linguist-generated",
                     "src/app.js.map -diff", "*.lock linguist-generated"):
            with self.subTest(line=line):
                self.assertEqual(review_packet.security_tier(f"+++ b/.gitattributes\n+{line}\n")[0], "artemis")
        for path in ("deploy/id_rsa", "keys/id_ed25519_github", "ios/AuthKey_ABC.p8", "tests/fixtures/dev.pem", ".ssh/id_dsa"):
            with self.subTest(path=path):
                self.assertIn("key or certificate file", review_packet.security_tier(f"+++ b/{path}\n+x\n")[1])
        for path in ("keys/id_rsa.pub", "keys/id_rsa_work.pub", "src/auth/id_rsa_parser.py", "docs/guide.asc"):
            with self.subTest(path=path):
                self.assertNotIn("key or certificate file", review_packet.security_tier(f"+++ b/{path}\n+x\n")[1])
        for path in (".env", ".env.production", "app/.npmrc", ".netrc", "deploy/svc.keytab", "gcp/service-account-prod.json",
                     ".aws/credentials", ".git-credentials", "infra/terraform.tfstate", "prod.tfvars", ".htpasswd", ".envrc",
                     "ops/kubeconfig-prod", ".kube/config", "services/messages/service-account.json", "env/prod.tfvars.json",
                     "services/messages/.env.production", "ops/kubeconfig.yaml", "services/messages/deploy/credentials.json",
                     "services/messages/gcp/credentials.json", "messages/aws-prod/credentials.json", "lang/credentials.json"):
            with self.subTest(path=path):
                self.assertIn("credential file", review_packet.security_tier(f"+++ b/{path}\n+x\n")[1])
        for path in (".env.example", ".env.sample", "src/env.ts", ".env.local.example", ".env.production.template",
                     "locales/en/credentials.json", "prod.example.tfvars", "prod.sample.tfvars", "docs/kubeconfig.md",
                     "pkg/kubeconfig.go", "pkg/kubeconfig_test.go", "src/messages/.env.example", "locales/de-DE/credentials.json", "locales/es-419/credentials.json", "i18n/credentials.json",
                     "deploy/kubeconfig-example.yaml", "prod_example.tfvars", "examples/example.tfvars"):
            with self.subTest(path=path):
                self.assertNotIn("credential file", review_packet.security_tier(f"+++ b/{path}\n+x\n")[1])
        self.assertIn("key or certificate file", review_packet.security_tier(
            "diff --git a/certs/client.p12 b/certs/client.p12\nnew file mode 100644\nBinary files /dev/null and b/certs/client.p12 differ\n")[1])
        for line in ("*.ts -diff", "src/payments/** linguist-generated=true", "src/payments/*.ts opaque", "[attr]opaque -diff",
                     "src/payments/** filter=lfs diff=lfs merge=lfs -text", "src/checkout.a* -diff", "src/core.a/** -diff",
                     "package-lock.json -diff", "yarn.lock binary", "*.min.js binary", "*.lock -diff",
                     "*[.generated.]*.ts -diff", "bun.lockb -diff"):
            with self.subTest(line=line):
                self.assertEqual(review_packet.security_tier(f"+++ b/.gitattributes\n+{line}\n")[0], "athena")
        self.assertEqual(review_packet.security_tier("+++ b/.gitattributes\n-*.ts -diff\n")[0], "artemis")

    @unittest.skipIf(tuple(int(x) for x in re.findall(r"\d+", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)[:2]) < (2, 40),
                     "--attr-source needs git 2.40+")
    def test_attributes_and_binary_markers_cannot_hide_source(self):
        write(os.path.join(self.repo, ".gitattributes"), "*.py -diff\n")
        write(os.path.join(self.repo, "src", "a.py"), "token = jwt.decode(t, verify=False)\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "hide")
        out = os.path.join(self.tmp.name, "attr")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude", "--out", out])
        self.assertIn("+token = jwt.decode(t, verify=False)", open(os.path.join(out, "diff.patch")).read())
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertEqual(manifest["security"]["tier"], "athena")
        self.assertIn("diff attributes", manifest["security"]["signals"])
        # A fix check reads attributes from the merge base too.
        head = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        write(os.path.join(self.repo, "src", "a.py"), "token = jwt.decode(t, verify=False)\nresp = requests.get(url)\n")
        git(self.repo, "commit", "-qam", "fix")
        out2 = os.path.join(self.tmp.name, "attr2")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude",
                            "--previous-head", head, "--out", out2])
        self.assertIn("+resp = requests.get(url)", open(os.path.join(out2, "fix-diff.patch")).read())

    def test_lone_carriage_return_does_not_shift_hunks(self):
        path = os.path.join(self.repo, "src", "cr.py")
        with open(path, "wb") as fh:
            fh.write(b'q = "\r"\ntok = 1\n++ b/docs/x.md\nresp = requests.get(url)\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "cr")
        out = os.path.join(self.tmp.name, "cr")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude", "--out", out])
        manifest = json.load(open(os.path.join(out, "manifest.json")))
        self.assertIn("network call", manifest["specialists"]["icarus"]["signals"])

    def test_repository_signals_match_paths_too(self):
        extra = review_packet.compile_extra_signals(["icarus:hot path=^src/hot/"], review_packet.SPECIALISTS)
        found = review_packet.specialist_signals("+++ b/src/hot/a.py\n+x = 1\n", extra)
        self.assertEqual(found["icarus"]["repo: hot path"], ["src/hot/a.py"])
        deleted = "diff --git a/src/hot/a.py b/src/hot/a.py\ndeleted file mode 100644\n--- a/src/hot/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x = 1\n"
        self.assertEqual(review_packet.specialist_signals(deleted, extra), {})

    def test_repository_signals_add_and_never_replace(self):
        extra = review_packet.compile_extra_signals(["icarus:database query=(?!)"], review_packet.SPECIALISTS)
        found = review_packet.specialist_signals("+++ b/src/a.ts\n+await db.query('x')\n", extra)
        self.assertIn("database query", found["icarus"])
        self.assertEqual(review_packet.security_tier("+++ b/api/s.ts\n+const jwt = sign(user)\n",
                                                     {"authentication": "(?!)"})[0], "athena")
        for bad in ("icarus:x=(", "maya:x=y", "icarus:=y", "icarus:x=a{99999999999}"):
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
        self.assertIn("icarus", manifest["roles"])
        self.assertTrue(manifest["specialists"]["icarus"]["added"])
        self.assertIn("network call", manifest["specialists"]["icarus"]["signals"])
        self.assertTrue(os.path.isfile(os.path.join(out, "prompts", "icarus.md")))
        self.assertIn("Icarus (performance) (added to the plan): ", open(os.path.join(out, "self-check.md")).read())
        # A fix check routes on the changes since the reviewed head only.
        head = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        write(os.path.join(self.repo, "src", "a.py"), "EFFORT = 'xhigh'\n")
        git(self.repo, "commit", "-qam", "fix")
        out2 = os.path.join(self.tmp.name, "spec2")
        review_packet.main(["--repo", self.repo, "--base", "main", "--roles", "maya", "--runtime", "claude",
                            "--previous-head", head, "--out", out2])
        manifest2 = json.load(open(os.path.join(out2, "manifest.json")))
        self.assertEqual(list(manifest2["roles"]), ["pandora"])
        self.assertEqual(manifest2["specialists"], {})

    def test_specialist_signal_flag_is_validated(self):
        with self.assertRaises(SystemExit):
            self.run_packet("--specialist-signal", "maya:x=y")
        code, out = self.run_packet("--specialist-signal", "hephaestus:effort constant=EFFORT")
        self.assertEqual(code, 0)
        self.assertIn("repo: effort constant", json.load(open(os.path.join(out, "manifest.json")))["specialists"]["hephaestus"]["signals"])

    def test_legacy_specialist_signals_use_canonical_routes_without_duplicates(self):
        for requested in ("ruby,icarus", "icarus"):
            with self.subTest(requested=requested):
                code, out = self.run_packet(
                    "--roles", requested,
                    "--specialist-signal", "ruby:legacy performance=EFFORT",
                    "--specialist-signal", "icarus:canonical performance=EFFORT",
                    "--specialist-signal", "oscar:legacy quality=EFFORT",
                    "--specialist-signal", "iris:legacy language=EFFORT")
                self.assertEqual(code, 0)
                manifest = json.load(open(os.path.join(out, "manifest.json")))
                self.assertEqual(set(manifest["roles"]), {"icarus", "hephaestus", "palamedes"})
                self.assertFalse(manifest["specialists"]["icarus"]["added"])
                self.assertEqual(set(manifest["specialists"]["icarus"]["signals"]),
                                 {"repo: legacy performance", "repo: canonical performance"})
                self.assertEqual(manifest["roles"]["icarus"]["definition"], "sonnet-reviewer-medium")
                for role in ("icarus", "hephaestus", "palamedes"):
                    self.assertTrue(os.path.isfile(os.path.join(out, "prompts", role + ".md")))
                for alias in ("ruby", "oscar", "iris"):
                    self.assertFalse(os.path.exists(os.path.join(out, "prompts", alias + ".md")))

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
        a = self.result("themis", {"role": "guidelines", "head": "abc", "status": "complete", "findings": [
            {"file": "/repo/AGENTS.md", "line": 10, "severity": "important", "impact": "stale sentence"}]})
        b = self.result("mnemosyne", {"role": "comments", "head": "abc", "status": "complete", "findings": [
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
        a = self.result("pandora", {"role": "bugs", "head": "old", "status": "complete", "findings": []})
        b = self.result("proteus", {"role": "types", "head": "abc", "status": "incomplete", "findings": []})
        self.assertEqual(merge_findings.main([a, b, "--head", "abc", "--out", self.tmp.name]), 1)
        summary = json.load(open(os.path.join(self.tmp.name, "findings.json")))["summary"]
        self.assertFalse(summary["complete"])
        self.assertEqual(len(summary["problems"]), 2)

    def test_clean_complete_review_passes(self):
        a = self.result("pandora", {"role": "bugs", "head": "abc", "status": "complete", "findings": []})
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
