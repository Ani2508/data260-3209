"""
hw1_client.py - interactive 5-turn CLI demo for Part 4.

Every model call goes through the shared adapter (src/model_client.complete()).
The system prompt is loaded from AGENT.md, which asks for strict bullet-only
code review. After each turn we print per-turn token counts; on exit we print
cumulative totals. A /stats command reports turn count, cumulative tokens, and
serialized conversation-history length WITHOUT adding a turn.

Usage:
    py -3.12 hw1_client.py
Commands inside the chat:
    /stats   - show turn count, cumulative tokens, history length
    exit     - quit and print cumulative summary
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from model_client import ModelClient  # noqa: E402


def load_system_prompt(path="AGENT.md"):
    """AGENT.md becomes the system prompt (strict bullet-only code review)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ("You are a code reviewer. Respond ONLY with bullet points. "
                "Each bullet starts with '- '. No paragraphs, no prose.")


def serialized_history_length(messages):
    """Length of the whole conversation serialized to text (chars).
    This is what gets resent to the model every turn."""
    return len(json.dumps(messages))


def print_stats(turn_count, cum_in, cum_out, messages):
    """/stats - reads state only, never mutates the history."""
    print("\n===== /stats =====")
    print(f"Turns completed          : {turn_count}")
    print(f"Cumulative input tokens  : {cum_in}")
    print(f"Cumulative output tokens : {cum_out}")
    print(f"Cumulative total tokens  : {cum_in + cum_out}")
    print(f"Serialized history length: {serialized_history_length(messages)} chars")
    print("==================\n")


def main():
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    # IMPORTANT: force_json=False -- this is a prose/bullet chat, not JSON output.
    client = ModelClient(model=model, temperature=0.0, force_json=False)

    system_prompt = load_system_prompt()

    # Conversation history: the system prompt is the first message and is
    # resent on every turn along with all prior user/assistant messages.
    messages = [{"role": "system", "content": system_prompt}]

    turn_count = 0
    cum_in = 0
    cum_out = 0

    print("HW1 Client - 5-turn code-review demo (type '/stats' or 'exit')")
    print(f"Model: {model}\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = "exit"

        if not user_input:
            continue

        if user_input == "/stats":
            print_stats(turn_count, cum_in, cum_out, messages)
            continue

        if user_input.lower() in ("exit", "quit"):
            break

        # Add the user's message, resend the WHOLE history to the model.
        messages.append({"role": "user", "content": user_input})
        result = client.complete(messages)

        # Record the assistant reply so the next turn includes it.
        messages.append({"role": "assistant", "content": result.text})

        turn_count += 1
        cum_in += result.input_tokens
        cum_out += result.output_tokens

        print(f"\nassistant>\n{result.text}\n")
        print(f"[turn {turn_count}] input={result.input_tokens} "
              f"output={result.output_tokens} total={result.total_tokens}")

    # ---- On exit: cumulative summary ----
    print("\n========== SESSION SUMMARY ==========")
    print(f"Total turns              : {turn_count}")
    print(f"Cumulative input tokens  : {cum_in}")
    print(f"Cumulative output tokens : {cum_out}")
    print(f"Cumulative total tokens  : {cum_in + cum_out}")
    print("=====================================")


if __name__ == "__main__":
    main()
