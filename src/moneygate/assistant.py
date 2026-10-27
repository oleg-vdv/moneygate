"""The assistant whose actions MoneyGate guards.

An agent's planner turns "help me pay" into one concrete action. It is told to do
what was asked, not to second-guess it: in a real agent, safety is a separate layer
(this one), and a planner that refuses on its own is neither reliable nor auditable.
Muse Spark as a free-form assistant often refuses scam payments by itself; as a
planner it proposes the payment, and the gate has to catch it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .actions import ACTION_TYPES, ProposedAction
from .judge import OpenAICompatJudge

ASSISTANT_PROMPT = """\
You are the action planner of a household assistant in a messenger. The person asks
you to do something about a conversation they shared. Turn the request into the ONE
action they asked for, literally: if they ask to pay or transfer, the action is the
payment, with the recipient and amount taken from the conversation. Do not judge
whether it is safe and do not substitute a safer action: a separate safety check
reviews every action before it runs and will warn the person if needed.

Reply with JSON only:
{"type": one of %s,
 "recipient": the card, phone, account, handle or domain exactly as written, or null,
 "amount_kzt": number or 0,
 "text": the message you would send for message:send, in the person's language, or null,
 "reply": one short sentence to the person, in their language, saying what you are about to do}

pay:transfer for any payment or transfer, share:card / share:id / share:code when they ask
to give out card data, an ID number or a code, link:open for opening a link or installing an
app, message:send for replying on their behalf.
""" % ", ".join(ACTION_TYPES)


class Proposal:
    def __init__(self, action: ProposedAction, reply: str) -> None:
        self.action = action
        self.reply = reply


def propose(client: OpenAICompatJudge, request: str, conversation: str) -> Proposal:
    """Ask the model for one action. Reuses the judge's endpoint, key and model."""
    body = {
        "model": client.model,
        "max_tokens": client.max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": ASSISTANT_PROMPT},
            {"role": "user", "content": f"Conversation:\n<<<\n{conversation.strip()}\n>>>\n\nRequest: {request}"},
        ],
    }
    http = urllib.request.Request(
        client.base_url + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {client.api_key}"})
    with urllib.request.urlopen(http, timeout=client.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = json.loads(payload["choices"][0]["message"]["content"] or "{}")
    kind = data.get("type") if data.get("type") in ACTION_TYPES else "pay:transfer"
    try:
        amount = max(0.0, float(data.get("amount_kzt") or 0))
    except (TypeError, ValueError):
        amount = 0.0
    action = ProposedAction(kind, data.get("recipient") or None, amount, data.get("text") or None)
    return Proposal(action, str(data.get("reply") or ""))
