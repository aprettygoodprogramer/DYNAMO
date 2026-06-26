import os
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional




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
    


class OpenAI(model):
    def __init__(self, model_name, api_key):
        super().__init__(model_name, api_key)
        import openai
        self.client = openai.OpenAI(
            api_key=self.api_key or os.getenv("OPENAI_API_KEY")
        )
    def chat_with_history(self, messages: List[Dict[str, str]], **kwargs):
            completion = self.client.chat.completions.create(
             model=self.model_name,
             messages=messages,
            **kwargs

         )
            return completion.choices[0].message.content
    

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
    def __init__(self, model_name, provider, api_key, url: Optional[str] = None):
        self.model_name = model_name
        self.provider = provider
        self.api_key = api_key
        self.url=url
        if provider == "Ollama":
            self.provider=Ollama(model_name, url)
    def chat(self, prompt: str, **kwargs):
        return self.provider.chat(prompt, kwargs)
    def chat_with_history(self, messages: List[Dict[str, str]], **kwargs):
        return self.provider.chat_with_history(messages, **kwargs)


        
