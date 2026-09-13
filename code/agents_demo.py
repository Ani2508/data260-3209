"""
agents_demo.py — Planner -> Reviewer -> Finalizer over a local Ollama model.

Input : a title + content from the assigned domain entity.
Output: exactly 3 topical tags + a summary (<=25 words), as valid JSON,
        printed with a Planner/Reviewer transcript and a final Publish package.

All model calls go through src/model_client.complete() (the shared adapter).
Tags are derived from the input title/content (phrase_candidates), never from
hardcoded domain keywords.
"""

import argparse, json, os, re, sys, time
from dataclasses import dataclass
from typing import List, Dict, Any, Iterable, Tuple, TypedDict
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, StrictStr, validator

# Make src/ importable regardless of where the script is run from
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from model_client import ModelClient  # noqa: E402
class AgentState(TypedDict):
    title: str
    content: str
    email: str
    strict: bool
    task: str
    llm: Any
    planner_proposal: Dict[str, Any]
    reviewer_feedback: Dict[str, Any]
    turn_count: int
    turn_ceiling: int
    planner_attempts: int


# Common English words to drop when mining tag candidates from the input text.
STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "than", "your", "you",
    "are", "was", "were", "have", "has", "had", "use", "used", "using", "about", "how",
    "can", "will", "more", "less", "very", "over", "under", "their", "there", "then",
    "our", "out", "on", "in", "of", "to", "by", "a", "an", "is", "it", "as", "we",
    "study", "trial",  # domain-neutral filler common to many inputs
}

class PlannerOutput(BaseModel):
    tags: list[StrictStr]
    summary: StrictStr

    @validator("tags")
    def validate_tags(cls, tags):
        if len(tags) != 3:
            raise ValueError("There must be exactly 3 tags.")

        for tag in tags:
            if not 3 <= len(tag) <= 30:
                raise ValueError(
                    "Each tag must contain between 3 and 30 characters."
                )

        return tags

    @validator("summary")
    def validate_summary(cls, summary):
        word_count = len(summary.split())

        if word_count > 25:
            raise ValueError(
                "The summary must contain at most 25 words."
            )

        return summary
# -------------------------
# Text cleanup + extraction
# -------------------------

def strip_code_and_md(s: str) -> str:
    """Remove markdown/code artifacts from model output and normalize whitespace."""
    s = str(s)
    s = re.sub(r"```.*?```", " ", s, flags=re.DOTALL)   # fenced code blocks
    s = re.sub(r"`([^`]*)`", r"\1", s)                   # inline backticks
    s = re.sub(r"[*_#>]", " ", s)                        # md emphasis/heading chars
    return " ".join(s.split())


def extract_json_block(text: str) -> str:
    """Return the first balanced {...} JSON object in text; else wrap as message."""
    text = str(text).strip()
    start = text.find("{")
    if start == -1:
        return json.dumps({"message": strip_code_and_md(text)})
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    # Unbalanced: wrap what we have
    return json.dumps({"message": strip_code_and_md(text)})


def tokens(txt: str) -> List[str]:
    """Lowercase word tokens, allowing internal hyphens."""
    return re.findall(r"[a-z][a-z\-]+", str(txt).lower())


def ngrams(words: List[str], n: int) -> Iterable[Tuple[str, ...]]:
    for i in range(max(0, len(words) - n + 1)):
        yield tuple(words[i:i + n])


def phrase_candidates(title: str, content: str, maxn: int = 12) -> List[str]:
    """
    Build tag candidates derived ONLY from title+content.
    Strategy: content-word bigrams/trigrams ranked by frequency, then unigrams
    as fallback. This is what makes the 'no hardcoded domain' rule provable —
    every candidate comes from the input text.
    """
    words = tokens(f"{title} {content}")
    content_words = [w for w in words if w not in STOP and len(w) > 2]

    from collections import Counter
    counts: Counter = Counter()

    # Multi-word phrases first (they read as better tags)
    for n in (2, 3):
        for gram in ngrams(content_words, n):
            counts[" ".join(gram)] += 1

    # Rank phrases by frequency, then by length (prefer longer, more specific)
    phrases = sorted(
        [p for p, c in counts.items()],
        key=lambda p: (counts[p], len(p.split())),
        reverse=True,
    )

    # Unigram fallback by frequency
    uni = Counter(content_words)
    unigrams = [w for w, _ in uni.most_common()]

    out: List[str] = []
    for cand in phrases + unigrams:
        if cand not in out:
            out.append(cand)
        if len(out) >= maxn:
            break
    return out


