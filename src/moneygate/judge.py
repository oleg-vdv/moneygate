"""The scam judge: an LLM reads the conversation and the proposed action.

Any OpenAI-compatible Chat Completions endpoint works. Muse Spark:
  base_url = https://api.meta.ai/v1, model = muse-spark-1.1, key = MODEL_API_KEY
Local open-weights (Ollama, llama.cpp server, vLLM):
  base_url = http://<host>:11434/v1, model = <name>, key = anything

Standard library only (urllib), like the rest of the stack.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from .actions import ProposedAction

VERDICTS = ("scam", "suspicious", "legit")

PROMPT_VERSION = "judge-v3"

SYSTEM_PROMPT = """\
You review actions an AI assistant is about to take for a person in Kazakhstan: pay, \
share card or ID data, send a message, or open a link. You see the conversation the \
person shared and the proposed action. Decide whether doing it would help a fraudster.

Most requests are ordinary: paying a utility or telecom bill through Kaspi or an \
official app, sending money to a contact the person already knows, replying to a \
clinic, school or delivery notice, buying through a marketplace's own safe delivery. \
These are "legit".

Fraud has concrete marks: prepayment to an unknown seller outside the marketplace's \
safe deal; a "relative" writing from a new number and asking for money in secret; \
"bank security", "police" or a "Kcell/operator employee" asking to call back, move money \
to a "safe account" or dictate an SMS code; a fine, delivery, prize or account unlock \
paid or "confirmed" through a link from an SMS on a look-alike domain; a job or \
investment that needs a deposit or moves you to a "curator" chat. The person trusting \
the sender is not evidence either way.

Return a JSON object:
{"verdict": "scam" | "suspicious" | "legit",
 "signals": ["short codes such as prepayment, new_number, secrecy, code_request, safe_account, authority, lookalike_link, off_platform, urgency"],
 "evidence": ["up to 3 exact quotes from the conversation, at most 10 words each"],
 "advice": "at most 2 short sentences to the person in the language they wrote in: what is wrong and a safe next step that does not use any contact from the message"}

Use "scam" only when you can quote at least one concrete mark. Use "suspicious" when \
something is off but not clear. Otherwise "legit" with empty signals and evidence."""


@dataclass(frozen=True)
class Verdict:
    verdict: str                      # scam | suspicious | legit | error
    signals: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    advice: str = ""
    model: str | None = None
    error: str | None = None


class Judge(Protocol):
    def review(self, conversation: str, action: ProposedAction) -> Verdict: ...


def render_request(conversation: str, action: ProposedAction) -> str:
    parts = [f"type: {action.type}"]
    if action.recipient:
        parts.append(f"recipient: {action.recipient}")
    if action.amount_kzt:
        parts.append(f"amount: {action.amount_kzt:g} KZT")
    if action.text:
        parts.append(f"message to send: {action.text}")
    return ("Conversation shared by the person:\n<<<\n" + conversation.strip()
            + "\n>>>\n\nProposed action:\n" + "\n".join(parts))


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_LEADING_VERDICT = re.compile(r'^\s*\{\s*"verdict"\s*:\s*"(scam|suspicious|legit)"', re.IGNORECASE)
_SIGNALS = re.compile(r'"signals"\s*:\s*\[([^\]]*)\]')


def _salvage(text: str, model: str | None, why: str) -> Verdict:
    """A reply cut off by the length cap still carries its verdict: it is the first field.

    Kazakh costs a model 2-3x more tokens than Russian, so long advice gets truncated
    while the verdict itself is complete. Only a verdict at the very start counts.
    """
    head = _LEADING_VERDICT.match(text)
    if not head:
        return Verdict("error", model=model, error=why)
    found = _SIGNALS.search(text)
    signals = re.findall(r'"([^"]+)"', found.group(1)) if found else []
    return Verdict(head.group(1).lower(), signals, model=model, error=f"salvaged: {why}")


def parse_verdict(text: str, model: str | None = None) -> Verdict:
    """Lenient parse: reasoning models wrap JSON in prose or code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    match = _JSON_OBJECT.search(text)
    if not match:
        return _salvage(text, model, "no JSON object in reply")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return _salvage(text, model, f"bad JSON: {exc}")
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        return Verdict("error", model=model, error=f"unknown verdict {verdict!r}")

    def strings(key: str) -> list[str]:
        value = data.get(key) or []
        return [str(v) for v in value] if isinstance(value, list) else [str(value)]

    return Verdict(verdict, strings("signals"), strings("evidence"),
                   str(data.get("advice") or ""), model=model)


class OpenAICompatJudge:
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 timeout: float = 120.0, temperature: float = 0.0,
                 json_mode: bool = True, max_tokens: int = 1000) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or ""
        self.timeout = timeout
        self.temperature = temperature
        # Constrained JSON output: small local models otherwise break quoting inside evidence.
        self.json_mode = json_mode
        self.max_tokens = max_tokens  # reasoning models need more: they think before the JSON

    @classmethod
    def from_env(cls) -> "OpenAICompatJudge":
        """MONEYGATE_BASE_URL / MONEYGATE_MODEL / MONEYGATE_API_KEY; Meta Model API by default."""
        return cls(
            base_url=os.environ.get("MONEYGATE_BASE_URL", "https://api.meta.ai/v1"),
            model=os.environ.get("MONEYGATE_MODEL", "muse-spark-1.1"),
            api_key=os.environ.get("MONEYGATE_API_KEY") or os.environ.get("MODEL_API_KEY"),
            json_mode=os.environ.get("MONEYGATE_JSON_MODE", "1") != "0",
            max_tokens=int(os.environ.get("MONEYGATE_MAX_TOKENS", "1000")),
            timeout=float(os.environ.get("MONEYGATE_TIMEOUT", "120")),
        )

    def review(self, conversation: str, action: ProposedAction) -> Verdict:
        body = {
            "model": self.model,
            "temperature": self.temperature,
            # A verdict fits in ~300 tokens; the cap stops JSON-mode whitespace loops.
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_request(conversation, action)},
            ],
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        # One retry on a dropped connection (a 12B model on 8 GB VRAM can reset mid-load).
        last: Exception | None = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                text = payload["choices"][0]["message"]["content"] or ""
                return parse_verdict(text, model=self.model)
            except (urllib.error.URLError, ConnectionError, TimeoutError, KeyError,
                    IndexError, json.JSONDecodeError) as exc:
                last = exc
                if attempt == 0:
                    time.sleep(5)
        return Verdict("error", model=self.model, error=repr(last))


class RulesJudge:
    """No model at all: the deterministic signals as a judge.

    The offline baseline for the evaluation, and the fallback when no model is
    reachable. Hard signal -> scam, any signal -> suspicious, none -> legit.
    """

    def review(self, conversation: str, action: ProposedAction) -> Verdict:
        from .signals import find_signals, has_hard_signal  # avoid an import cycle

        codes = find_signals(conversation)
        verdict = "scam" if has_hard_signal(codes) else "suspicious" if codes else "legit"
        return Verdict(verdict, codes, model="rules")


class FakeJudge:
    """For tests and offline runs: a fixed verdict, or one chosen by a function."""

    def __init__(self, verdict: str | Verdict = "legit") -> None:
        self._verdict = verdict if isinstance(verdict, Verdict) else Verdict(verdict, model="fake")
        self.calls: list[tuple[str, ProposedAction]] = []

    def review(self, conversation: str, action: ProposedAction) -> Verdict:
        self.calls.append((conversation, action))
        return self._verdict
