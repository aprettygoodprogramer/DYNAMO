from __future__ import annotations

import base64
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from ddgs import DDGS
from playwright.sync_api import sync_playwright


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

    def run(self, query: str) -> str:
        with DDGS() as ddg:
            results = ddg.text(query, max_results=5)
        return "\n\n".join(
            f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}"
            for r in results
        )


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
        user_choice = input(
            f"The AI is attempting to run: {commands}. "
            "Press Enter to proceed, or type anything to cancel: "
        )
        if user_choice != "":
            return "The User refused to run the command"

        if not isinstance(commands, list) or not all(
            isinstance(x, str) for x in commands
        ):
            return "Error: 'commands' must be a list of strings."

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