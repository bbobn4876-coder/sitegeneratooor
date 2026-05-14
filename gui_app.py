#!/usr/bin/env python3
"""
PHP Site Generator — terminal GUI
Run: python gui_app.py
"""
import os
import sys
import json
import queue
import threading
import subprocess

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button, Input, Label, RadioButton, RadioSet,
    RichLog, Static, TextArea, Header, Footer,
)
from textual.reactive import reactive
from textual.css.query import NoMatches

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generator_config.json")
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phpgen_version82.py")


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    cfg = load_config()
    cfg.update(data)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


CSS = """
Screen {
    background: #0d0d0d;
}

.app-container {
    width: 100%;
    height: 100%;
    padding: 1 2;
}

/* ── Header bar ── */
.header-bar {
    height: 3;
    width: 100%;
    border-bottom: solid #2a2a2a;
    margin-bottom: 1;
    padding: 0 1;
    layout: horizontal;
    align: left middle;
}
.header-logo {
    background: #d97706;
    color: #000000;
    width: 3;
    height: 1;
    text-style: bold;
    content-align: center middle;
    margin-right: 1;
}
.header-title {
    color: #e0e0e0;
    text-style: bold;
}
.header-version {
    color: #444444;
    width: 1fr;
    text-align: right;
}

/* ── Section labels ── */
.section-label {
    color: #555555;
    text-style: bold;
    margin-bottom: 0;
    padding: 0 1;
}

/* ── Settings / form boxes ── */
.box {
    border: solid #2a2a2a;
    background: #141414;
    margin-bottom: 1;
    padding: 0;
}
.field-row {
    height: 3;
    layout: horizontal;
    align: left middle;
    border-bottom: solid #1e1e1e;
    padding: 0 1;
}
.field-row:last-of-type {
    border-bottom: none;
}
.field-label {
    width: 18;
    color: #555555;
    content-align: left middle;
}
.field-input {
    background: #141414;
    border: none;
    color: #e0e0e0;
    width: 1fr;
    padding: 0;
}
.field-input:focus {
    border: none;
    background: #141414;
    color: #60a5fa;
}

/* ── Radio row ── */
.radio-row {
    height: 3;
    layout: horizontal;
    align: left middle;
    border-bottom: solid #1e1e1e;
    padding: 0 1;
}
RadioSet {
    background: #141414;
    border: none;
    padding: 0;
    height: 1;
    width: 1fr;
}
RadioSet:focus {
    border: none;
}
RadioButton {
    background: #141414;
    border: none;
    color: #888888;
    padding: 0 1 0 0;
}
RadioButton:hover {
    background: #141414;
    color: #e0e0e0;
}
RadioButton.-selected {
    color: #e0e0e0;
}
RadioButton > .toggle--button {
    color: #d97706;
    background: #141414;
}

/* ── Description textarea ── */
.desc-row {
    min-height: 6;
    layout: horizontal;
    border-bottom: none;
    padding: 0 1;
}
.desc-area {
    background: #141414;
    border: none;
    color: #e0e0e0;
    width: 1fr;
    height: 5;
    padding: 0;
}
.desc-area:focus {
    border: none;
    background: #141414;
}
TextArea .text-area--cursor {
    background: #d97706;
}

/* ── Create button ── */
.create-btn {
    width: 100%;
    margin-top: 1;
    background: #d97706;
    color: #000000;
    text-style: bold;
    border: none;
    height: 3;
}
.create-btn:hover {
    background: #e88b0a;
}
.create-btn:disabled {
    background: #92400e;
    color: #4a3000;
}
.create-btn:focus {
    border: none;
    background: #d97706;
}

/* ── Console ── */
.console-outer {
    border: solid #2a2a2a;
    background: #0a0a0a;
    margin-top: 1;
    height: 1fr;
}
.console-bar {
    height: 2;
    background: #141414;
    border-bottom: solid #2a2a2a;
    layout: horizontal;
    align: left middle;
    padding: 0 1;
}
.console-dots {
    width: 9;
    color: #ff5f57;
}
.console-title {
    color: #444444;
    padding-left: 1;
}
.console-status {
    width: 1fr;
    text-align: right;
    color: #444444;
}
.console-status.running {
    color: #22c55e;
}
.console-status.done {
    color: #22c55e;
}
.console-status.error {
    color: #ef4444;
}
RichLog {
    background: #0a0a0a;
    color: #e0e0e0;
    padding: 0 1;
    scrollbar-background: #0a0a0a;
    scrollbar-color: #2a2a2a;
    scrollbar-color-active: #3a3a3a;
    scrollbar-color-hover: #333333;
    border: none;
}
"""


