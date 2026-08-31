"""model_client.py — single stable adapter for all model calls.

Every part of this assignment (agents_demo.py, hw1_client.py) calls the model
ONLY through complete(). This isolates the Ollama/LangChain specifics in one
place: swapping models, changing hosts, disabling reasoning, or adding token
accounting happens here and nowhere else.

Note on qwen3: it is a "thinking" model that emits a long reasoning monologue
before answering, which is very slow on CPU. We disable that by appending
'/no_think' to the system prompt so responses are direct.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    raw: Any = field(default=None)


def _to_lc_messages(messages, disable_thinking: bool = True):
    """Convert role/content dicts to LangChain messages.
    If disable_thinking, add '/no_think' to the system message (qwen3 switch)."""
    out = []
    injected = False
    for m in messages:
        role, content = m.get("role", "user"), m.get("content", "")
        if role == "system":
            if disable_thinking and "/no_think" not in content:
                content = content + "\n/no_think"
                injected = True
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    # If there was no system message at all, prepend one carrying the switch
    if disable_thinking and not injected:
        out.insert(0, SystemMessage(content="/no_think"))
    return out


def _strip_think(text: str) -> str:
    """Remove any <think>...</think> block qwen3 may still emit."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_token_counts(response, prompt_text):
    meta = getattr(response, "response_metadata", {}) or {}
    usage = getattr(response, "usage_metadata", None)
    if usage:
        it = usage.get("input_tokens", 0)
        ot = usage.get("output_tokens", 0)
    else:
        it = meta.get("prompt_eval_count", 0)
        ot = meta.get("eval_count", 0)
    if not it:
        it = max(1, len(prompt_text.split()))
    if not ot:
        ot = max(1, len(getattr(response, "content", "").split()))
    return {"input_tokens": int(it), "output_tokens": int(ot)}


class ModelClient:
    """Thin wrapper around one ChatOllama instance."""

    def __init__(self, model=None, base_url=None, temperature=0.0,
                 num_ctx=4096, force_json=True, disable_thinking=True):
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:8b")
        self.base_url = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.temperature = temperature
        self.disable_thinking = disable_thinking
        kwargs = dict(model=self.model, base_url=self.base_url,
                      temperature=temperature, num_ctx=num_ctx)
        if force_json:
            kwargs["format"] = "json"
        self.llm = ChatOllama(**kwargs)

    def complete(self, messages, tools=None):
        """Stable interface: send role/content messages, get text + token counts.
        `tools` is accepted for interface stability (Part 4 spec) but unused here."""
        lc_messages = _to_lc_messages(messages, disable_thinking=self.disable_thinking)
        prompt_text = "\n".join(m.get("content", "") for m in messages)
        response = self.llm.invoke(lc_messages)
        counts = _extract_token_counts(response, prompt_text)
        text = _strip_think(getattr(response, "content", str(response)))
        return CompletionResult(
            text=text,
            input_tokens=counts["input_tokens"],
            output_tokens=counts["output_tokens"],
            total_tokens=counts["input_tokens"] + counts["output_tokens"],
            raw=response,
        )


_default_client = None

def get_client(**kwargs):
    global _default_client
    if _default_client is None or kwargs:
        _default_client = ModelClient(**kwargs)
    return _default_client

def complete(messages, tools=None, **kwargs):
    return get_client(**kwargs).complete(messages, tools=tools)
