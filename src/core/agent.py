from model import Provider, ChatSession

class Agent:
    def __init__(self, name: str, client: Provider, system_prompt: str):
        self.name = name
        self.session = client.create_session(system_prompt=system_prompt)

    def ask(self, prompt: str) -> str:
        reply = self.session.send_message(prompt)
        return reply

