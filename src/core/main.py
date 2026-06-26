from model import Ollama, Provider
from DYNAMO import DYNAMO
def main():

    test=Provider("gemma4:e2b", "Ollama", "", "http://localhost:11434/api/chat")
    v1=DYNAMO(test, 2, "Write a well reaserched essay about Linux and Linus Torvalds.")
    v1.run()


    

    


if __name__ == "__main__":
    main()
