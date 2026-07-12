from model import Ollama, Provider
from DYNAMO import DYNAMO
from dotenv import load_dotenv
from toolcall import ToolRegistry, WebSearchTool, ReadFileTool, RunCommand, ScreenshotTool, ScreenshotTool
from agent import Agent
from tui.Run import run_app
def main():
    load_dotenv()
    # registry = ToolRegistry()
    # registry.register(WebSearchTool())
    # registry.register(ReadFileTool())
    # registry.register(ScreenshotTool())
    # #registry.register(RunCommand())
    # #test=Provider("deepseek/deepseek-v4-flash", "OpenAI", False, "https://openrouter.ai/api/v1")
    # test=Provider("google/gemma-4-e2b", "OpenAI", False, "http://localhost:1234/v1")
    # v1=DYNAMO(test, 2, """Give me all the AI news from the past week. It is currently July 4th 2026 (Your training data is outdated, therefore your date is outdated.) ONLY USE KNOWLEDGE FROM THE INTERNET, DO NOT USE ANYTHING ELSE.""",     tools=registry.get_schemas(),
    # tool_executor=registry.execute)
    # output = v1.run()
    run_app()



    




    

    


if __name__ == "__main__":
    main()
