"""Real-browser regressions for creator-facing Dashboard behaviour."""

import json
import hashlib
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover - exercised by dependency-free local runs
    if os.environ.get("DASHBOARD_BROWSER_REQUIRED") == "1":
        raise
    expect = sync_playwright = None

from tests.test_dashboard_server import (
    EXAMPLE,
    PIXEL,
    SKILL,
    STILL_CUT_LIST,
    create_server,
    dashboard_server,
    make_creator_project,
    make_project,
)

NO_OVERFLOW = """() => {
  const width = document.documentElement.clientWidth;
  const escaped = [...document.querySelectorAll('body *')].filter((node) => {
    const box = node.getBoundingClientRect();
    if (!box.width || box.right <= width + 1) return false;
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      if (['auto', 'hidden', 'scroll'].includes(getComputedStyle(parent).overflowX)) return false;
    }
    return true;
  });
  return [document.documentElement.scrollWidth - width, escaped.slice(0, 5).map((node) => node.tagName + '.' + node.className)];
}"""


class Browser:
    """One server over a temporary workspace and one Chromium, shared by a test class."""

    @classmethod
    def start(cls, workspace: Path) -> None:
        cls.server = create_server(workspace, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.origin = f"http://{host}:{port}"
        cls.url = f"{cls.origin}/#{cls.server.access_token}"
        cls.playwright = sync_playwright().start()
        browser_path = os.environ.get("DASHBOARD_CHROMIUM_EXECUTABLE")
        try:
            cls.browser = cls.playwright.chromium.launch(
                headless=True, **({"executable_path": browser_path} if browser_path else {})
            )
        except Exception:
            cls.playwright.stop()
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join(timeout=3)
            raise

    @classmethod
    def stop(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def open(self, width: int = 1440, height: int = 900, route: str = "#/", **options):
        context = self.browser.new_context(
            viewport={"width": width, "height": height}, reduced_motion="reduce", **options
        )
        self.addCleanup(context.close)
        page = context.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        self.addCleanup(self.assertEqual, page_errors, [])
        page.goto(self.url)
        expect(page.locator("#view")).to_have_attribute("data-state", "ready")
        if route != "#/":
            self.go(page, route)
        return page

    @staticmethod
    def go(page, route: str) -> None:
        page.evaluate("(hash) => { location.hash = hash; }", route)
        page.wait_for_function(
            "(hash) => { const v = document.querySelector('#view'); return v.dataset.route === hash && v.dataset.state === 'ready'; }",
            arg=route,
        )

    def assertNoHorizontalOverflow(self, page) -> None:
        extra, escaped = page.evaluate(NO_OVERFLOW)
        self.assertEqual((extra, escaped), (0, []))


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class CreatorDeskBrowserTests(Browser, unittest.TestCase):
    """The stage views over a creator-first project with a cut list, media and a review."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        cls.project = workspace / "creator"
        make_creator_project(cls.project)
        for number in range(3, 9):
            (cls.project / f"剧集/EP{number:03d}").mkdir()
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_overview_lists_every_episode_and_leads_with_what_must_change(self) -> None:
        page = self.open()
        rows = page.locator(".matrix tbody tr")
        self.assertEqual(
            rows.evaluate_all("nodes => nodes.map((node) => node.dataset.episode)"),
            [f"EP{number:03d}" for number in range(1, 9)],
        )
        first = rows.first
        self.assertEqual(
            first.locator(".pip[data-on='1']").evaluate_all("nodes => nodes.map((node) => node.dataset.stage)"),
            ["script", "settings", "board", "imgp", "vidp", "cut", "film", "review"],
        )
        todos = page.locator("#nextSteps .todo")
        self.assertEqual(
            todos.evaluate_all("nodes => nodes.map((node) => node.dataset.ep)"), ["EP001", "EP002", "EP003"]
        )
        expect(todos.first).to_contain_text("必须改")
        rows.nth(1).click()
        page.wait_for_function("() => location.hash === '#/EP002'")

    def test_copy_to_assistant_puts_a_request_on_the_clipboard_instead_of_producing(self) -> None:
        page = self.open()
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.origin)
        page.locator("#nextSteps .todo").first.get_by_role("button", name="复制给助手").click()
        expect(page.locator("#toast")).to_contain_text("已复制")
        self.assertEqual(
            page.evaluate("() => navigator.clipboard.readText()"),
            "请按 EP001 的审查意见，先改必须改的 1 条（REV-001）。",
        )

    def test_the_stage_bar_is_the_episodes_progress(self) -> None:
        page = self.open(route="#/EP001")
        tabs = page.locator("#stagebar .tab")
        self.assertEqual(
            tabs.evaluate_all("nodes => nodes.map((node) => node.querySelector('.lbl').textContent)"),
            ["概况", "剧本", "设定", "分镜", "提示词", "成片", "审查"],
        )
        expect(page.locator('#stagebar [data-stage="board"] .meta')).to_have_text("22 镜")
        expect(page.locator('#stagebar [data-stage="review"] .dot')).to_have_class("dot warn")
        page.locator('#stagebar [data-stage="script"]').click()
        page.wait_for_function("() => location.hash === '#/EP001/script'")
        expect(page.locator('#stagebar [aria-current="page"]')).to_have_attribute("data-stage", "script")
        self.go(page, "#/EP002")
        expect(page.locator('#stagebar [data-stage="board"] .meta')).to_have_text("未写")

    def test_rhythm_strip_is_proportional_and_metrics_follow_the_profile(self) -> None:
        page = self.open(route="#/EP001/board")
        bars = page.locator(".strip-bars .sb")
        expect(bars).to_have_count(22)
        widths = bars.evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().width)")
        # SHOT-002 is 4 s and SHOT-003 is 2 s: twice the width, less the gap.
        self.assertAlmostEqual(widths[1] / widths[2], 2, delta=0.15)
        expect(page.locator('.sb[data-shot="SHOT-EP001-006"]')).to_have_class(re.compile(r"\bunsized\b"))
        expect(page.locator(".sb .cl")).to_have_count(11)
        cards = page.locator("#boardMetrics .gauge")
        # A target without a tolerance is reported as a distance, not judged.
        expect(cards.nth(0)).to_contain_text(re.compile(r"目标 60 秒 · (多|少) [\d.]+ 秒"))
        expect(cards.nth(0).locator(".status")).to_have_count(0)
        expect(cards.nth(2)).to_contain_text("50%")
        expect(cards.nth(3)).to_contain_text("留意")
        # The one bound start frame is shown; the others are shot-size diagrams.
        expect(page.locator(".shot .thumb img")).to_have_count(1)

    def test_the_shot_drawer_follows_the_strip_and_the_keyboard(self) -> None:
        page = self.open(route="#/EP001/board")
        page.locator('.sb[data-shot="SHOT-EP001-004"]').click()
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-004'")
        drawer = page.locator("#inspector")
        expect(drawer).to_be_visible()
        expect(drawer.locator(".ins-head .t")).to_have_text("没有针眼的手")
        expect(page.locator(".sb.sel")).to_have_attribute("data-shot", "SHOT-EP001-004")
        page.keyboard.press("ArrowRight")
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-005'")
        expect(drawer.locator(".ins-head .id")).to_have_text("SHOT-EP001-005")
        page.keyboard.press("Escape")
        page.wait_for_function("() => location.hash === '#/EP001/board'")
        expect(drawer).to_be_hidden()

    def test_script_reads_as_a_screenplay_with_links_from_the_cut_list(self) -> None:
        page = self.open(route="#/EP001/script")
        expect(page.locator(".slug")).to_have_count(2)
        expect(page.locator(".dlg")).to_have_count(12)
        expect(page.locator(".dlg.vo").first).to_contain_text("上辈子，我死在病床上。")
        expect(page.locator(".onscreen")).to_have_count(5)
        # A line links to a shot only where the cut list quotes it as a subtitle.
        quoted = page.locator('.dlg[data-line="都听见了。新媒体这摊子，本来就是空白。"] .shotref')
        expect(quoted).to_have_attribute("href", "#/EP001/board/SHOT-EP001-002")
        expect(page.locator('.dlg[data-line="空白才好。"] .shotref')).to_have_count(0)
        expect(page.locator('.dlg .shotref[href$="SHOT-EP001-001"]')).to_have_count(1)
        page.locator(".slug .go").first.click()
        page.wait_for_function("() => location.hash === '#/EP001/board?scene=EP001-SC001'")
        expect(page.locator(".shot")).to_have_count(13)
        expect(page.locator(".blocking-card")).to_have_count(1)
        expect(page.locator('.blocking-card[data-scene="EP001-SC001"] dd').first).to_contain_text("办公桌")
        page.locator(".shot").first.click()
        expect(page.locator("#insBlocking")).to_contain_text("working side")

    def test_settings_cards_show_locks_and_filter_the_storyboard(self) -> None:
        page = self.open(route="#/EP001/settings")
        card = page.locator('.asset[data-entry="江晨"]')
        expect(card.locator(".lock .surface")).to_have_text("pine-green lapel service jacket")
        expect(card.locator(".pstrip i")).to_have_count(22)
        expect(card.locator(".pstrip i.lk")).to_have_count(11)
        expect(page.locator(".era .p")).to_have_text("当下（2020 年代）")
        card.get_by_role("link", name="在分镜里筛出").click()
        page.wait_for_function("() => location.hash.startsWith('#/EP001/board?entity=')")
        expect(page.locator(".filter-note")).to_contain_text("江晨")
        expect(page.locator(".shot")).to_have_count(13)

    def test_prompts_copy_verbatim_and_count_what_was_copied(self) -> None:
        page = self.open(route="#/EP001/prompts/video")
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.origin)
        source = (EXAMPLE / "视频提示词.md").read_text(encoding="utf-8").split("\n")
        first = source[source.index("### 可复制提示词") + 1][2:]
        expect(page.locator("#copyProgress")).to_have_text("0 / 22")
        page.locator(".copybar").get_by_role("button", name="复制下一条").click()
        expect(page.locator("#copyProgress")).to_have_text("1 / 22")
        self.assertEqual(page.evaluate("() => navigator.clipboard.readText()"), first)
        expect(page.locator('.pcard[data-key="MOTION-EP001-001"]')).to_have_class(re.compile(r"\bcopied\b"))
        page.get_by_role("button", name="清除标记").click()
        expect(page.locator("#copyProgress")).to_have_text("0 / 22")

    def test_film_view_lays_the_cut_list_on_a_timeline(self) -> None:
        page = self.open(route="#/EP001/film")
        expect(page.locator(".tl-cut")).to_have_count(3)
        expect(page.locator(".tl-sub")).to_have_count(3)
        expect(page.locator(".tl-txt")).to_have_count(4)
        expect(page.locator(".tl-sfx")).to_have_count(2)
        expect(page.locator("#film")).to_have_count(1)
        widths = page.locator(".tl-cut").evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().width)")
        self.assertAlmostEqual(widths[1] / widths[2], 2, delta=0.1)
        page.locator("#r-CUT-EP001-002").click()
        expect(page.locator("#r-CUT-EP001-002")).to_have_class(re.compile(r"\bon\b"))
        expect(page.locator("#nowCut")).to_contain_text("四个号，四个粉")
        # Clips come only from 来源: SHOT-002 has a file named after it, and still waits.
        self.go(page, "#/EP001/film/clips")
        tiles = page.locator("[data-shot-tile]")
        self.assertEqual(tiles.evaluate_all("nodes => nodes.filter((node) => node.dataset.hasClip === '1').map((node) => node.dataset.shotTile)"), ["SHOT-EP001-001"])

    def test_film_view_marks_still_cuts_and_lays_voice_lines_on_their_own_track(self) -> None:
        episode = self.project / "剧集/EP003"
        (episode / "剪辑单.md").write_text(STILL_CUT_LIST, encoding="utf-8")
        (episode / "制作成果/images").mkdir(parents=True)
        (episode / "制作成果/images/002.png").write_bytes(PIXEL)
        self.addCleanup(lambda: (episode / "剪辑单.md").unlink())
        page = self.open(route="#/EP003/film")
        expect(page.locator(".tl-cut")).to_have_count(3)
        self.assertEqual(
            page.locator(".tl-cut").evaluate_all("nodes => nodes.map((node) => node.classList.contains('still'))"),
            [False, True, True],
        )
        expect(page.locator(".tl-voice")).to_have_count(4)
        expect(page.locator(".tl-sfx:not(.tl-voice)")).to_have_count(1)
        lefts = page.locator(".tl-voice").evaluate_all("nodes => nodes.map((node) => node.getBoundingClientRect().left)")
        self.assertEqual(lefts, sorted(lefts))
        # The last cut's line is a J-cut: it is heard before its picture starts.
        cut_left = page.locator(".tl-cut").nth(2).evaluate("node => node.getBoundingClientRect().left")
        self.assertLess(lefts[-1], cut_left)
        expect(page.locator("#r-CUT-EP001-002")).to_contain_text("静帧 · 推近 2.5%/秒")
        expect(page.locator("#r-CUT-EP001-002")).to_contain_text("S_room.mp3")
        expect(page.locator("#r-CUT-EP001-003")).to_contain_text("静帧 · 固定")
        expect(page.locator("#r-CUT-EP001-002")).to_contain_text("L02.mp3")

    def test_review_findings_link_to_where_they_are(self) -> None:
        page = self.open(route="#/EP001/review")
        finding = page.locator("#f-REV-001")
        expect(finding).to_contain_text("先给周薄森半拍停顿")
        self.assertNotIn("STY-14", page.locator("#view").inner_text())
        finding.get_by_role("link", name="镜 011").click()
        page.wait_for_function("() => location.hash === '#/EP001/board/SHOT-EP001-011'")
        expect(page.locator("#inspector .refstate.must")).to_contain_text("空白才好")
        self.go(page, "#/EP001/review")
        page.locator('[data-rf="could"]').click()
        expect(page.locator(".finding")).to_have_count(1)

    def test_search_jumps_to_the_line_it_found(self) -> None:
        page = self.open(route="#/EP001/board")
        page.keyboard.press("Control+k")
        expect(page.locator("#palette")).to_be_visible()
        page.fill("#palq", "空白才好")
        expect(page.locator(".pal-item").first).to_be_visible()
        expect(page.locator(".pal-item mark").first).to_have_text("空白才好")
        page.locator(".pal-item", has_text="江晨").first.click()
        page.wait_for_function("() => location.hash === '#/EP001/script/EP001-SC001'")
        expect(page.locator(".dlg.hl")).to_contain_text("空白才好")
        page.keyboard.press("/")
        page.locator('[data-scope="series"]').click()
        page.fill("#palq", "空白才好")
        expect(page.locator(".pal-item .w", has_text="EP002").first).to_be_visible()

    def test_editing_saves_markdown_and_refuses_to_overwrite_a_newer_file(self) -> None:
        page = self.open(route="#/EP001/board/SHOT-EP001-011")
        page.get_by_role("link", name="在分镜.md 里编辑这一镜").click()
        expect(page.locator("#editState")).to_have_text("已载入")
        editor = page.locator("#editor")
        caret = editor.evaluate("node => node.value.slice(node.selectionStart, node.selectionStart + 18)")
        self.assertEqual(caret, "## SHOT-EP001-011 ")
        path = self.project / "剧集/EP001/分镜.md"
        original = path.read_text(encoding="utf-8")
        self.addCleanup(path.write_text, original, encoding="utf-8")
        editor.evaluate("node => { node.value = node.value.replace('## SHOT-EP001-011 · 冷茶', '## SHOT-EP001-011 · 凉茶'); node.dispatchEvent(new Event('input')); }")
        path.write_text(original + "\n<!-- 别处的修改 -->\n", encoding="utf-8")
        page.keyboard.press("Control+s")
        expect(page.locator("#saveError")).to_have_attribute("data-conflict", "1")
        self.assertIn("别处的修改", path.read_text(encoding="utf-8"))
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="载入最新版本").click()
        expect(page.locator("#editState")).to_have_text("已载入")
        editor.evaluate("node => { node.value = node.value.replace('## SHOT-EP001-011 · 冷茶', '## SHOT-EP001-011 · 凉茶'); node.dispatchEvent(new Event('input')); }")
        page.get_by_role("button", name="保存").click()
        expect(page.locator("#editState")).to_contain_text("已保存")
        saved = path.read_text(encoding="utf-8")
        self.assertIn("## SHOT-EP001-011 · 凉茶", saved)
        self.assertIn("别处的修改", saved)
        # The structured view reads the saved Markdown.
        self.go(page, "#/EP001/board/SHOT-EP001-011")
        expect(page.locator("#inspector .ins-head .t")).to_have_text("凉茶")

    def test_phone_width_keeps_every_view_inside_the_screen(self) -> None:
        page = self.open(390, 844)
        for route in (
            "#/", "#/EP001", "#/EP001/script", "#/EP001/settings", "#/EP001/board",
            "#/EP001/board/SHOT-EP001-004", "#/EP001/prompts/video", "#/EP001/film",
            "#/EP001/review", "#/files",
        ):
            with self.subTest(route=route):
                self.go(page, route)
                self.assertNoHorizontalOverflow(page)
        self.go(page, "#/EP001/board/SHOT-EP001-004")
        box = page.locator("#inspector").bounding_box()
        self.assertEqual((box["x"], box["width"]), (0, 390))
        self.go(page, "#/EP001/review")
        current = page.locator('#stagebar [aria-current="page"]').bounding_box()
        self.assertLessEqual(current["x"] + current["width"], 390)
        self.go(page, "#/")
        expect(page.locator(".ep-cards")).to_be_visible()
        expect(page.locator(".matrix-wrap")).to_be_hidden()


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class DeliveryGroupBrowserTests(Browser, unittest.TestCase):
    """A multi-shot group is copied once, in sequence, instead of its members."""

    GROUP_BODY = "镜头1：攥紧的茶杯。镜头2：穿 pine-green lapel service jacket 的四个号四个粉。"

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "grouped"
        make_creator_project(project)
        video = project / "剧集/EP001/视频提示词.md"
        video.write_text(
            video.read_text(encoding="utf-8")
            + "\n## GROUP-EP001-01 · 低头到手\n- 成员：MOTION-EP001-003、MOTION-EP001-004\n"
            + f"- 时长：5s\n\n### 可复制提示词\n> {cls.GROUP_BODY}\n",
            encoding="utf-8",
        )
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_the_group_replaces_its_members_in_the_copy_queue(self) -> None:
        page = self.open(route="#/EP001/prompts/video")
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.origin)
        expect(page.locator("#copyProgress")).to_have_text("0 / 21")
        keys = page.locator(".pcard").evaluate_all("nodes => nodes.map((node) => node.dataset.key)")
        self.assertEqual(keys[:4], ["MOTION-EP001-001", "MOTION-EP001-002", "GROUP-EP001-01", "MOTION-EP001-005"])
        self.assertNotIn("MOTION-EP001-004", keys)
        page.locator('.pcard[data-key="GROUP-EP001-01"] .pact button').click()
        self.assertEqual(page.evaluate("() => navigator.clipboard.readText()"), self.GROUP_BODY)


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class PlainProjectBrowserTests(Browser, unittest.TestCase):
    """Projects outside the five documents still open, and raw text stays text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "alpha"
        make_project(project, "ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMN")
        (project / "带注释.md").write_text(
            "# 带注释\n\n"
            "<!-- 改编取舍：\n     番号一律虚构。 -->\n\n"
            "第一段正文。\n\n"
            "第二段正文 <!-- 行内备注 --> 后半句。\n\n"
            "```md\n<!-- 代码块里的注释要保留 -->\n```\n\n"
            "嵌套 <!<!-- 内层 -->-- 外层 --> 之后。\n\n"
            "<!-- 跨行备注\n     第二行 --> 终止符后面的正文。\n\n"
            "<!-- 注释里的围栏\n```md\n围栏里的内容不该出现\n```\n-->\n\n"
            "围栏之后的正文。\n\n"
            "<!-- 这条没有闭合\n还有一行\n",
            encoding="utf-8",
        )
        make_project(workspace / "empty", "空项目")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_creator_notes_in_markdown_comments_stay_out_of_the_reading_view(self) -> None:
        page = self.open(route=f"#/file?path={quote('带注释.md')}")
        body = page.locator("[data-raw] .doc")
        expect(body).to_contain_text("第一段正文。")
        text = body.inner_text()
        for kept in ("第一段正文。", "第二段正文", "后半句", "嵌套", "之后。", "代码块里的注释要保留",
                     "终止符后面的正文。", "围栏之后的正文。", "这条没有闭合", "还有一行"):
            self.assertIn(kept, text)
        for dropped in ("改编取舍", "番号一律虚构", "行内备注", "外层", "跨行备注", "第二行",
                        "围栏里的内容不该出现", "注释里的围栏"):
            self.assertNotIn(dropped, text)
        self.assertEqual(text.count("嵌套"), 1)

    def test_long_project_title_never_creates_horizontal_page_scroll(self) -> None:
        page = self.open()
        for width in (1440, 861, 760, 620, 390, 360):
            with self.subTest(width=width):
                page.set_viewport_size({"width": width, "height": 700})
                self.assertNoHorizontalOverflow(page)

    def test_projects_switch_and_an_empty_one_says_what_to_do(self) -> None:
        page = self.open()
        value = page.locator("#projectSelect option", has_text="空项目").get_attribute("value")
        page.select_option("#projectSelect", value)
        expect(page.locator(".matrix-wrap, .empty").first).to_contain_text("还没有分集")
        expect(page.locator("#view")).to_have_attribute("data-state", "ready")

    def test_invalid_projects_payload_shows_creator_safe_chinese_error(self) -> None:
        context = self.browser.new_context(viewport={"width": 861, "height": 650})
        self.addCleanup(context.close)
        page = context.new_page()
        page.route(
            "**/api/projects",
            lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"projects": None})),
        )
        page.goto(self.url)
        expect(page.locator("#notices")).to_contain_text("无效")
        self.assertNotIn("Cannot read properties", page.locator("#notices").inner_text())


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class PlantedMarkupBrowserTests(Browser, unittest.TestCase):
    """Project text is shown as text in every view, never parsed as markup."""

    MARK = '<img id="pwn" src="x">'

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "creator"
        cls.project = project
        make_creator_project(project)
        episode = project / "剧集/EP001"
        # Free-text fields only: IDs, durations and sources stay parseable, so each view renders its structure.
        free = "运镜|起点|终点|目的|景别/机位|声音|唯一动作|画面文字|用途|识别锚点|画面代称|本集造型|连续性锁|时代锚点|生成方式|状态链"
        for path in [*episode.glob("*.md"), *project.glob("审查/*.md")]:
            text = path.read_text(encoding="utf-8")
            text = re.sub(rf"^(## .+ · .+|- (?:{free})：.+|[^#\-\n\[].+)$", lambda m: m.group(1) + cls.MARK, text, flags=re.M)
            path.write_text(text, encoding="utf-8")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_no_view_turns_project_text_into_elements(self) -> None:
        page = self.open()
        for route in (
            "#/", "#/EP001", "#/EP001/script", "#/EP001/settings", "#/EP001/board", "#/EP001/board/SHOT-EP001-004",
            "#/EP001/prompts/video", "#/EP001/prompts/image", "#/EP001/prompts/keyframe", "#/EP001/film",
            "#/EP001/review",
        ):
            with self.subTest(route=route):
                self.go(page, route)
                self.assertEqual(page.locator("#pwn").count(), 0)
        self.go(page, "#/EP001/board")
        expect(page.locator(".shot")).to_have_count(22)
        expect(page.locator("#view")).to_contain_text('<img id="pwn"')
        self.go(page, "#/EP001/prompts/video")
        expect(page.locator("#view")).to_contain_text('文生视频<img id="pwn"')
        page.keyboard.press("/")
        page.fill("#palq", "没有针眼")
        expect(page.locator(".pal-item").first).to_be_visible()
        self.assertEqual(page.locator("#pwn").count(), 0)


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class StagingPlanBrowserTests(Browser, unittest.TestCase):
    """Structured scene staging is drawn and stays inside desktop and phone widths."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "creator"
        cls.project = project
        make_creator_project(project)
        episode = project / "剧集/EP001"
        visual = (episode / "视觉设定.md").read_text(encoding="utf-8")
        view = """\
