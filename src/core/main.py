from model import Ollama
def main():
    history = [
        {"role": "system", "content": "You are a AI helper"},
        {"role": "user", "content": "Yo whats up man!"}
    ]
    ollam_test = Ollama("gemma4:e2b", "http://localhost:11434/api/chat")    
    print(ollam_test.chat_with_history(history))

    


if __name__ == "__main__":
    main()