# -------------------------
# Output schema coercion
# -------------------------

def _word_count(s: str) -> int:
    return len(str(s).split())


def _clean_tag(t: str) -> str:
    t = strip_code_and_md(str(t)).lower().strip(" .,-")
    return " ".join(t.split())


def coerce_reply(raw_obj: Any, title: str, content: str, strict: bool) -> Dict[str, Any]:
    """
    Coerce arbitrary model output into the required schema:
      { "thought": str,
        "message": str (non-empty, <=60 words),
        "data": { "tags": [str,str,str], "summary": str (<=25 words, ends '.'),
                  "issues": [str, ...] } }
    Missing/invalid pieces are repaired from phrase_candidates so output is
    always valid even if the model misbehaves.
    """
    obj = raw_obj if isinstance(raw_obj, dict) else {}
    data = obj.get("data") if isinstance(obj.get("data"), dict) else {}

    # ---- tags: exactly 3, cleaned, deduped, backfilled from the input ----
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [_clean_tag(t) for t in tags if str(t).strip()]
    # dedupe preserving order
    seen, deduped = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t); deduped.append(t)
    tags = deduped

    if len(tags) < 3:
        for cand in phrase_candidates(title, content):
            if cand not in tags:
                tags.append(cand)
            if len(tags) >= 3:
                break
    tags = tags[:3]
    while len(tags) < 3:              # absolute last resort
        tags.append(f"topic {len(tags)+1}")

    if strict:
        # enforce at least two multi-word tags where possible
        multi = [t for t in tags if len(t.split()) > 1]
        if len(multi) < 2:
            for cand in phrase_candidates(title, content):
                if len(cand.split()) > 1 and cand not in tags:
                    tags[len(tags) - 1] = cand
                    multi.append(cand)
                if len([t for t in tags if len(t.split()) > 1]) >= 2:
                    break

    # ---- summary: <=25 words, ends with a period ----
    summary = strip_code_and_md(data.get("summary", "") or obj.get("message", ""))
    if _word_count(summary) > 25:
        summary = " ".join(summary.split()[:25])
    summary = summary.strip()
    if summary and not summary.endswith("."):
        summary += "."
    if not summary:
        summary = (title.strip() or "Summary unavailable") + "."

    # ---- message: non-empty, <=60 words, no code ----
    message = strip_code_and_md(obj.get("message", "")) or "Tags and summary prepared."
    if _word_count(message) > 60:
        message = " ".join(message.split()[:60])

    # ---- issues ----
    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    issues = [strip_code_and_md(x) for x in issues if str(x).strip()]

    return {
        "thought": strip_code_and_md(obj.get("thought", "")),
        "message": message,
        "data": {"tags": tags, "summary": summary, "issues": issues},
    }


def parse_and_coerce(text: str, title: str, content: str, strict: bool) -> Dict[str, Any]:
    try:
        obj = json.loads(extract_json_block(text))
    except Exception:
        obj = {"message": strip_code_and_md(text)}
    return coerce_reply(obj, title, content, strict)


# -------------------------
# Agent wrapper (uses the shared adapter)
# -------------------------

@dataclass
class SimpleAgent:
    name: str
    system: str
    client: ModelClient

    def respond(
        self,
        conversation: List[Dict[str, str]],
        task: str,
        title: str,
        content: str,
        strict: bool,
    ) -> Dict[str, Any]:
        history_text = "\n".join(
            f'{m["role"]}: {m["content"]}' for m in conversation
        ) or "(empty)"

        human = (
            f"Task:\n{task}\n\nConversation so far:\n{history_text}\n\n"
            "Return ONLY one JSON object (no code fences, no markdown, no explanations). "
            "Keys: thought (string), message (non-empty, <=60 words, no code), "
            "data.tags (array of exactly 3 topical tags), "
            "data.summary (<=25 words, no ellipses), data.issues (array).\n"
            "Do not add extra text outside JSON."
        )
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": human},
        ]
        result = self.client.complete(messages)
        parsed = parse_and_coerce(result.text, title, content, strict)
        # attach token accounting for optional inspection
        parsed["_tokens"] = {
            "input": result.input_tokens,
            "output": result.output_tokens,
            "total": result.total_tokens,
        }
        return parsed
        