### 空间视图 · VIEW-OFFICE-MAIN · 主视角
- 图片：无
- 认图来源：prompt
- 屏幕方向：主视角朝北；画面左为西、右为东。
- 平面物件：ITEM-DESK《办公桌》（图框：无；平面：0.24, 0.40, 0.76, 0.68；可坐：否）
- 平面物件：ITEM-CHAIR《办公椅》（图框：无；平面：0.70, 0.16, 0.88, 0.34；可坐：是）

"""
        visual = visual.replace("## 地点 · 副团长办公室\n", "## 地点 · 副团长办公室\n" + view, 1)
        (episode / "视觉设定.md").write_text(visual, encoding="utf-8")
        board = (episode / "分镜.md").read_text(encoding="utf-8")
        board = board.replace(
            "## 场景站位 · EP001-SC001 · 副团长办公室\n",
            "## 场景站位 · EP001-SC001 · 副团长办公室\n"
            "- 空间视图：VIEW-OFFICE-MAIN\n"
            "- 人物位置：江晨｜物：ITEM-DESK｜侧：west｜沿线：0.50｜姿态：stand｜朝向：east\n"
            "- 人物位置：周薄森｜物：ITEM-CHAIR｜侧：on｜沿线：0.50｜姿态：sit｜朝向：west\n",
            1,
        )
        (episode / "分镜.md").write_text(board, encoding="utf-8")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_desktop_and_phone_show_the_scene_plan_without_overflow(self) -> None:
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                page = self.open(width=width, height=height, route="#/EP001/board")
                expect(page.locator(".stage-plan")).to_have_count(1)
                expect(page.locator(".stage-item")).to_have_count(2)
                expect(page.locator(".stage-person")).to_have_count(2)
                expect(page.locator(".stage-plan-svg")).to_be_visible()
                expect(page.locator("[data-stage-save]")).to_be_visible()
                expect(page.locator("[data-stage-extras]")).to_be_visible()
                self.assertNoHorizontalOverflow(page)
                self.assertIn("江晨", page.locator(".stage-plan-svg").get_attribute("aria-label"))
                captures = os.environ.get("DASHBOARD_SCREENSHOTS_DIR")
                if captures:
                    target = Path(captures)
                    target.mkdir(parents=True, exist_ok=True)
                    page.locator(".stage-plan").screenshot(path=str(target / f"staging-{width}.png"))

    def test_drag_posture_and_keyboard_write_back_to_markdown(self) -> None:
        board = self.project / "剧集/EP001/分镜.md"
        original = board.read_text(encoding="utf-8")
        self.addCleanup(board.write_text, original, encoding="utf-8")
        page = self.open(route="#/EP001/board")
        person = page.locator('[data-stage-person="江晨"]')
        tools = page.locator('[data-stage-person-tools="江晨"]')
        person.focus()
        page.keyboard.press("ArrowRight")
        expect(page.locator("[data-stage-status]")).to_contain_text("未保存")
        tools.get_by_role("button", name="坐").click()
        target = page.locator(".stage-plan-svg").evaluate("""svg => {
            const point = svg.createSVGPoint();
            point.x = 79; point.y = 36;
            const screen = point.matrixTransform(svg.getScreenCTM());
            return {x:screen.x, y:screen.y};
        }""")
        person_box = person.locator("circle").bounding_box()
        self.assertIsNotNone(person_box)
        page.mouse.move(
            person_box["x"] + person_box["width"] / 2,
            person_box["y"] + person_box["height"] / 2,
        )
        page.mouse.down()
        page.mouse.move(target["x"], target["y"])
        page.mouse.up()
        page.locator("[data-stage-save]").click()
        expect(page.locator("#toast")).to_contain_text("站位已写回")
        saved = board.read_text(encoding="utf-8")
        self.assertRegex(
            saved,
            r"江晨｜物：ITEM-CHAIR｜侧：(?:on|south)｜沿线：[0-9.]+｜姿态：sit｜朝向：east",
        )
        self.assertIn("## SHOT-EP001-", saved)

    def test_external_edit_conflicts_and_reload_is_explicit(self) -> None:
        board = self.project / "剧集/EP001/分镜.md"
        original = board.read_text(encoding="utf-8")
        self.addCleanup(board.write_text, original, encoding="utf-8")
        page = self.open(route="#/EP001/board")
        page.locator('[data-stage-person="江晨"]').focus()
        page.keyboard.press("ArrowRight")
        external = original.replace("沿线：0.50", "沿线：0.25", 1)
        board.write_text(external, encoding="utf-8")
        page.locator("[data-stage-save]").click()
        expect(page.locator("[data-stage-status]")).to_contain_text("别处修改")
        self.assertEqual(board.read_text(encoding="utf-8"), external)
        expect(page.locator("[data-stage-copy]")).to_be_visible()
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("[data-stage-reload]").click()
        expect(page.locator('[data-stage-person="江晨"]')).to_have_attribute("data-stage-along", "0.25")
        expect(page.locator("[data-stage-save]")).to_be_disabled()

    def test_unsaved_staging_blocks_declined_navigation_and_page_close(self) -> None:
        page = self.open(route="#/EP001/board")
        page.locator('[data-stage-person="江晨"]').focus()
        page.keyboard.press("ArrowRight")
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator('a[href="#/EP001/script"]').first.click()
        expect(page.locator("#view")).to_have_attribute("data-route", "#/EP001/board")
        expect(page.locator("[data-stage-status]")).to_contain_text("未保存")
        prevented = page.evaluate("""() => {
            const event = new Event('beforeunload', {cancelable:true});
            window.dispatchEvent(event);
            return event.defaultPrevented;
        }""")
        self.assertTrue(prevented)

    def test_structural_errors_and_asset_notes_are_readable_in_both_widths(self) -> None:
        script = self.project / "剧集/EP001/剧本.md"
        original = script.read_text(encoding="utf-8")
        self.addCleanup(script.write_text, original, encoding="utf-8")
        script.write_text(original + "\n江晨把一张纸条塞进抽屉。\n", encoding="utf-8")
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                page = self.open(width=width, height=height, route="#/EP001/board")
                errors = page.locator("[data-check-errors]")
                errors.locator("summary").click()
                expect(errors).to_contain_text("纸条塞进抽屉")
                expect(errors.locator(".notice", has_text="missing.png")).not_to_contain_text("制作成果/")
                expect(page.locator("[data-check-diagnostics]")).to_be_visible()
                self.assertNoHorizontalOverflow(page)
                captures = os.environ.get("DASHBOARD_SCREENSHOTS_DIR")
                if captures:
                    target = Path(captures)
                    target.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(target / f"diagnostics-{width}.png"))


@unittest.skipUnless(sync_playwright, "Playwright is unavailable")
class ReferenceOnlyBrowserTests(Browser, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        workspace = Path(cls.temporary.name)
        project = workspace / "character"
        cls.project = project
        tool = dashboard_server.load_project_tool(SKILL)
        tool.initialize_project(
            project,
            title="角色参考图",
            language="zh-CN",
            prompt_language="en",
            aspect_ratio="2:3",
            mode="reference-only",
            suite_root=SKILL,
        )
        source = project / "参考图提示词.md"
        source.write_text(
            "# 参考图提示词\n\n## IMG-HERO · 正面全身\n\n"
            "- 参考：无外部参考\n\n### 可复制提示词\n> portrait\n",
            encoding="utf-8",
        )
        output = project / "production/reference/HERO/front-full.v1.png"
        output.parent.mkdir(parents=True)
        output.write_bytes(PIXEL)
        manifest = {
            "schema_version": "1.0",
            "kind": "reference_manifest",
            "groups": {
                "HERO": {
                    "id": "HERO",
                    "views": {
                        "front-full": {
                            "current": {
                                "job_id": "REF-HERO",
                                "stage": "anchor",
                                "view": "front-full",
                                "version": 1,
                                "output": "production/reference/HERO/front-full.v1.png",
                                "sha256": hashlib.sha256(PIXEL).hexdigest(),
                                "source": "参考图提示词.md",
                                "source_entry": "IMG-HERO",
                                "source_sha256": hashlib.sha256(
                                    source.read_bytes()
                                ).hexdigest(),
                                "depends_on_job_id": None,
                                "depends_on_output": None,
                                "created_at": "2026-10-30T00:00:00Z",
                            },
                            "versions": [],
                        }
                    },
                }
            },
        }
        path = project / "production/reference/index.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        cls.start(workspace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop()
        cls.temporary.cleanup()

    def test_reference_versions_fit_desktop_and_phone(self) -> None:
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                page = self.open(width=width, height=height)
                expect(page.locator("h1")).to_have_text("《角色参考图》")
                expect(page.locator("[data-reference-view]")).to_have_count(1)
                expect(page.locator("[data-reference-view] .status")).to_contain_text(
                    "当前"
                )
                expect(page.locator(".reference-thumb img")).to_be_visible()
                self.assertNoHorizontalOverflow(page)


if __name__ == "__main__":
    unittest.main()
