from abc import ABC, abstractmethod
import json
from ddgs import DDGS

import subprocess

subprocess.run(["ls", "-l"]) 

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
                "parameters": self.parameters
            }
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
            "query": {"type": "string", "description": "The search query"}
        },
        "required": ["query"]
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
            "path": {"type": "string", "description": "File path to read"}
        },
        "required": ["path"]
    }

    def run(self, path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except Exception as e:
            return f"Error: {e}"
class RunCommand(Tool):
    name="run_command"
    description="Run any command."
    parameters = {
        "type": "object",
        "properties": {
            "commands": {"type": "list", "description": "list of commands to run"}
        },
        "required": ["commands"]
    }

    def run(self, commands: list) -> str:

        input(f"The AI is attempting to run: {commands}. Type anything if you would like to cancel")
        if input!="":
            try:
                output = subprocess.run(commands, capture_output=True, shell=True, text=True)

                return output
            except:
                return "The Command failed to run."
        else:
            return "The User refused to run the command"



