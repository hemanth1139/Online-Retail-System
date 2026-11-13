from config import validate_config
from core.bedrock_client import BedrockNL2SQL
from core.database import get_connection
from utils.logger import get_logger

logger = get_logger()

def main():
    print("\n======================================")
    print("       NORTHWIND NL2SQL - TOOL USE")
    print("======================================")
    try:
        validate_config()
        print("\nChecking PostgreSQL connection...")
        conn = get_connection()
        conn.close()
        print("Database connection successful.")
        print("Initializing Amazon Bedrock...")
        assistant = BedrockNL2SQL()
        print("Bedrock client initialized.")
    except Exception as exc:
        print(f"\nStartup error: {exc}")
        print("Check .env, AWS authentication, model access and network connectivity.")
        return

    while True:
        try:
            question = input("\nAsk a database question (or type exit): ").strip()
            if question.lower() in {"exit", "quit"}:
                break
            if not question:
                continue
            print("\nProcessing with Amazon Bedrock Tool Use...\n")
            answer = assistant.ask(question)
            print("======================================")
            print("                 ANSWER")
            print("======================================")
            print(answer)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as exc:
            logger.exception("Question processing failed")
            print(f"\nQuery error: {exc}")

    print("\nApplication closed.")

if __name__ == "__main__":
    main()
