from model import Ollama, Provider
def main():
    history = [
        {"role": "system", "content": "You are a AI helper"},
        {"role": "user", "content": "Yo whats up man!"}
    ]
    test=Provider("gemma4:e2b", "Ollama", "", "http://localhost:11434/api/chat")
    print(test.chat_with_history(history))   

    


if __name__ == "__main__":
    main()
