"""Behavioural regressions for the six findings in the repository audit."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode

from tests import test_dashboard_reference_versions as reference_fixtures
from tests import test_dashboard_staging_editor as editor_fixtures
from tests.test_dashboard_server import make_creator_project, run_node
from tests.test_drama_diagnostics import check


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_regression_views", ROOT / "skills/short-drama/scripts/creator_views.py"
)
assert SPEC and SPEC.loader
views = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(views)


class CoverageAndTimingTests(unittest.TestCase):
    def report(self, paragraphs, shots, rate=None):
        errors, notes = [], []
        check._check_beat_coverage(
            "## EP001-SC001 内 · 办公室 · 日\n\n" + "\n\n".join(paragraphs),
            {f"SHOT-EP001-{i:03d}": body for i, body in enumerate(shots, 1)},
            {}, rate, errors, notes,
        )
        return errors, notes

    @staticmethod
    def shot(quote, *, scene="EP001-SC001", seconds="4s"):
        return f"- 来源：{scene}「{quote}」\n- 时长：{seconds}\n"

    def test_same_quote_from_another_scene_cannot_carry_the_beat(self):
        line = "许棠把铜钥匙丢进雨水井。"
        errors, _ = self.report([line], [self.shot(line, scene="EP001-SC002")])
        self.assertEqual(len(errors), 1)
        self.assertIn("EP001-SC001", errors[0])

    def test_shared_prefix_and_partial_quote_do_not_prove_opposite_action(self):
        for other in ("许棠把文件仔细叠好放进保险柜。", "许棠把文件"):
            with self.subTest(other=other):
                errors, _ = self.report(
                    ["许棠把文件撕成碎片扔进垃圾桶。"], [self.shot(other)]
                )
                self.assertEqual(len(errors), 1)

    def test_negation_is_not_lost_by_matching_inside_a_larger_surface(self):
        errors, _ = self.report(
            ["打开大门。"], ["- 来源：EP001-SC001\n- 唯一动作：没有打开大门。\n"]
        )
        self.assertEqual(len(errors), 1)

    def test_explicit_full_quotes_ignore_punctuation_and_whitespace(self):
        errors, _ = self.report(
            ["许棠把文件放好。"], [self.shot("许棠 把文件放好")]
        )
        self.assertEqual(errors, [])

    def test_dialogue_can_span_two_shots_without_first_shot_overcharge(self):
        line = "今天下午我们一起回去取那个重要文件。"
        errors, _ = self.report(["许棠：" + line], [self.shot(line), self.shot(line)], rate=3)
        self.assertEqual(errors, [])

    def test_multiple_lines_cannot_spend_the_same_shot_time_twice(self):
        first, second = "甲乙丙丁戊己", "庚辛壬癸子丑"
        shot = f"- 来源：EP001-SC001「{first}」「{second}」\n- 时长：3s\n"
        errors, _ = self.report(["许棠：" + first, "赵经理：" + second], [shot], rate=2)
        self.assertEqual(len(errors), 1)
        self.assertIn("共享镜长", errors[0])

    def test_overlapping_claims_use_a_feasible_shared_budget(self):
        first, second = "甲乙丙丁戊己", "庚辛壬癸子丑"
        shots = [
            f"- 来源：EP001-SC001「{first}」「{second}」\n- 时长：3s\n",
            self.shot(first, seconds="3s"),
        ]
        errors, _ = self.report(["许棠：" + first, "赵经理：" + second], shots, rate=2)
        self.assertEqual(errors, [])

    def test_subset_overload_is_detected_even_with_spare_unrelated_capacity(self):
        lines = ["甲乙丙丁戊己", "庚辛壬癸子丑", "寅卯辰巳午未"]
        shots = [
            f"- 来源：EP001-SC001「{lines[0]}」「{lines[1]}」\n- 时长：3s\n",
            self.shot(lines[2], seconds="20s"),
        ]
        errors, _ = self.report(["许棠：" + line for line in lines], shots, rate=2)
        self.assertEqual(len(errors), 1)

    def test_an_unknown_duration_does_not_become_zero_available_time(self):
        line = "今天下午我们一起回去取那个重要文件。"
        errors, notes = self.report(
            ["许棠：" + line], [self.shot(line, seconds="未知"), self.shot(line, seconds="1s")], rate=1
        )
        self.assertEqual(errors, [])
        self.assertTrue(any("尚未确定" in note for note in notes))

    def test_dashboard_consumes_the_same_errors_notes_and_project_rate(self):
        line = "今天下午我们一起回去取那个重要文件。"
        docs = {
            "剧本.md": "## EP001-SC001 内 · 办公室 · 日\n\n许棠：" + line,
            "分镜.md": "## SHOT-EP001-001 · 交谈\n" + self.shot(line, seconds="1s"),
            "视觉设定.md": "## 人物 · 许棠\n- 本集造型：灰色外套\n",
        }
        notes = []
        expected = check.validate_documents(docs, None, partial=True, diagnostics=notes, pacing_rate=1)
        parsed = views.read_episode("EP001", docs, None, pacing_rate=1)
        self.assertEqual(parsed["checks"], {"errors": expected, "diagnostics": notes})
        self.assertTrue(any("对白约需" in error for error in expected))
        self.assertTrue(any("没有识别锚点" in note for note in notes))

    def test_safely_supplied_language_runs_the_same_language_check(self):
        docs = {"视觉设定.md": "## 人物 · 许棠\n- 识别锚点：旧外套。\n"}
        english = views.read_episode("EP001", docs, None, prompt_language="en")
        chinese = views.read_episode("EP001", docs, None, prompt_language="zh-CN")
        self.assertTrue(any("缺少画面代称" in error for error in english["checks"]["errors"]))
        self.assertFalse(any("缺少画面代称" in error for error in chinese["checks"]["errors"]))

    def test_safe_reference_callback_is_never_given_an_escaping_path(self):
        calls, errors = [], []
        check._check_project_file("../secret.png", "SHOT", None, errors, file_exists=lambda p: calls.append(p))
        self.assertEqual(calls, [])
        self.assertTrue(errors)
        errors.clear()
        check._check_project_file("输入/missing.png", "SHOT", None, errors, file_exists=lambda p: calls.append(p))
        self.assertEqual(calls, ["输入/missing.png"])
        self.assertTrue(errors)

    def test_invalid_project_rates_are_unknown_instead_of_crashing(self):
        for rate in (True, 0, -1, float("nan"), float("inf"), 10**1000, "3"):
            with self.subTest(rate=type(rate).__name__):
                self.assertIsNone(check.pacing_rate_from_manifest({"format": {"pacing": {"spoken_characters_per_second": rate}}}))


class ReferenceDependencyTests(unittest.TestCase):
    @contextmanager
    def project(self):
        helper = reference_fixtures.DashboardReferenceVersionTests()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            make_creator_project(project)
            paths = helper.setup_references(project)
            store = helper.store(workspace)
            try:
                projects, _ = store.discover()
                yield project, paths, store, projects[0]["id"]
            finally:
                store.close()

    @staticmethod
    def views(store, project_id):
        return {
            view["id"]: view
            for group in store.episode(project_id, "EP001")["references"]["groups"]
            for view in group["views"]
        }

    @staticmethod
    def edit_manifest(project, edit):
        path = project / "剧集/EP001/制作成果/references/index.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        edit(manifest)
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def test_parent_tamper_and_deletion_expire_the_derived_view(self):
        for deleted in (False, True):
            with self.subTest(deleted=deleted), self.project() as (_, paths, store, project_id):
                if deleted:
                    paths["anchor"].unlink()
                else:
                    paths["anchor"].write_bytes(b"changed")
                views_ = self.views(store, project_id)
                self.assertEqual(views_["front-full"]["status"], "expired")
                self.assertEqual(views_["face-front"]["status"], "expired")
                self.assertIn("父图已失效", views_["face-front"]["reasons"])

    def test_a_missing_source_is_never_reported_current(self):
        with self.project() as (_, paths, store, project_id):
            paths["source"].unlink()
            self.assertTrue(all(v["status"] == "expired" for v in self.views(store, project_id).values()))

    def test_source_resolution_uses_its_exact_project_path(self):
        with self.project() as (project, _, store, project_id):
            def edit(manifest):
                manifest["groups"]["HERO"]["views"]["front-full"]["current"]["source"] = "剧集/EP999/图片提示词.md"
            self.edit_manifest(project, edit)
            self.assertEqual(self.views(store, project_id)["front-full"]["status"], "expired")

    def test_unsafe_manifest_source_cannot_read_outside_the_project(self):
        with self.project() as (project, paths, store, project_id):
            outside = project.parent / "图片提示词.md"
            outside.write_bytes(paths["source"].read_bytes())
            def edit(manifest):
                manifest["groups"]["HERO"]["views"]["front-full"]["current"]["source"] = "../图片提示词.md"
            self.edit_manifest(project, edit)
            self.assertEqual(self.views(store, project_id)["front-full"]["status"], "expired")

    def test_parent_path_is_checked_even_when_hashes_are_equal(self):
        with self.project() as (project, _, store, project_id):
            def edit(manifest):
                manifest["groups"]["HERO"]["views"]["face-front"]["current"]["depends_on_output"]["path"] = "production/reference/other.png"
            self.edit_manifest(project, edit)
            self.assertIn("父图已更新", self.views(store, project_id)["face-front"]["reasons"])

    def test_transitive_expiry_is_independent_of_view_sorting(self):
        with self.project() as (project, paths, store, project_id):
            def edit(manifest):
                raw = manifest["groups"]["HERO"]["views"]
                grandchild = copy.deepcopy(raw["face-front"])
                current = grandchild["current"]
                current["job_id"] = "REF-DETAIL"
                current["depends_on_job_id"] = "REF-HERO-FACE"
                current["depends_on_output"] = {"path": current["output"], "sha256": current["sha256"]}
                manifest["groups"]["DETAIL"] = {"views": {"aaa-detail": grandchild}}
            self.edit_manifest(project, edit)
            self.assertTrue(all(v["status"] == "current" for v in self.views(store, project_id).values()))
            paths["anchor"].write_bytes(b"changed")
            self.assertTrue(all(v["status"] == "expired" for v in self.views(store, project_id).values()))

    def test_cycles_expire_without_recursing_or_hanging(self):
        with self.project() as (project, _, store, project_id):
            def edit(manifest):
                raw = manifest["groups"]["HERO"]["views"]
                anchor, face = raw["front-full"]["current"], raw["face-front"]["current"]
                anchor["depends_on_job_id"] = face["job_id"]
                anchor["depends_on_output"] = {"path": face["output"], "sha256": face["sha256"]}
            self.edit_manifest(project, edit)
            views_ = self.views(store, project_id)
            self.assertTrue(all("父图依赖成环" in v["reasons"] for v in views_.values()))


class StagingClientTests(unittest.TestCase):
    def client(self, body):
        app = str(ROOT / "skills/short-drama/assets/dashboard/app.js")
        script = """
