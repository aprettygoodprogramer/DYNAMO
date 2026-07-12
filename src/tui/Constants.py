from __future__ import annotations
 
OPENROUTER_MODELS: list[tuple[str, str]] = [
    ("DeepSeek: DeepSeek V4 Flash", "deepseek/deepseek-v4-flash"),
    ("OpenAI: GPT-5.6 Luna", "openai/gpt-5.6-luna"),
]
 
MODE_OPTIONS: list[tuple[str, str]] = [
    ("Auto (let the model decide)", "auto"),
    ("Agent (DYNAMO + tools)", "dynamo"),
    ("Simple chat (no tools)", "chat"),
]