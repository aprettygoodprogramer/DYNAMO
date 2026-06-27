from model import Ollama, Provider
from DYNAMO import DYNAMO
from dotenv import load_dotenv
from toolcall import ToolRegistry, WebSearchTool, ReadFileTool, RunCommand
from agent import Agent
def main():
    load_dotenv()
    # registry = ToolRegistry()
    # registry.register(WebSearchTool())
    # registry.register(ReadFileTool())
    # test=Provider("deepseek/deepseek-v4-flash", "OpenAI", False, "https://openrouter.ai/api/v1")
    # v1=DYNAMO(test, 2, """What are the current developments in AI as of June 2026? (Your base knowledge won't be enough; use tool calls. Your training data is outdated, the current date is June 27th, 2026)""",     tools=registry.get_schemas(),
    # tool_executor=registry.execute)
    # output = v1.run()

    test_reg=ToolRegistry()
    test=Provider("openai/gpt-oss-20b", "OpenAI", False, "https://openrouter.ai/api/v1")
    test_reg.register(RunCommand())
    test_aegent=Agent("Echo Engineer", test, "You are a master bash scripter", tools=test_reg.get_schemas(), tool_executor=test_reg.execute)
    print(test_aegent.ask("Make a new directory called test, this is simple a test to see if the tool call is working."))





    

    


if __name__ == "__main__":
    main()
