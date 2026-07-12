from __future__ import annotations

import base64
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from ddgs import DDGS
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

 
from typing import Optional
 
class Tool(ABC):
    name: str
    description: str
    parameters: dict

    @abstractmethod
    def run(self, **kwargs) -> str:
        pass

    def to_schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def execute(self, name: str, args: dict) -> str:
        if name not in self.tools:
            return f"Unknown tool: {name}"
        return self.tools[name].run(**args)

    def get_schemas(self):
        return [t.to_schema() for t in self.tools.values()]


import time

class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for current information."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
        },
        "required": ["query"],
    }

    def run(self, query: str, retries: int = 3, delay: float = 3.0) -> str:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                with DDGS() as ddg:
                    results = ddg.text(query, max_results=5)
                if not results:
                    return "No results found."
                return "\n\n".join(
                    f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}"
                    for r in results
                )
            except Exception as e:
                last_error = e
                print(f"[WebSearchTool] Attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)
        return f"Search failed after {retries} attempts: {last_error}"


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a file from disk."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    }

    def run(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Error: {e}"


class RunCommand(Tool):

    name = "run_command"
    description = "Run a command (supports >, >>, 2>, 2>> without a shell)."
    parameters = {
        "type": "object",
        "properties": {
            "commands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of command tokens (e.g. ['ls', '-la'])",
            }
        },
        "required": ["commands"],
    }

    def __init__(self, confirm: Optional[Callable[[list[str]], bool]] = None):
        """
        confirm: optional callback that receives the command tokens and
        returns True/False for whether to proceed. If not provided, falls
        back to a blocking input() prompt on stdin (only safe for plain
        CLI use — never pass None when running inside a GUI/TUI, since a
        raw input() call will fight with the UI for control of the
        terminal).
        """
        self.confirm = confirm

    def _ask_permission(self, commands: list[str]) -> bool:
        if self.confirm is not None:
            try:
                return bool(self.confirm(commands))
            except Exception:
                return False

        user_choice = input(
            f"The AI is attempting to run: {commands}. "
            "Press Enter to proceed, or type anything to cancel: "
        )
        return user_choice == ""

    def _is_within(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _resolve_write_path(self, raw_path: str) -> Path:
        p = Path(raw_path).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()

        allowed_roots = [
            Path.cwd().resolve(),
            Path("/tmp").resolve(),
            Path("/out").resolve(),
        ]
        if not any(self._is_within(p, r) for r in allowed_roots):
            raise ValueError(
                f"Refusing to write outside allowed roots: {p} "
                f"(allowed: cwd, /tmp, /out)"
            )
        return p

    def _parse_redirects(self, tokens: list[str]):
        argv: list[str] = []
        stdout_path: Path | None = None
        stderr_path: Path | None = None
        stdout_append = False
        stderr_append = False

        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in (">", ">>", "1>", "1>>", "2>", "2>>"):
                if i + 1 >= len(tokens):
                    raise ValueError(f"Redirection operator '{t}' missing a path.")
                target = tokens[i + 1]

                if t in (">", "1>", ">>", "1>>"):
                    stdout_path = self._resolve_write_path(target)
                    stdout_append = t.endswith(">>")
                else:
                    stderr_path = self._resolve_write_path(target)
                    stderr_append = t.endswith(">>")

                i += 2
                continue

            argv.append(t)
            i += 1

        if not argv:
            raise ValueError("No command provided.")

        return argv, stdout_path, stdout_append, stderr_path, stderr_append

    def run(self, commands: list) -> str:
        if not isinstance(commands, list) or not all(
            isinstance(x, str) for x in commands
        ):
            return "Error: 'commands' must be a list of strings."

        if not self._ask_permission(commands):
            return "The User refused to run the command"

        try:
            argv, out_path, out_append, err_path, err_append = (
                self._parse_redirects(commands)
            )

            stdout_f = None
            stderr_f = None
            try:
                if out_path is not None:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    mode = "a" if out_append else "w"
                    stdout_f = open(out_path, mode, encoding="utf-8")
                if err_path is not None:
                    err_path.parent.mkdir(parents=True, exist_ok=True)
                    mode = "a" if err_append else "w"
                    stderr_f = open(err_path, mode, encoding="utf-8")

                result = subprocess.run(
                    argv,
                    capture_output=(stdout_f is None and stderr_f is None),
                    stdout=stdout_f,
                    stderr=stderr_f,
                    text=True,
                    shell=False,
                    timeout=60,
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "HOME": os.environ.get("HOME", ""),
                    },
                )

                if stdout_f is not None or stderr_f is not None:
                    return "OK (output redirected)"

                if result.stdout:
                    return result.stdout
                if result.stderr:
                    return result.stderr
                return f"OK (exit {result.returncode})"
            finally:
                if stdout_f is not None:
                    stdout_f.close()
                if stderr_f is not None:
                    stderr_f.close()

        except Exception as e:
            return f"The command failed to run: {e}"


class ScreenshotTool(Tool):
    name = "screenshot"
    description = (
        "Take a full-page screenshot of a URL and return the image as a "
        "base64-encoded PNG string."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to screenshot"},
            "full_page": {
                "type": "boolean",
                "description": "Capture full scrollable page (default: true)",
            },
            "save_path": {
                "type": "string",
                "description": "Optional path to save the PNG (e.g. 'shot.png')",
            },
        },
        "required": ["url"],
    }

    def run(
        self,
        url: str,
        full_page: bool = True,
        save_path: str | None = None,
    ) -> str:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle", timeout=30000)
                img_bytes = page.screenshot(full_page=full_page)
                browser.close()

            if save_path:
                with open(save_path, "wb") as f:
                    f.write(img_bytes)
                return f"Screenshot saved to '{save_path}' ({len(img_bytes)} bytes)"

            b64 = base64.b64encode(img_bytes).decode()
            return f"data:image/png;base64,{b64}"

        except Exception as e:
            return f"Screenshot failed: {e}"
        







