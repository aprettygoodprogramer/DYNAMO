from model import Ollama, Provider
from DYNAMO import DYNAMO
from dotenv import load_dotenv
from toolcall import ToolRegistry, WebSearchTool, ReadFileTool, RunCommand, ScreenshotTool, ScreenshotTool
from agent import Agent
def main():
    load_dotenv()
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(ReadFileTool())
    registry.register(ScreenshotTool())
    #registry.register(RunCommand())
    test=Provider("deepseek/deepseek-v4-flash", "OpenAI", False, "https://openrouter.ai/api/v1")
    v1=DYNAMO(test, 2, """Reaserch ALL the AI news in the past week. It is currently July 3rd 2026. ONLT USE INFORMATION FROM THE WEB. Your training data is outdated.""",     tools=registry.get_schemas(),
    tool_executor=registry.execute)
    output = v1.run()

    




    

    


if __name__ == "__main__":
    main()