const fs = require('fs'); const vm = require('vm');
const context = vm.createContext({console, URLSearchParams, location:{hash:'#/EP001/board'}, CSS:{escape:x=>x}});
vm.runInContext(fs.readFileSync(APP,'utf8'), context);
vm.runInContext(`(async () => {
  const scene='EP001-SC001', version='a'.repeat(64), nextVersion='b'.repeat(64);
  const block={scene, positions:[{name:'许棠',present:true,item:'ITEM-DESK',side:'west',along:0.4,posture:'stand',facing:'east'}],extras:0,extrasWhere:''};
  const E={id:'EP001',documentVersions:{'分镜.md':version},docs:{'分镜.md':'剧集/EP001/分镜.md'},board:{blocking:[block]}};
  S.project='creator'; S.episodes.set('EP001',E);
  const draft=stageDraft(block,E); draft.dirty=true;
  const messages=[]; const requests=[];
  render=async()=>{}; refreshProject=async()=>{}; toast=(text)=>messages.push(text);
  BODY
})().catch(error=>{console.log(JSON.stringify({failure:error.stack}));})`, context);
""".replace("APP", json.dumps(app)).replace("BODY", body)
        result = json.loads(run_node(script).stdout)
        self.assertNotIn("failure", result, result)
        return result

    def test_save_submits_the_captured_version_and_preserves_a_conflicting_draft(self):
        result = self.client("""