class BrowserTool(Tool):

 
    name = "browser_use"
    description = (
        "Control a real web browser. Use this to navigate to pages, click "
        "elements, type into fields, read visible text, list links, scroll, "
        "go back, or take a screenshot of the current page. Always start "
        "with action='goto' to load a URL. Elements are targeted with CSS "
        "selectors (e.g. 'button#submit', 'a.nav-link', 'input[name=q]')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "goto",
                    "click",
                    "type",
                    "press",
                    "extract_text",
                    "extract_links",
                    "scroll",
                    "go_back",
                    "go_forward",
                    "screenshot",
                    "current_url",
                    "close",
                ],
                "description": "Which browser action to perform.",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to. Required for 'goto'.",
            },
            "selector": {
                "type": "string",
                "description": (
                    "CSS selector of the target element. Required for "
                    "'click' and 'type'. Optional for 'extract_text' "
                    "(scopes extraction to that element)."
                ),
            },
            "text": {
                "type": "string",
                "description": "Text to type. Required for 'type'.",
            },
            "key": {
                "type": "string",
                "description": "Keyboard key to press, e.g. 'Enter', 'Tab'. Required for 'press'.",
            },
            "direction": {
                "type": "string",
                "enum": ["down", "up"],
                "description": "Scroll direction. Used with 'scroll' (default: down).",
            },
            "save_path": {
                "type": "string",
                "description": "Optional path to save a screenshot PNG to disk.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Max time to wait for an action/selector, in ms (default 15000).",
            },
        },
        "required": ["action"],
    }
 
    # Actions that change state (navigate, click, submit, type) rather than
    # just read the current page. These are the ones gated by `confirm`.
    CONSEQUENTIAL_ACTIONS = {"goto", "click", "type", "press"}
 
    def __init__(
        self,
        headless: bool = True,
        viewport: Optional[dict] = None,
        confirm: Optional[Callable[[dict], bool]] = None,
    ):
        """
        confirm: optional callback that receives a dict describing the
        pending action (e.g. {"action": "click", "selector": "#buy-now"})
        and returns True/False for whether to proceed. Only called for
        CONSEQUENTIAL_ACTIONS -- read-only actions like extract_text or
        screenshot always run without asking.
 
        If confirm is None (default), consequential actions run
        automatically with no gate. Pass a callback if you want a human
        (or a policy check) in the loop before the agent clicks/types/
        navigates.
        """
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 800}
        self.confirm = confirm
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
 
    def _ask_permission(self, action_info: dict) -> bool:
        if self.confirm is None:
            return True
        try:
            return bool(self.confirm(action_info))
        except Exception:
            return False
 
    # -- lifecycle -----------------------------------------------------
 
    def _ensure_started(self):
        if self._page is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page(viewport=self.viewport)
 
    def close(self):
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()
            self._browser = None
            self._page = None
            self._playwright = None
 
    # -- main entrypoint -------------------------------------------------
 
    def run(
        self,
        action: str,
        url: str | None = None,
        selector: str | None = None,
        text: str | None = None,
        key: str | None = None,
        direction: str = "down",
        save_path: str | None = None,
        timeout_ms: int = 15000,
    ) -> str:
        try:
            if action == "close":
                self.close()
                return "Browser closed."
 
            if action in self.CONSEQUENTIAL_ACTIONS:
                info = {"action": action, "url": url, "selector": selector, "text": text, "key": key}
                info = {k: v for k, v in info.items() if v is not None}
                if not self._ask_permission(info):
                    return "The user refused to run this browser action."
 
            self._ensure_started()
            page = self._page
 
            if action == "goto":
                if not url:
                    return "Error: 'url' is required for action='goto'."
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                title = page.title()
                return f"Loaded {page.url}\nTitle: {title}"
 
            if action == "click":
                if not selector:
                    return "Error: 'selector' is required for action='click'."
                page.click(selector, timeout=timeout_ms)
                return f"Clicked '{selector}'. Current URL: {page.url}"
 
            if action == "type":
                if not selector or text is None:
                    return "Error: 'selector' and 'text' are required for action='type'."
                page.fill(selector, text, timeout=timeout_ms)
                return f"Typed into '{selector}'."
 
            if action == "press":
                if not key:
                    return "Error: 'key' is required for action='press'."
                target = selector if selector else "body"
                page.press(target, key, timeout=timeout_ms)
                return f"Pressed '{key}' on '{target}'."
 
            if action == "extract_text":
                if selector:
                    el = page.query_selector(selector)
                    if el is None:
                        return f"No element found for selector '{selector}'."
                    return el.inner_text()
                return page.inner_text("body")
 
            if action == "extract_links":
                links = page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))",
                )
                if not links:
                    return "No links found."
                return "\n".join(
                    f"{l['text'] or '(no text)'} -> {l['href']}" for l in links[:200]
                )
 
            if action == "scroll":
                delta = 1000 if direction == "down" else -1000
                page.mouse.wheel(0, delta)
                return f"Scrolled {direction}."
 
            if action == "go_back":
                page.go_back(timeout=timeout_ms)
                return f"Went back. Current URL: {page.url}"
 
            if action == "go_forward":
                page.go_forward(timeout=timeout_ms)
                return f"Went forward. Current URL: {page.url}"
 
            if action == "current_url":
                return page.url
 
            if action == "screenshot":
                img_bytes = page.screenshot(full_page=True)
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(img_bytes)
                    return f"Screenshot saved to '{save_path}' ({len(img_bytes)} bytes)"
                b64 = base64.b64encode(img_bytes).decode()
                return f"data:image/png;base64,{b64}"
 
            return f"Unknown action: {action}"
 
        except Exception as e:
            return f"Browser action '{action}' failed: {e}"