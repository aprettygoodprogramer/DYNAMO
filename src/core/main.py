from model import Ollama, Provider
from DYNAMO import DYNAMO
from dotenv import load_dotenv

def main():
    load_dotenv()

    test=Provider("deepseek/deepseek-v4-flash", "OpenAI", False, "https://openrouter.ai/api/v1")
    v1=DYNAMO(test, 2, """Make me a cohesive plan to get me (The user) to become rich. I will paste this plan back in and enable tool calling enabled. Budget of 100$. (tool calling means that agents can preform real world actions like searching the web, creating files, spending money, etc)""")
    output = v1.run()




    

    


if __name__ == "__main__":
    main()