api=async(path,options)=>{requests.push({path,payload:JSON.parse(options.body)}); const error=new Error('file changed since it was opened');error.status=409;throw error;};
await saveStaging(scene);
console.log(JSON.stringify({requests,dirty:draft.dirty,conflict:draft.conflict,retained:S.stagingDrafts.get(scene)===draft,version:draft.version}));
""")
        self.assertEqual(len(result["requests"]), 1)
        self.assertTrue(result["requests"][0]["path"].startswith("/api/staging?"))
        self.assertEqual(result["requests"][0]["payload"]["expectedVersion"], "a" * 64)
        self.assertTrue(result["dirty"] and result["conflict"] and result["retained"])

    def test_edits_during_save_are_retained_against_the_returned_version(self):
        result = self.client("""
let release; api=async(path,options)=>{requests.push(JSON.parse(options.body));return await new Promise(resolve=>{release=resolve;});};
const pending=saveStaging(scene); await saveStaging(scene);
draft.positions[0].along=0.8;markStageDirty(scene);
release({saved:true,version:nextVersion});await pending;
console.log(JSON.stringify({requests,retained:S.stagingDrafts.get(scene)===draft,version:draft.version,dirty:draft.dirty,saving:draft.saving,along:draft.positions[0].along}));
""")
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["positions"][0]["along"], 0.4)
        self.assertEqual(result["along"], 0.8)
        self.assertEqual(result["version"], "b" * 64)
        self.assertTrue(result["retained"] and result["dirty"])
        self.assertFalse(result["saving"])

    def test_close_guard_includes_staging_and_clears_after_successful_save(self):
        result = self.client("""
