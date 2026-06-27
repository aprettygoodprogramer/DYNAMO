from model import Ollama, Provider
from DYNAMO import DYNAMO
from dotenv import load_dotenv
from toolcall import ToolRegistry, WebSearchTool, ReadFileTool

def main():
    load_dotenv()
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(ReadFileTool())
    test=Provider("deepseek/deepseek-v4-flash", "OpenAI", False, "https://openrouter.ai/api/v1")
    v1=DYNAMO(test, 2, """What are the current developments in AI as of June 2026? (Your base knowledge won't be enough; use tool calls. Your training data is outdated, the current date is June 27th, 2026)""",     tools=registry.get_schemas(),
    tool_executor=registry.execute)
    output = v1.run()




    

    


if __name__ == "__main__":
    main()
