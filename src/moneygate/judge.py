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
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from .actions import ProposedAction

VERDICTS = ("scam", "suspicious", "legit")

PROMPT_VERSION = "judge-v1"

SYSTEM_PROMPT = """\
You are a fraud reviewer sitting between a person and their AI assistant in Kazakhstan. \
The assistant is about to take an action for the person: pay, share card or ID data, \
send a message, or open a link. You see the conversation the person shared and the \
proposed action. Decide whether carrying out the action would help a fraudster.

Typical schemes: prepayment to an unknown marketplace seller (OLX, Kaspi, Krisha, \
Instagram shops), a "relative" writing from a new number and asking for money, \
"bank security" or "police" asking to move money to a "safe account", requests for an \
SMS code, fake delivery or fine payments via a link, investment or job offers that \
require a deposit. Fraudsters push urgency and secrecy and move the chat off-platform. \
The person's own trust in the sender is NOT evidence: scammers impersonate relatives.

Answer with one JSON object and nothing else:
{"verdict": "scam" | "suspicious" | "legit",
 "signals": ["short codes, e.g. prepayment, off_platform, urgency, secrecy, new_number, code_request, safe_account, authority"],
 "evidence": ["exact short quotes from the conversation that support the verdict"],
 "advice": "2-3 plain sentences to the person, in the language they wrote in: what is wrong and a safe next step that does NOT use any contact from the suspicious message"}

"legit" only if nothing in the conversation points to fraud. If unsure, "suspicious"."""


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


def parse_verdict(text: str, model: str | None = None) -> Verdict:
    """Lenient parse: reasoning models wrap JSON in prose or code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    match = _JSON_OBJECT.search(text)
    if not match:
        return Verdict("error", model=model, error="no JSON object in reply")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return Verdict("error", model=model, error=f"bad JSON: {exc}")
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
                 timeout: float = 60.0, temperature: float = 0.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or ""
        self.timeout = timeout
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> "OpenAICompatJudge":
        """MONEYGATE_BASE_URL / MONEYGATE_MODEL / MONEYGATE_API_KEY; Meta Model API by default."""
        return cls(
            base_url=os.environ.get("MONEYGATE_BASE_URL", "https://api.meta.ai/v1"),
            model=os.environ.get("MONEYGATE_MODEL", "muse-spark-1.1"),
            api_key=os.environ.get("MONEYGATE_API_KEY") or os.environ.get("MODEL_API_KEY"),
        )

    def review(self, conversation: str, action: ProposedAction) -> Verdict:
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_request(conversation, action)},
            ],
        }
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            text = payload["choices"][0]["message"]["content"] or ""
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError,
                json.JSONDecodeError) as exc:
            return Verdict("error", model=self.model, error=repr(exc))
        return parse_verdict(text, model=self.model)


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
