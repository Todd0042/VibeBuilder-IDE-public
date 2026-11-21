"""UI end-to-end: the real app (Vite dev build in Chromium) against a real server + builder agent.

A working session, start to finish: pair with a 30-second code, sign in with the authenticator, open a
file and save it, watch an agent change files behind your back and review the change set, hit a
conflict and keep your version, search the project, jump to a file with Ctrl+P, run a terminal, then
lock and come back to find your tabs where you left them.

Run: cd server && .venv/bin/pytest -q ../desktop/e2e   (Chromium from Playwright; set VB_SHOTS=dir for screenshots)
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server" / "tests"))
from stack import fresh_code, pair_code, running_stack  # noqa: E402

DESKTOP = Path(__file__).resolve().parents[1]
SHOTS = os.environ.get("VB_SHOTS")


def shot(page: Page, name: str) -> None:
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{SHOTS}/{name}.png")


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    assert _free(1420), "port 1420 (the Vite dev server) is in use"
    with running_stack(tmp_path_factory.mktemp("vbui")) as stack:
        # No built-in server (what a fresh clone without vibebuilder.env gets): the app must ask for it.
        vite = subprocess.Popen(["npx", "vite", "--port", "1420", "--strictPort"], cwd=DESKTOP,
                                env={**os.environ, "VITE_DEFAULT_SERVER": ""},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if not _free(1420):
                    break
                time.sleep(0.1)
            yield stack
        finally:
            vite.terminate()
            vite.wait(5)


def wait_for(cond, what: str, timeout: float = 10) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for: {what}")


def code_input(page: Page):
    return page.locator("input.code:not(.pair)")


def test_working_session(app):
    used: set[int] = set()
    ws = app["ws"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 920})
        page.on("pageerror", lambda e: print("PAGE ERROR:", e))
        page.on("console", lambda m: m.type in ("error", "warning") and print("CONSOLE:", m.text))
        page.goto("http://localhost:1420/")

        # First run, no server known: it asks for the address, and pairing waits for it.
        expect(page.get_by_text("Pair this device")).to_be_visible()
        expect(page.get_by_text("First, enter your IDE server's address")).to_be_visible()
        page.locator("input.code.pair").fill("ABC123")
        expect(page.get_by_role("button", name="Pair")).to_be_disabled()
        expect(page.get_by_role("button", name="Use")).to_be_disabled()
        page.get_by_placeholder("https://ide.example.com").fill(app["url"])
        page.get_by_role("button", name="Use").click()
        expect(page.get_by_text("First, enter your IDE server's address")).to_be_hidden()
        # Remembered across restarts.
        page.reload()
        expect(page.locator(".server .muted")).to_have_text(app["url"].split("://", 1)[1])
        expect(page.get_by_placeholder("https://ide.example.com")).to_have_count(0)

        # Pair, then sign in.
        page.locator("input.code.pair").fill(pair_code(app["data"]))
        page.get_by_role("button", name="Pair").click()
        expect(page.get_by_text("Enter the 6-digit code")).to_be_visible()
        shot(page, "01-sign-in")
        code_input(page).fill(fresh_code(app["totp"], used))
        expect(page.locator(".tree")).to_be_visible(timeout=10_000)
        expect(page.locator(".row.root")).to_contain_text("PROJ")

        # Open a file from the explorer, edit, Ctrl+S.
        page.locator(".row", has_text="src").first.click()
        page.locator(".row", has_text="app.py").click()
        editor = page.locator(".pane:not(.hidden) .cm-content")
        expect(editor).to_contain_text("def hello")
        editor.click()
        page.keyboard.press("Control+End")
        page.keyboard.type("\n# edited in the IDE\n")
        expect(page.locator(".tab.active .x.dirty")).to_be_visible()
        expect(page.locator(".save-all .count")).to_have_text("1")
        shot(page, "02-editing")
        page.keyboard.press("Control+s")
        expect(page.locator(".tab.active .x.dirty")).to_have_count(0, timeout=5000)
        wait_for(lambda: "# edited in the IDE" in (ws / "proj" / "src" / "app.py").read_text(), "Ctrl+S wrote the file")

        # An agent changes files behind the IDE's back -> a change set shows up; review it.
        (ws / "proj" / "README.md").write_text("# proj\n\nA test project.\nNow with docs from the agent.\n")
        (ws / "proj" / "src" / "util.py").write_text("def add(a, b):\n    return a + b\n")
        page.keyboard.press("Control+Shift+G")
        row = page.locator(".cs:not(.live)").first
        expect(row).to_contain_text("2 files", timeout=20_000)
        row.click()
        review = page.locator(".pane:not(.hidden) .review")
        expect(review.locator(".file")).to_have_count(2)
        expect(review).to_contain_text("Now with docs from the agent.")
        expect(review.locator(".ln.add")).to_have_count(3)  # README +1, util.py +2
        expect(review).to_contain_text("A test project.")  # context lines around the change
        shot(page, "03-review")

        # Conflict: unsaved edits in the editor + the agent rewrites the same file.
        page.locator(".tab", has_text="app.py").click()
        editor.click()
        page.keyboard.press("Control+Home")
        page.keyboard.type("# mine\n")
        (ws / "proj" / "src" / "app.py").write_text("# the agent's version\n")
        expect(page.locator(".banner.conflict")).to_be_visible(timeout=15_000)
        shot(page, "04-conflict")
        page.get_by_role("button", name="Keep mine").click()
        expect(page.locator(".banner.conflict")).to_have_count(0)
        wait_for(lambda: (ws / "proj" / "src" / "app.py").read_text().startswith("# mine\n"), "your version saved over the agent's")

        # Search the project, jump to a match. util.py loads slowly here (a slow connection), so Go to File
        # below opens before it arrives: the editor must not take the keyboard away from that dialog.
        page.evaluate("""() => {
          const real = window.fetch;
          window.fetch = async (input, init) => {
            const url = String(input instanceof Request ? input.url : input);
            if (url.includes("/api/v1/fs/file?") && url.includes("util.py") && !window.__slowDone) {
              window.__slowDone = true;
              await new Promise((r) => setTimeout(r, 1500));
            }
            return real(input, init);
          };
        }""")
        page.keyboard.press("Control+Shift+F")
        page.locator(".qbox input").fill("return a + b")
        match = page.locator(".match").first
        expect(match).to_contain_text("return a + b", timeout=10_000)
        shot(page, "05-search")
        match.click()
        expect(page.locator(".area .tab.active")).to_contain_text("util.py")

        # Quick open, while util.py is still loading.
        page.keyboard.press("Control+p")
        page.locator(".box input").fill("readme")
        expect(page.locator(".box .row").first).to_contain_text("README.md")
        page.wait_for_function("() => window.__slowDone")
        page.wait_for_timeout(1700)  # util.py has now loaded and jumped to the match
        expect(page.locator(".box input")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator(".box")).to_have_count(0)
        expect(page.locator(".area .tab.active")).to_contain_text("README.md")

        # Menus: File shows what's possible right now, Edit → Find opens the find bar, Alt+V opens View.
        page.locator(".menubar .top", has_text="File").click()
        drop = page.locator(".drop")
        expect(drop.locator(".item", has_text="Save All")).to_have_class(re.compile("disabled"))
        expect(drop.locator(".item", has_text="proj")).to_be_visible()  # the project list is in File too
        page.locator(".menubar .top", has_text="Edit").hover()  # hover switches menus while one is open
        drop.locator(".item", has_text="Find").first.click()
        expect(page.locator(".pane:not(.hidden) .cm-search")).to_be_visible()
        page.keyboard.press("Escape")
        page.keyboard.press("Alt+v")
        expect(page.locator(".drop")).to_contain_text("Terminal Panel")
        page.keyboard.press("Escape")
        expect(page.locator(".drop")).to_have_count(0)

        # File → Open Folder: a nested folder becomes the explorer's root; Ctrl+P searches inside it.
        page.keyboard.press("Control+Alt+o")
        picker = page.get_by_role("dialog", name="Open folder")
        expect(picker.locator(".row", has_text="proj")).to_be_visible()
        page.keyboard.press("Enter")  # into proj
        expect(picker.locator(".row", has_text="src")).to_be_visible()
        page.keyboard.press("Control+Enter")  # open the selected folder (src)
        expect(page.locator(".row.root")).to_contain_text("SRC")
        expect(page.locator("select.project")).to_have_value("proj/src")
        page.keyboard.press("Control+p")
        expect(page.locator(".box .row").first).to_contain_text(".py")
        expect(page.locator(".box")).not_to_contain_text("README.md")  # outside the open folder
        page.keyboard.press("Escape")
        page.locator("select.project").select_option("proj")

        # A terminal.
        page.locator(".newbtn.k-shell").click()
        term = page.locator(".term:not(.hidden) .xterm")
        expect(term).to_be_visible(timeout=10_000)
        time.sleep(1.0)
        term.click()
        page.keyboard.type("echo vb-$((40+2))")
        page.keyboard.press("Enter")
        wait_for(lambda: "vb-42" in page.evaluate("window.__vbTerminalText()"), "the command's output in the terminal")
        shot(page, "06-terminal")
        tabs_before = page.locator(".area .tab").count()
        page.keyboard.press("Control+w")  # in a shell this deletes a word; it must not close an editor tab
        time.sleep(0.3)
        assert page.locator(".area .tab").count() == tabs_before
        shot(page, "06-terminal")
        tabs_before = page.locator(".area .tab").count()
        page.keyboard.press("Control+w")  # in a shell this deletes a word; it must not close an editor tab
        time.sleep(0.3)
        assert page.locator(".area .tab").count() == tabs_before

        # Lock, sign back in: tabs survive.
        page.locator("button[title^='Lock']").click()
        expect(page.get_by_role("heading", name="Locked")).to_be_visible()
        shot(page, "07-locked")
        code_input(page).fill(fresh_code(app["totp"], used))
        expect(page.locator(".login")).to_have_count(0, timeout=15_000)
        expect(page.locator(".tab", has_text="README.md")).to_be_visible()
        expect(page.locator(".tab", has_text="app.py")).to_be_visible()
        browser.close()
