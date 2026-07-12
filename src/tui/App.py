from __future__ import annotations

import getpass
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal, Middle, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    LoadingIndicator,
    Markdown,
    Select,
    Static,
)

from core.DYNAMO import DYNAMO
from core.model import Provider
from tui.Screens import ConfirmScreen, SettingsScreen
from core.agent import Agent
from core.toolcall import (
    ReadFileTool,
    RunCommand,
    ScreenshotTool,
    ToolRegistry,
    WebSearchTool,
    BrowserTool,
)


@dataclass
class JobResult:
    job_id: int
    mode: str
    prompt: str
    output: str = ""
    error: str | None = None
    done: bool = False


class AssistantTUI(App[None]):
    TITLE = "DYNAMO"
    SUB_TITLE = "OpenRouter terminal interface"

    CSS = """
    Screen {
        background: $surface;
        align: center middle;
    }

    #card {
        width: 110;
        max-width: 98%;
        height: 42;
        max-height: 92%;
        border: round $primary;
        padding: 1 2;
    }

    #greeting {
        text-align: center;
        text-style: bold;
        color: $text;
        height: auto;
        margin-bottom: 1;
    }

    #output-scroll {
        height: 1fr;
        border: round $secondary;
        margin-bottom: 1;
        display: none;
        padding: 0 1;
        scrollbar-gutter: stable;
    }

    #output {
        height: auto;
        margin: 0;
        padding: 1 0;
    }

    #status {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #loading {
        width: 5;
        height: 1;
        display: none;
    }

    #prompt-row {
        height: 3;
        border: round $primary;
    }

    #prompt {
        width: 1fr;
        border: none;
        background: transparent;
    }

    #settings-button {
        width: 5;
        min-width: 5;
        border: round $primary;
        margin: 0 0 0 1;
    }
    """

    BINDINGS = [
        ("ctrl+s", "save_output", "Save"),
        ("ctrl+l", "clear_output", "Clear"),
        ("ctrl+comma", "open_settings", "Settings"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.last_output = ""
        self.settings_screen = SettingsScreen()

        # Concurrency
        self._job_lock = threading.Lock()
        self._chat_lock = threading.Lock()
        self._next_job_id = 1
        self.active_jobs = 0
        self.jobs: dict[int, JobResult] = {}

        # Persistent chat session (survives across messages)
        self.chat_agent: Agent | None = None
        self.chat_session_key: tuple[str, str] | None = None  # (model_id, endpoint)
        self.chat_history: list[tuple[str, str]] = []  # (role, text)

    def compose(self) -> ComposeResult:
        with Center(), Middle():
            with Vertical(id="card"):
                yield Static(
                    f"Hello, Welcome back {self._username()}!",
                    id="greeting",
                )

                with VerticalScroll(id="output-scroll"):
                    yield Markdown(id="output")

                with Horizontal(id="status"):
                    yield LoadingIndicator(id="loading")
                    yield Static("Ready", id="status-text")

                with Horizontal(id="prompt-row"):
                    yield Input(
                        placeholder="Ask anything...",
                        id="prompt",
                    )
                    yield Button("\u2699", id="settings-button")

        yield Footer()

    @staticmethod
    def _username() -> str:
        try:
            name = getpass.getuser()
        except Exception:
            name = "there"

        return name.split(".")[0].capitalize() if name else "there"

    def on_mount(self) -> None:
        self.install_screen(self.settings_screen, name="settings")

    # -- settings helpers -------------------------------------------------

    def get_selected_model(self) -> str:
        custom_model = self.settings_screen.query_one(
            "#custom-model", Input
        ).value.strip()

        if custom_model:
            return custom_model

        selected = self.settings_screen.query_one("#model-select", Select).value

        if selected is Select.BLANK:
            raise ValueError("Select a model or enter a custom model ID.")

        return str(selected)

    def get_selected_mode(self) -> str:
        mode = self.settings_screen.query_one("#mode-select", Select).value

        if mode is Select.BLANK:
            return "auto"

        return str(mode)

    def get_iterations(self) -> int:
        raw_value = self.settings_screen.query_one(
            "#iterations-input", Input
        ).value.strip()

        try:
            iterations = int(raw_value)
        except ValueError as error:
            raise ValueError(
                "Maximum iterations must be a whole number."
            ) from error

        if iterations < 1:
            raise ValueError("Maximum iterations must be at least 1.")

        if iterations > 100:
            raise ValueError("Maximum iterations cannot exceed 100.")

        return iterations

    def build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()

        if self.settings_screen.query_one("#tool-web-search", Checkbox).value:
            registry.register(WebSearchTool())

        if self.settings_screen.query_one("#tool-read-file", Checkbox).value:
            registry.register(ReadFileTool())

        if self.settings_screen.query_one("#tool-screenshot", Checkbox).value:
            registry.register(ScreenshotTool())

        if self.settings_screen.query_one("#tool-run-command", Checkbox).value:
            registry.register(RunCommand(confirm=self.confirm_command))

        if self.settings_screen.query_one("#tool-browser", Checkbox).value:
            registry.register(BrowserTool(headless=False))

        return registry

    def confirm_command(self, commands: list[str]) -> bool:
        """
        Called by RunCommand from a worker thread. Blocks that worker
        (never the UI thread) until Allow/Deny is chosen.
        """
        result_event = threading.Event()
        approved = {"value": False}

        def handle_result(value: bool | None) -> None:
            approved["value"] = bool(value)
            result_event.set()

        def push() -> None:
            self.push_screen(ConfirmScreen(commands), handle_result)

        self.call_from_thread(push)
        result_event.wait()
        return approved["value"]

    def classify_mode(self, provider: Provider, prompt: str) -> str:
        classifier_prompt = (
            "You are a routing assistant for an AI agent framework.\n"
            "Decide whether the request below needs an agentic loop with "
            "tools (web search, reading files, running shell commands, "
            "taking screenshots) and multiple reasoning steps, or whether "
            "it can be answered directly with a single chat response with "
            "no tools.\n\n"
            f"Request:\n{prompt}\n\n"
            "Respond with exactly one word: DYNAMO or CHAT."
        )

        try:
            result = provider.chat(classifier_prompt)
        except Exception:
            return "dynamo"

        decision = (result or "").strip().upper()

        if "CHAT" in decision and "DYNAMO" not in decision:
            return "chat"

        return "dynamo"

    # -- chat session helpers -----------------------------------------------

    def get_or_create_chat_agent(
        self,
        provider: Provider,
        model_id: str,
        endpoint: str,
        registry: ToolRegistry,
    ) -> Agent:
        """Reuse one Agent/session so chat keeps multi-turn context."""
        key = (model_id, endpoint)
        schemas = registry.get_schemas()

        if self.chat_agent is None or self.chat_session_key != key:
            self.chat_agent = Agent(
                name="chat",
                client=provider,
                system_prompt="You are a helpful assistant.",
                tools=schemas if schemas else None,
                tool_executor=registry.execute if schemas else None,
            )
            self.chat_session_key = key

        return self.chat_agent

    def reset_chat_session(self) -> None:
        self.chat_agent = None
        self.chat_session_key = None
        self.chat_history.clear()

    # -- UI state -----------------------------------------------------------

    def _refresh_busy_ui(self) -> None:
        loading = self.query_one("#loading", LoadingIndicator)
        loading.display = self.active_jobs > 0

        if self.active_jobs <= 0:
            self.set_status("Ready")
        else:
            self.set_status(f"{self.active_jobs} job(s) running…")

    def set_status(self, message: str) -> None:
        self.query_one("#status-text", Static).update(message)

    @work(exclusive=True)
    async def _set_output_markdown(self, content: str) -> None:
        """Render markdown and jump to the latest content."""
        markdown = self.query_one("#output", Markdown)
        await markdown.update(content or "")
        scroll = self.query_one("#output-scroll", VerticalScroll)
        # Scroll after the next layout pass so content height is correct
        self.call_after_refresh(scroll.scroll_end, animate=False)

    def show_output(self, output: Any) -> None:
        rendered_output = output if isinstance(output, str) else str(output)
        self.last_output = rendered_output

        greeting = self.query_one("#greeting", Static)
        scroll = self.query_one("#output-scroll", VerticalScroll)

        greeting.display = False
        scroll.display = True
        self._set_output_markdown(rendered_output)

    def render_all_output(self) -> None:
        """
        Build the display from completed jobs + chat history.

        Chat transcript appears as a continuous conversation.
        DYNAMO / other job results appear as labeled sections.
        """
        parts: list[str] = []

        if self.chat_history:
            chat_block = "\n\n".join(
                f"**{role.upper()}**\n{text}"
                for role, text in self.chat_history
            )
            parts.append("### Chat\n\n" + chat_block)

        for job_id in sorted(self.jobs):
            job = self.jobs[job_id]
            if not job.done:
                continue
            # Chat results already live in chat_history
            if job.mode == "chat":
                continue

            if job.error:
                parts.append(
                    f"### Job {job_id} ({job.mode}) — ERROR\n\n"
                    f"**Prompt:** {job.prompt}\n\n{job.error}"
                )
            else:
                parts.append(
                    f"### Job {job_id} ({job.mode})\n\n"
                    f"**Prompt:** {job.prompt}\n\n{job.output}"
                )

        rendered = "\n\n---\n\n".join(parts) if parts else ""
        if rendered:
            self.show_output(rendered)
        else:
            # fall back to empty/greeting if nothing to show
            self.last_output = ""

    # -- running the agent ---------------------------------------------------

    @work(thread=True, exclusive=False)
    def run_agent_worker(
        self,
        job_id: int,
        model_id: str,
        endpoint: str,
        iterations: int,
        prompt: str,
        registry: ToolRegistry,
        mode: str,
    ) -> None:
        resolved_mode = mode
        try:
            provider = Provider(model_id, "OpenAI", False, endpoint)

            if resolved_mode == "auto":
                self.call_from_thread(
                    self.set_status,
                    f"[job {job_id}] Deciding mode…",
                )
                resolved_mode = self.classify_mode(provider, prompt)
                self.call_from_thread(
                    self.set_status,
                    f"[job {job_id}] Mode: "
                    + (
                        "Agent (DYNAMO)"
                        if resolved_mode == "dynamo"
                        else "Simple chat"
                    ),
                )

            if resolved_mode == "chat":
                # Serialize chat asks so session history stays consistent
                with self._chat_lock:
                    agent = self.get_or_create_chat_agent(
                        provider, model_id, endpoint, registry
                    )
                    output = agent.ask(prompt)
            else:
                dynamo = DYNAMO(
                    provider,
                    iterations,
                    prompt,
                    tools=registry.get_schemas(),
                    tool_executor=registry.execute,
                )
                output = dynamo.run()

        except Exception as error:
            self.call_from_thread(
                self.finish_job,
                job_id,
                mode=resolved_mode,
                prompt=prompt,
                error=f"{type(error).__name__}: {error}",
            )
            return

        self.call_from_thread(
            self.finish_job,
            job_id,
            mode=resolved_mode,
            prompt=prompt,
            output=output,
        )

    def start_agent(self) -> None:
        try:
            model_id = self.get_selected_model()
            endpoint = self.settings_screen.query_one(
                "#endpoint-input", Input
            ).value.strip()
            iterations = self.get_iterations()
            prompt = self.query_one("#prompt", Input).value.strip()
            registry = self.build_registry()
            mode = self.get_selected_mode()

            if not endpoint:
                raise ValueError("The API endpoint cannot be empty.")

            if not prompt:
                raise ValueError("The prompt cannot be empty.")
        except Exception as error:
            self.notify(str(error), severity="error")
            return

        with self._job_lock:
            job_id = self._next_job_id
            self._next_job_id += 1
            self.active_jobs += 1
            self.jobs[job_id] = JobResult(
                job_id=job_id,
                mode=mode,
                prompt=prompt,
            )

        # Clear immediately so the user can type the next message
        prompt_input = self.query_one("#prompt", Input)
        prompt_input.value = ""
        # Keep input enabled — multi-job / multi-chat is intentional
        prompt_input.disabled = False

        self._refresh_busy_ui()
        self.set_status(
            f"{self.active_jobs} job(s) running… (#{job_id} · {model_id})"
        )

        self.run_agent_worker(
            job_id, model_id, endpoint, iterations, prompt, registry, mode
        )

    def finish_job(
        self,
        job_id: int,
        mode: str,
        prompt: str,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        with self._job_lock:
            self.active_jobs = max(0, self.active_jobs - 1)
            job = self.jobs.get(job_id)
            if job is None:
                job = JobResult(job_id=job_id, mode=mode, prompt=prompt)
                self.jobs[job_id] = job

            job.mode = mode
            job.prompt = prompt
            job.done = True

            if error is not None:
                job.error = error
            else:
                job.output = output if isinstance(output, str) else str(output)

        if error is not None:
            self.notify(
                f"Job {job_id} failed: {error}",
                severity="error",
                timeout=8,
            )
        else:
            # Append chat turns only on success so history matches session
            if mode == "chat":
                self.chat_history.append(("user", prompt))
                self.chat_history.append(
                    ("assistant", job.output if job else str(output))
                )

            self.notify(f"Job {job_id} completed.", severity="information")

            auto_save = self.settings_screen.query_one(
                "#auto-save", Checkbox
            ).value
            if auto_save:
                # Render first so last_output is current, then save
                self.render_all_output()
                self.save_output()
                self._refresh_busy_ui()
                return

        self.render_all_output()
        self._refresh_busy_ui()

    def save_output(self) -> None:
        output = self.last_output
        raw_path = self.settings_screen.query_one(
            "#output-path", Input
        ).value.strip()

        if not raw_path:
            self.notify("Enter an output file path.", severity="error")
            return

        if not output:
            self.notify("There is no output to save.", severity="warning")
            return

        try:
            output_path = Path(raw_path).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
        except OSError as error:
            self.notify(f"Could not save file: {error}", severity="error")
            return

        self.set_status(f"Saved to {output_path}")
        self.notify(f"Saved output to {output_path}")

    def clear_output(self) -> None:
        """Reset display + chat memory. Running jobs still finish in background."""
        self.last_output = ""
        self.jobs.clear()
        self.reset_chat_session()

        greeting = self.query_one("#greeting", Static)
        scroll = self.query_one("#output-scroll", VerticalScroll)

        scroll.display = False
        greeting.display = True
        self._set_output_markdown("")
        self.set_status(
            "Ready"
            if self.active_jobs <= 0
            else f"{self.active_jobs} job(s) still running…"
        )

    # -- actions & events -----------------------------------------------------

    def action_save_output(self) -> None:
        self.save_output()

    def action_clear_output(self) -> None:
        self.clear_output()

    def action_open_settings(self) -> None:
        self.push_screen(self.settings_screen)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-button":
            self.push_screen(self.settings_screen)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt":
            self.start_agent()