const event={prevented:false,preventDefault(){this.prevented=true;}};beforeUnload(event);
api=async()=>({saved:true,version:nextVersion});await saveStaging(scene);
console.log(JSON.stringify({prevented:event.prevented,unsaved:hasUnsavedChanges()}));
""")
        self.assertTrue(result["prevented"])
        self.assertFalse(result["unsaved"])

    def test_declining_project_change_keeps_the_staging_draft(self):
        result = self.client("""
let prompted=0;confirm=()=>{prompted++;return false;};await selectProject('other');
console.log(JSON.stringify({prompted,project:S.project,retained:S.stagingDrafts.get(scene)===draft}));
""")
        self.assertEqual(result["prompted"], 1)
        self.assertEqual(result["project"], "creator")
        self.assertTrue(result["retained"])

    def test_an_unversioned_draft_cannot_fetch_a_new_version_to_authorize_itself(self):
        result = self.client("""
draft.version=null;api=async()=>{requests.push('unexpected');};await saveStaging(scene);
console.log(JSON.stringify({requests,retained:S.stagingDrafts.get(scene)===draft}));
""")
        self.assertEqual(result["requests"], [])
        self.assertTrue(result["retained"])

    def test_saving_one_scene_rebases_only_drafts_from_the_same_snapshot(self):
        result = self.client("""
const other={...draft,positions:[],episode:'EP001'};
const stale={...other,version:'c'.repeat(64)};
S.stagingDrafts.set('EP001-SC002',other);S.stagingDrafts.set('EP001-SC003',stale);
api=async()=>({saved:true,version:nextVersion});await saveStaging(scene);
console.log(JSON.stringify({other:other.version,stale:stale.version,retained:S.stagingDrafts.has('EP001-SC002')}));
""")
        self.assertEqual(result["other"], "b" * 64)
        self.assertEqual(result["stale"], "c" * 64)
        self.assertTrue(result["retained"])

    def test_reload_failure_and_cancel_both_preserve_the_draft(self):
        result = self.client("""
confirm=()=>false;api=async()=>{requests.push('unexpected');};await reloadStaging(scene);
const cancelled=requests.length===0 && S.stagingDrafts.get(scene)===draft;
confirm=()=>true;api=async()=>{throw new Error('offline');};await reloadStaging(scene);
console.log(JSON.stringify({cancelled,retained:S.stagingDrafts.get(scene)===draft,dirty:draft.dirty}));
""")
        self.assertTrue(result["cancelled"] and result["retained"] and result["dirty"])


class DashboardDiagnosticHttpTests(unittest.TestCase):
    def test_episode_http_exposes_snapshot_version_errors_and_nonblocking_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "creator"
            make_creator_project(project)
            episode = project / "剧集/EP001"
            script = episode / "剧本.md"
            script.write_text(script.read_text(encoding="utf-8") + "\n江晨把一张纸条塞进抽屉。\n", encoding="utf-8")
            server = editor_fixtures.create_server(workspace, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                request = editor_fixtures.DashboardStagingEditorTests.request
                projects = json.loads(request(server, host, port, "GET", "/api/projects")[2])["projects"]
                status, _, raw = request(server, host, port, "GET", f"/api/episode?project={projects[0]['id']}&ep=EP001")
                self.assertEqual(status, 200)
                data = json.loads(raw)
                self.assertTrue(any("纸条塞进抽屉" in error for error in data["checks"]["errors"]))
                self.assertTrue(data["checks"]["diagnostics"])
                file_status, _, file_raw = request(server, host, port, "GET", "/api/file?" + urlencode({"project": projects[0]["id"], "path": "剧集/EP001/分镜.md"}))
                self.assertEqual(file_status, 200)
                self.assertEqual(data["documentVersions"]["分镜.md"], json.loads(file_raw)["version"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
