from abc import ABC, abstractmethod
import json
from ddgs import DDGS

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

