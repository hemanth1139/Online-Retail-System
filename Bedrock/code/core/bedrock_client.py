import json
import boto3
from config import AWS_REGION, MODEL_ID, PROMPTS_DIR, CONFIG_DIR, MAX_TOOL_ROUNDS
from tools.tool_definitions import TOOL_CONFIG
from core.tool_executor import execute_tool_use

def _read_text(path):
    return path.read_text(encoding="utf-8")

def build_system_prompt():
    system_text = _read_text(PROMPTS_DIR / "system_prompt.md")
    generation = _read_text(PROMPTS_DIR / "sql_generation_prompt.md")
    examples = json.loads(_read_text(CONFIG_DIR / "few_shot_examples.json"))
    examples_text = "\n\n".join(
        f"Question: {x['question']}\nSQL: {x['sql']}" for x in examples
    )
    return system_text + "\n\n" + generation + "\n\nFEW-SHOT EXAMPLES:\n" + examples_text

class BedrockNL2SQL:
    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        self.system = [{"text": build_system_prompt()}]

        
    def ask(self, question):
        messages = [{"role": "user", "content": [{"text": question}]}]

        # Token usage counters for this question
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        api_call_number = 0

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.converse(
                modelId=MODEL_ID,
                system=self.system,
                messages=messages,
                toolConfig=TOOL_CONFIG,
                inferenceConfig={"maxTokens": 1200, "temperature": 0.1}
            )

            # Extract token usage from this API call
            usage = response.get("usage", {})

            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)
            call_total_tokens = usage.get("totalTokens", 0)

            api_call_number += 1

            # Accumulate usage for the current question
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_tokens += call_total_tokens

            # Display usage for each API call
            print(f"\n--- Bedrock API Call {api_call_number} ---")
            print(f"Input tokens:  {input_tokens}")
            print(f"Output tokens: {output_tokens}")
            print(f"Total tokens:  {call_total_tokens}")

            output_message = response["output"]["message"]
            messages.append(output_message)

            tool_uses = [
                block["toolUse"] for block in output_message.get("content", [])
                if "toolUse" in block
            ]

            if not tool_uses:
                print("\n========== TOKEN USAGE SUMMARY ==========")
                print(f"Total API calls:  {api_call_number}")
                print(f"Total input tokens:  {total_input_tokens}")
                print(f"Total output tokens: {total_output_tokens}")
                print(f"Total tokens:        {total_tokens}")
                print("=========================================")

                return "\n".join(
                    block["text"] for block in output_message.get("content", [])
                    if "text" in block
                ).strip()

            tool_results = [
                execute_tool_use(tool) for tool in tool_uses
            ]

            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            f"Bedrock exceeded the maximum of {MAX_TOOL_ROUNDS} tool-use rounds."
        )