class GeneratorApp(App):
    CSS = CSS
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    _running: reactive[bool] = reactive(False)

    def __init__(self):
        super().__init__()
        self._q: queue.Queue = queue.Queue()
        cfg = load_config()
        self._cfg = cfg

    def compose(self) -> ComposeResult:
        cfg = self._cfg
        with Container(classes="app-container"):
            # Header
            with Horizontal(classes="header-bar"):
                yield Static(" G ", classes="header-logo")
                yield Static("PHP Site Generator", classes="header-title")
                yield Static("v82 · terminal ui", classes="header-version")

            # Settings
            yield Static("SETTINGS", classes="section-label")
            with Container(classes="box"):
                with Horizontal(classes="field-row"):
                    yield Static("api_key", classes="field-label")
                    yield Input(
                        value=cfg.get("api_key", ""),
                        placeholder="sk-or-v1-…",
                        password=True,
                        id="api_key",
                        classes="field-input",
                    )
                with Horizontal(classes="field-row"):
                    yield Static("bytedance_key", classes="field-label")
                    yield Input(
                        value=cfg.get("bytedance_key", ""),
                        placeholder="ark-…",
                        password=True,
                        id="bytedance_key",
                        classes="field-input",
                    )

            # Generation
            yield Static("GENERATION", classes="section-label")
            with Container(classes="box"):
                with Horizontal(classes="field-row"):
                    yield Static("site_name", classes="field-label")
                    yield Input(
                        placeholder="My Awesome Company",
                        id="site_name",
                        classes="field-input",
                    )
                with Horizontal(classes="radio-row"):
                    yield Static("site_type", classes="field-label")
                    with RadioSet(id="site_type"):
                        yield RadioButton("landing", value=True, id="rb_landing")
                        yield RadioButton("multipage", id="rb_multipage")
                with Horizontal(classes="desc-row"):
                    yield Static("description", classes="field-label")
                    yield TextArea(
                        id="description",
                        classes="desc-area",
                    )

            # Create button
            yield Button("▶   Create", id="create_btn", classes="create-btn")

            # Console
            with Container(classes="console-outer"):
                with Horizontal(classes="console-bar"):
                    yield Static("⬤ ⬤ ⬤", classes="console-dots")
                    yield Static("generator output", classes="console-title")
                    yield Static("idle", id="console_status", classes="console-status")
                yield RichLog(
                    id="console_log",
                    highlight=True,
                    markup=True,
                    wrap=True,
                    auto_scroll=True,
                )

    # ── Event handlers ──────────────────────────────────────

    @on(Button.Pressed, "#create_btn")
    def on_create(self) -> None:
        if self._running:
            return
        self._start_generation()

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        self._start_generation()

    # ── Generation logic ────────────────────────────────────

    def _start_generation(self) -> None:
        api_key = self.query_one("#api_key", Input).value.strip()
        bdc_key = self.query_one("#bytedance_key", Input).value.strip()
        site_name = self.query_one("#site_name", Input).value.strip()
        description = self.query_one("#description", TextArea).text.strip()
        site_type = "multipage" if self.query_one("#rb_multipage", RadioButton).value else "landing"

        if not description:
            self.query_one("#description", TextArea).focus()
            return

        if api_key or bdc_key:
            save_config({"api_key": api_key, "bytedance_key": bdc_key})

        log = self.query_one("#console_log", RichLog)
        log.clear()
        self._set_status("● running", "running")
        self.query_one("#create_btn", Button).disabled = True
        self._running = True

        log.write("[dim]$ python phpgen_version82.py[/dim]")
        log.write("")

        env = os.environ.copy()
        if api_key:
            env["OPENROUTER_API_KEY"] = api_key
        if bdc_key:
            env["BYTEDANCE_KEY"] = bdc_key

        inp = f"{description}\n{site_type}\n{site_name}\n"
        threading.Thread(
            target=self._run_subprocess,
            args=(inp, env),
            daemon=True,
        ).start()
        self._drain_timer = self.set_interval(0.05, self._drain_queue)

    def _run_subprocess(self, inp: str, env: dict) -> None:
        try:
            proc = subprocess.Popen(
                [sys.executable, SCRIPT_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=os.path.dirname(SCRIPT_PATH),
            )
            proc.stdin.write(inp)
            proc.stdin.close()
            for line in proc.stdout:
                self._q.put(("line", line.rstrip("\n")))
            proc.wait()
            self._q.put(("done", proc.returncode))
        except Exception as exc:
            self._q.put(("error", str(exc)))

    def _drain_queue(self) -> None:
        log = self.query_one("#console_log", RichLog)
        finished = False
        for _ in range(50):
            try:
                kind, val = self._q.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                log.write(self._markup(val))
            elif kind == "done":
                finished = True
                if val == 0:
                    log.write("")
                    log.write("[bold green]✓ Generation complete.[/bold green]")
                    self._set_status("✓ done", "done")
                else:
                    log.write("")
                    log.write(f"[red]✗ Process exited with code {val}[/red]")
                    self._set_status(f"✗ exit {val}", "error")
            elif kind == "error":
                finished = True
                log.write(f"[red]ERROR: {val}[/red]")
                self._set_status("✗ error", "error")

        if finished:
            self._running = False
            self.query_one("#create_btn", Button).disabled = False
            # Remove the interval timer
            try:
                self._drain_timer.stop()  # type: ignore
            except Exception:
                pass

    def _set_status(self, text: str, css_class: str) -> None:
        status = self.query_one("#console_status", Static)
        status.update(text)
        status.remove_class("running", "done", "error")
        status.add_class(css_class)

    # ── Line → Rich markup ──────────────────────────────────

    def _markup(self, t: str) -> str:
        if not t.strip():
            return ""
        # error
        if any(c in t for c in ("❌",)) or any(
            w in t.lower() for w in ("traceback", "exception", "ошибка")
        ):
            return f"[red]{_esc(t)}[/red]"
        if "error" in t.lower() and "openrouter" not in t.lower():
            return f"[red]{_esc(t)}[/red]"
        # success
        if "✓" in t or "✅" in t:
            return f"[green]{_esc(t)}[/green]"
        if any(w in t.lower() for w in ("успешно", "готово", "complete", "saved", "done")):
            return f"[green]{_esc(t)}[/green]"
        # warnings
        if "⚠" in t or "warning" in t.lower():
            return f"[yellow]{_esc(t)}[/yellow]"
        # step / headline
        if any(
            t.startswith(p)
            for p in ("🚀", "📋", "📄", "🔧", "🎨", "🖼", "💾", "📁", "🏗", "⚙", "🔑", "🌐", "📝", "✨", "▶")
        ):
            return f"[bold #d97706]{_esc(t)}[/bold #d97706]"
        # section dividers
        if len(t.strip()) > 4 and all(c in "═━─ =" for c in t.strip()):
            return f"[#a78bfa]{_esc(t)}[/#a78bfa]"
        # generation activity
        if any(w in t.lower() for w in ("генерац", "генерир", "создан", "обработ", "пишем")):
            return f"[#22d3ee]{_esc(t)}[/#22d3ee]"
        # dim separators / prompts
        if t.strip().startswith("#") or not t.strip():
            return f"[dim]{_esc(t)}[/dim]"
        return _esc(t)


def _esc(t: str) -> str:
    return t.replace("[", "\\[").replace("]", "\\]")


if __name__ == "__main__":
    app = GeneratorApp()
    app.run()
