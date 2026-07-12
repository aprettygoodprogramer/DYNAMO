from __future__ import annotations

from dotenv import load_dotenv

from tui.App import AssistantTUI


def run_app() -> None:
    """Load environment variables and run the DYNAMO terminal UI."""
    load_dotenv()
    AssistantTUI().run()