def planner_node(state: AgentState) -> Dict[str, Any]:
    print("--- NODE: Planner ---")
    planner_attempts = state.get("planner_attempts", 0) + 1
        # Test mode: force one invalid Planner attempt.
    # The next attempt runs normally and receives this error as feedback.
    if (
        os.environ.get("FORCE_PLANNER_INVALID") == "1"
        and planner_attempts == 1
    ):
        validation_message = (
            "There must be exactly 3 tags, and the summary "
            "must contain at most 25 words."
        )

        print("--- TEST: Forced Planner validation failure ---")
        print(validation_message)

        return {
            "planner_proposal": {},
            "reviewer_feedback": {
                "message": "Planner output failed validation.",
                "data": {
                    "tags": [],
                    "summary": "",
                    "issues": [validation_message],
                },
            },
            "planner_attempts": planner_attempts,
        }

    previous_feedback = state.get("reviewer_feedback", {})
    previous_issues = (
        previous_feedback
        .get("data", {})
        .get("issues", [])
    )

    correction_message = ""

    if previous_issues:
        correction_message = (
            "\nThe previous attempt failed validation. "
            "Fix this problem:\n"
            + "\n".join(previous_issues)
        )

    system_message = (
        "You are the Planner. Return exactly one JSON object with this structure: "
        '{"thought": "short explanation", '
        '"message": "short message", '
        '"data": {"tags": ["tag1", "tag2", "tag3"], '
        '"summary": "summary"}}. '
        "Tags must be strings between 3 and 30 characters. "
        "There must be exactly 3 tags. "
        "The summary must contain at most 25 words. "
        "Do not add markdown or extra text."
    )

    user_message = (
        f"Title: {state['title']}\n"
        f"Content: {state['content']}\n"
        f"Task: {state['task']}\n"
        f"{correction_message}"
    )

    result = state["llm"].complete(
        [
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]
    )

    try:
        raw_output = json.loads(
            extract_json_block(result.text)
        )

        raw_data = raw_output.get("data", {})

        validated_output = PlannerOutput.model_validate(raw_data)

        proposal = {
            "thought": str(
                raw_output.get("thought", "")
            ),
            "message": str(
                raw_output.get(
                    "message",
                    "Planner output validated."
                )
            ),
            "data": validated_output.model_dump(),
            "_tokens": {
                "input": result.input_tokens,
                "output": result.output_tokens,
                "total": result.total_tokens,
            },
        }

        return {
            "planner_proposal": proposal,
            "reviewer_feedback": {},
            "planner_attempts": planner_attempts,
        }

    except Exception as error:
        validation_message = str(error)

        print("--- Planner validation failed ---")
        print(validation_message)

        return {
            "planner_proposal": {},
            "reviewer_feedback": {
                "message": "Planner output failed validation.",
                "data": {
                    "tags": [],
                    "summary": "",
                    "issues": [validation_message],
                },
            },
             "planner_attempts": planner_attempts,
        }
    
def reviewer_node(state: AgentState) -> Dict[str, Any]:
    print("--- NODE: Reviewer ---")
    
        # Test mode for the Homework 2 correction-loop demonstration.
    if os.environ.get("FORCE_REVIEW_ISSUE") == "1":
        print("--- TEST: Reviewer forced an issue ---")

        return {
            "reviewer_feedback": {
                "message": "Forced issue for loop testing.",
                "data": {
                    "tags": [],
                    "summary": "",
                    "issues": ["Forced test issue"]
                }
            }
        }

    planner_proposal = state.get("planner_proposal", {})

    reviewer = SimpleAgent(
        name="Reviewer",
        system=(
            "Review the Planner proposal. Check that there are exactly 3 "
            "topical tags and that the summary has no more than 25 words. "
            "If there are problems, explain them in data.issues and provide "
            "corrected tags and summary."
        ),
        client=state["llm"],
    )

    conversation = [
        {
            "role": "Planner",
            "content": json.dumps(planner_proposal)
        }
    ]

    feedback = reviewer.respond(
        conversation=conversation,
        task=state["task"],
        title=state["title"],
        content=state["content"],
        strict=state["strict"],
    )

    return {
        "reviewer_feedback": feedback
    }  
