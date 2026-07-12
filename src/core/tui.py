from __future__ import annotations

import getpass
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal, Middle, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    Label,
    LoadingIndicator,
    Select,
    Static,
)

from DYNAMO import DYNAMO
from model import Provider
from toolcall import (
    ReadFileTool,
    RunCommand,
    ScreenshotTool,
    ToolRegistry,
    WebSearchTool,
)


OPENROUTER_MODELS = [
    ("DeepSeek: DeepSeek V4 Flash", "deepseek/deepseek-v4-flash"),
    ("OpenAI: GPT-5.6 Luna", "openai/gpt-5.6-luna"),
]

MODE_OPTIONS = [
    ("Auto (let the model decide)", "auto"),
    ("Agent (DYNAMO + tools)", "dynamo"),
    ("Simple chat (no tools)", "chat"),
]


class SettingsScreen(ModalScreen[None]):


    CSS = """
    SettingsScreen {
        align: center middle;
        background: $background 60%;
    }

    #settings-card {
        width: 60;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #settings-card .section-title {
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }

    #settings-card .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #settings-card Select,
    #settings-card Input {
        width: 100%;
    }

    #settings-warning {
        margin-top: 1;
        padding: 1;
        border: round $warning;
        color: $warning;
    }

    #settings-close-row {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="settings-card"):
            yield Label("Settings", classes="section-title")

            yield Label("Model", classes="field-label")
            yield Select(
                OPENROUTER_MODELS,
                value=OPENROUTER_MODELS[0][1],
                allow_blank=False,
                id="model-select",
            )

            yield Label("Custom model ID (optional)", classes="field-label")
            yield Input(placeholder="provider/model-name", id="custom-model")

            yield Label("Mode", classes="field-label")
            yield Select(
                MODE_OPTIONS,
                value="auto",
                allow_blank=False,
                id="mode-select",
            )

            yield Label("API endpoint", classes="field-label")
            yield Input(value="https://openrouter.ai/api/v1", id="endpoint-input")

            yield Label("Maximum iterations", classes="field-label")
            yield Input(value="5", type="integer", id="iterations-input")

            yield Label("Tools", classes="section-title")
            yield Checkbox("Web search", value=True, id="tool-web-search")
            yield Checkbox("Read files", value=True, id="tool-read-file")
            yield Checkbox("Screenshot", value=False, id="tool-screenshot")
            yield Checkbox("Run shell commands", value=False, id="tool-run-command")

            yield Static(
                "Warning: Run shell commands allows the model to execute "
                "commands on your computer. Only enable it when you trust "
                "the prompt and model.",
                id="settings-warning",
            )

            yield Label("Output file", classes="section-title")
            yield Input(value="output.md", placeholder="output.md", id="output-path")
            yield Checkbox("Save automatically after running", value=False, id="auto-save")

            with Horizontal(id="settings-close-row"):
                yield Button("Done", id="settings-done", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-done":
            self.dismiss()


class ConfirmScreen(ModalScreen[bool]):
    """Asks the user to approve or deny a shell command the model wants to run."""

    CSS = """
    ConfirmScreen {
        align: center middle;
        background: $background 60%;
    }

    #confirm-card {
        width: 70;
        max-width: 90%;
        height: auto;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }

    #confirm-title {
        color: $warning;
        text-style: bold;
    }

    #confirm-message {
        margin-top: 1;
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: auto;
        align-horizontal: right;
    }

    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "deny", "Deny")]

    def __init__(self, commands: list[str]) -> None:
        super().__init__()
        self.commands = commands

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-card"):
            yield Static("The agent wants to run a command", id="confirm-title")
            yield Static(" ".join(self.commands), id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Deny", id="confirm-deny", variant="default")
                yield Button("Allow", id="confirm-allow", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-allow")

    def action_deny(self) -> None:
        self.dismiss(False)


class AssistantTUI(App[None]):
    TITLE = "DYNAMO"
    SUB_TITLE = "OpenRouter terminal interface"

    CSS = """
    Screen {
        background: $surface;
        align: center middle;
    }

    #card {
        width: 90;
        max-width: 96%;
        height: 26;
        border: round $primary;
        padding: 2 3;
    }

    #greeting {
        text-align: center;
        text-style: bold;
        color: $text;
        height: auto;
        margin-bottom: 1;
    }

    #output {
        height: 1fr;
        border: round $secondary;
        margin-bottom: 1;
        display: none;
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
        self.agent_running = False
        self.settings_screen = SettingsScreen()

    def compose(self) -> ComposeResult:
        with Center(), Middle():
            with Vertical(id="card"):
                yield Static(
                    f"Hello, Welcome back {self._username()}!",
                    id="greeting",
                )

                yield Static("", id="output")

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
        custom_model = self.settings_screen.query_one("#custom-model", Input).value.strip()

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
        raw_value = self.settings_screen.query_one("#iterations-input", Input).value.strip()

        try:
            iterations = int(raw_value)
        except ValueError as error:
            raise ValueError("Maximum iterations must be a whole number.") from error

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

        return registry

    def confirm_command(self, commands: list[str]) -> bool:
        """
        Called by RunCommand from the worker thread. Blocks that thread
        (never the UI thread) while a modal pops up on screen and waits
        for the user to click Allow/Deny.
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

    # -- UI state -----------------------------------------------------------

    def set_running(self, running: bool) -> None:
        self.agent_running = running

        prompt_input = self.query_one("#prompt", Input)
        loading = self.query_one("#loading", LoadingIndicator)

        prompt_input.disabled = running
        loading.display = running

    def set_status(self, message: str) -> None:
        self.query_one("#status-text", Static).update(message)

    def show_output(self, output: Any) -> None:
        rendered_output = output if isinstance(output, str) else str(output)
        self.last_output = rendered_output

        greeting = self.query_one("#greeting", Static)
        output_box = self.query_one("#output", Static)

        greeting.display = False
        output_box.display = True
        output_box.update(rendered_output)

    # -- running the agent ---------------------------------------------------

    @work(thread=True, exclusive=True)
    def run_agent_worker(
        self,
        model_id: str,
        endpoint: str,
        iterations: int,
        prompt: str,
        registry: ToolRegistry,
        mode: str,
    ) -> None:
        try:
            provider = Provider(model_id, "OpenAI", False, endpoint)

            if mode == "auto":
                self.call_from_thread(
                    self.set_status,
                    "Deciding whether to use the agent or chat directly...",
                )
                mode = self.classify_mode(provider, prompt)
                self.call_from_thread(
                    self.set_status,
                    "Auto-selected: " + ("Agent (DYNAMO)" if mode == "dynamo" else "Simple chat"),
                )

            if mode == "chat":
                output = provider.chat(prompt)
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
                self.finish_with_error,
                f"{type(error).__name__}: {error}",
            )
            return

        self.call_from_thread(self.finish_successfully, output)

    def start_agent(self) -> None:
        if self.agent_running:
            self.notify("The agent is already running.", severity="warning")
            return

        try:
            model_id = self.get_selected_model()
            endpoint = self.settings_screen.query_one("#endpoint-input", Input).value.strip()
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

        self.set_running(True)
        self.set_status(f"Running {model_id}...")

        self.run_agent_worker(model_id, endpoint, iterations, prompt, registry, mode)

    def finish_successfully(self, output: Any) -> None:
        self.set_running(False)
        self.show_output(output)
        self.set_status("Completed successfully.")
        self.notify("Agent completed.", severity="information")

        auto_save = self.settings_screen.query_one("#auto-save", Checkbox).value

        if auto_save:
            self.save_output()

    def finish_with_error(self, message: str) -> None:
        self.set_running(False)
        self.show_output(f"Error\n\n{message}")
        self.set_status("Agent failed.")
        self.notify(message, severity="error", timeout=8)

    def save_output(self) -> None:
        output = self.last_output
        raw_path = self.settings_screen.query_one("#output-path", Input).value.strip()

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
        self.last_output = ""

        greeting = self.query_one("#greeting", Static)
        output_box = self.query_one("#output", Static)

        output_box.display = False
        output_box.update("")
        greeting.display = True
        self.set_status("Ready")

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


def main() -> None:
    load_dotenv()
    AssistantTUI().run()


if __name__ == "__main__":
    main()