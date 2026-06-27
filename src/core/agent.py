class Agent:
    def __init__(self, name, client, system_prompt, tools=None, tool_executor=None):
        self.name = name
        self.session = client.create_session(
            system_prompt=system_prompt,
            tools=tools,
            tool_executor=tool_executor
        )

    def ask(self, prompt: str) -> str:
        return self.session.send_message(prompt)