import os
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json



class model(ABC):
    def __init__(self, model_name, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    def chat_with_history(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> str:
        pass


    
    def chat(self, prompt, **kwargs):
        messages=[{"role": "user", "content": prompt}]
        return self.chat_with_history(messages, **kwargs)
    


class OpenAIProvider(model):
    def __init__(self, model_name, api_key, bu):
        super().__init__(model_name, api_key)
        self.bu = bu
        import openai

        self.client = openai.OpenAI(
            base_url=self.bu,
            api_key=self.api_key or os.getenv("OPENAI_API_KEY"),
        )

    def chat_with_history(self, messages: List[Dict[str, str]], **kwargs):
        tools = kwargs.pop("tools", None)
        tool_executor = kwargs.pop("tool_executor", None)

        while True:
            create_kwargs = {"model": self.model_name, "messages": messages, **kwargs}
            if tools:
                create_kwargs["tools"] = tools

            completion = self.client.chat.completions.create(**create_kwargs)
            message = completion.choices[0].message

            if message.tool_calls:
                # FIXED: Convert API object to dict and drop None values 
                # (prevents OpenRouter 400 errors)
                messages.append(message.model_dump(exclude_none=True))
                
                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = tool_executor(tc.function.name, args)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        # Adding name is good practice for the tool response
                        "name": tc.function.name, 
                        "content": str(result),
                    })
            else:
                return message.content
    

class Ollama(model):
    def __init__(self, model_name, api_url):
        super().__init__(model_name)
        self.api_url=api_url
    def chat_with_history( self, messages: List[Dict[str, str]], **kwargs):
        payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.7),
                    },
                }
        response = requests.post(self.api_url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]
    

class Provider:
    def __init__(self, model_name, provider, api_key, url: Optional[str] = None, reasoning=False):
        self.model_name = model_name
        self.provider = provider
        self.reasoning = reasoning
        self.api_key = api_key
        self.url=url
        if provider == "Ollama":
            self.provider=Ollama(model_name, url)
        if provider == "OpenAI":
            self.provider=OpenAIProvider(model_name, api_key, url)
    def chat(self, prompt: str, **kwargs):
        return self.provider.chat(prompt, **kwargs)
    def chat_with_history(self, messages, **kwargs):
        if self.reasoning:
            kwargs.setdefault("reasoning", {"effort": "high"})
        return self.provider.chat_with_history(messages, **kwargs)
    def create_session(self, system_prompt, tools=None, tool_executor=None):
        return ChatSession(self.provider, system_prompt, tools=tools, tool_executor=tool_executor)

    

class ChatSession:
    def __init__(self, provider, system_prompt=None, tools=None, tool_executor=None):
        self.provider = provider
        self.tools = tools
        self.tool_executor = tool_executor
        self.history = []
        if system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

    def send_message(self, prompt: str, **kwargs) -> str:
        self.history.append({"role": "user", "content": prompt})
        response = self.provider.chat_with_history(
            self.history,
            tools=self.tools,
            tool_executor=self.tool_executor,
            **kwargs
        )
        self.history.append({"role": "assistant", "content": response})
        return response
    




        