def supervisor_node(state: AgentState) -> Dict[str, Any]:
    print("--- NODE: Supervisor ---")

    current_turn = state.get("turn_count", 0)

    return {
        "turn_count": current_turn + 1
    }


def router_logic(state: AgentState) -> str:
    turn_count = state.get("turn_count", 0)
    planner_proposal = state.get("planner_proposal")
    reviewer_feedback = state.get("reviewer_feedback")

    # Stop if the turn ceiling has been reached.
    turn_ceiling = state.get("turn_ceiling", 10)

    if turn_count >= turn_ceiling:
        return "end"

    # No Planner output yet: send the task to Planner.
    if not planner_proposal:
        return "planner"

    # Planner has run, but Reviewer has not run yet.
    if not reviewer_feedback:
        return "reviewer"

    # Reviewer found issues: loop back to Planner.
    issues = reviewer_feedback.get("data", {}).get("issues", [])

    if issues:
        return "planner"

    # Reviewer found no issues: finish.
    return "end" 
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        router_logic,
        {
            "planner": "planner",
            "reviewer": "reviewer",
            "end": END,
        },
    )

    graph.add_edge("planner", "supervisor")
    graph.add_edge("reviewer", "supervisor")

    return graph.compile()    
# -------------------------
# CLI entrypoint
# -------------------------

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--title",
        default="Diabetes Drug Trial"
    )

    ap.add_argument(
        "--content",
        default=(
            "A randomized clinical trial testing a new oral medication "
            "for type 2 diabetes in adults."
        )
    )

    ap.add_argument(
        "--email",
        default="student@example.com"
    )

    ap.add_argument(
        "--model",
        default=os.environ.get(
            "OLLAMA_MODEL",
            "qwen3:4b-instruct-2507-q4_K_M"
        )
    )

    ap.add_argument(
        "--base_url",
        default=os.environ.get(
            "OLLAMA_URL",
            "http://localhost:11434"
        )
    )

    ap.add_argument(
        "--temperature",
        type=float,
        default=0.0
    )

    ap.add_argument(
        "--strict",
        action="store_true"
    )
    ap.add_argument(
        "--input-file",
        default=None
    )

    ap.add_argument(
        "--turn-ceiling",
        type=int,
        default=10
    )

    args = ap.parse_args()
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        args.title = input_data["title"]
        args.content = input_data["content"]
        args.email = input_data.get("email", args.email)
        args.strict = input_data.get("strict", args.strict)

    try:
        client = ModelClient(
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
        )
    except Exception:
        print(
            "Failed to initialize model client. Is Ollama running and the model pulled?\n"
            "Try: `ollama serve` and `ollama pull qwen3:4b-instruct-2507-q4_K_M`.",
            file=sys.stderr,
        )
        raise

    task = (
        f'Given title "{args.title}" and content "{args.content}", '
        "produce exactly 3 topical tags and a summary of no more than "
        "25 words."
    )

    initial_state: AgentState = {
        "title": args.title,
        "content": args.content,
        "email": args.email,
        "strict": args.strict,
        "task": task,
        "llm": client,
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "turn_ceiling": args.turn_ceiling,
        "planner_attempts": 0,
    }

    graph = build_graph()

    print("\n=== Stateful Agent Graph ===")
    print(f"Model: {args.model}")
    print(f"Title: {args.title}")
    print("")

    final_state = initial_state

    for state in graph.stream(
        initial_state,
        stream_mode="values"
    ):
        final_state = state

        print(
            f"Turn count: {state.get('turn_count', 0)}"
        )

        if state.get("planner_proposal"):
            print("Planner proposal updated.")

        if state.get("reviewer_feedback"):
            print("Reviewer feedback updated.")

        print("")

    print("=== Final Graph State ===")
    print(
        json.dumps(
            {
                "planner_proposal": final_state.get(
                    "planner_proposal",
                    {}
                ),
                "reviewer_feedback": final_state.get(
                    "reviewer_feedback",
                    {}
                ),
                "turn_count": final_state.get(
                    "turn_count",
                    0
                ),
                "turn_ceiling": final_state.get(
                    "turn_ceiling",
    10
),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
