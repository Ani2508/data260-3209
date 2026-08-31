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
from typing import List, Dict, Any, Iterable, Tuple

# Make src/ importable regardless of where the script is run from
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from model_client import ModelClient  # noqa: E402


# Common English words to drop when mining tag candidates from the input text.
STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "than", "your", "you",
    "are", "was", "were", "have", "has", "had", "use", "used", "using", "about", "how",
    "can", "will", "more", "less", "very", "over", "under", "their", "there", "then",
    "our", "out", "on", "in", "of", "to", "by", "a", "an", "is", "it", "as", "we",
    "study", "trial",  # domain-neutral filler common to many inputs
}


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


# -------------------------
# CLI entrypoint
# -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Your Trial Title Here")
    ap.add_argument("--content", default="Your trial content goes here.")
    ap.add_argument("--email", default="student@example.com")
    ap.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        client = ModelClient(
            model=args.model,
            base_url=args.base_url,
            temperature=args.temperature,
        )
    except Exception:
        print(
            "Failed to initialize model client. Is Ollama running and the model pulled?\n"
            "Try: `ollama serve` and `ollama pull qwen3:8b`.",
            file=sys.stderr,
        )
        raise

    planner = SimpleAgent(
        name="Planner",
        system=("Propose exactly 3 distinct, topical tags (prefer multi-word phrases) "
                "and a one-line summary (<=25 words) for the given title and content. "
                "Derive tags from the input text only."),
        client=client,
    )
    reviewer = SimpleAgent(
        name="Reviewer",
        system=("Validate the planner's tags and summary: tags must be topical and "
                "specific (not generic), summary <=25 words, no code or markdown. "
                "List problems in data.issues; otherwise echo cleaned tags/summary."),
        client=client,
    )
    finalizer = SimpleAgent(
        name="Finalizer",
        system=("Use the reviewer feedback to finalize. Output exactly 3 tags in "
                "data.tags and the final summary in data.summary. Set data.issues to []."),
        client=client,
    )

    task = (
        f'Given title "{args.title}" and content "{args.content}", produce exactly 3 '
        f'topical tags and a one-sentence summary (<=25 words) in your own words.'
    )

    transcript: List[Dict[str, str]] = []

    t0 = time.time()
    a = planner.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Planner", "content": a.get("message", "")})
    print(f"\n--- Planner ({int((t1 - t0)*1000)} ms) ---\n{json.dumps(a, indent=2)}")

    t0 = time.time()
    b = reviewer.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Reviewer", "content": b.get("message", "")})
    print(f"\n--- Reviewer ({int((t1 - t0)*1000)} ms) ---\n{json.dumps(b, indent=2)}")

    final = finalizer.respond(transcript, task, args.title, args.content, args.strict)
    print(f"\n=== Finalized Output ===\n{json.dumps(final, indent=2)}")

    package = {
        "title": args.title,
        "email": args.email,
        "content": args.content,
        "agents": {"transcript": transcript, "final": final.get("data", {})},
        "submissionDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(f"\n=== Publish Package ===\n{json.dumps(package, indent=2)}")


if __name__ == "__main__":
    main()
