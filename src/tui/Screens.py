from __future__ import annotations
 
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static
 
from tui.Constants import MODE_OPTIONS, OPENROUTER_MODELS
 
 
class SettingsScreen(ModalScreen[None]):
    """Configuration panel for model, mode, tools, and output options."""
 
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
            yield Checkbox("Give the agent full acess to a browswer", value=False, id="tool-browser")
 
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
 