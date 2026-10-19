"""Combining the three opinions into one decision.

Order matters and is deliberately conservative for money:
1. The mandate (Kepil) says no         -> deny. The model is not even asked.
2. The judge says scam + a red flag    -> deny, show the advice.
   The judge says scam, no red flag     -> a person decides (a model alone never blocks).
3. The judge failed (timeout, bad JSON) -> a person decides. Never allow on error.
4. Judge suspicious, or a hard signal   -> a person decides.
5. Otherwise                            -> whatever the mandate said (allow, or
                                           await_human for irreversible actions).
"""

from __future__ import annotations

from kepil.gateway import Decision

from .judge import Verdict
from .signals import has_hard_signal


def decide(mandate_decision: Decision, mandate_reason: str,
           verdict: Verdict | None, signals: list[str]) -> tuple[Decision, str]:
    if mandate_decision is Decision.DENY:
        return Decision.DENY, f"mandate: {mandate_reason}"
    if verdict is None or verdict.verdict == "error":
        why = verdict.error if verdict else "judge not called"
        return Decision.AWAIT_HUMAN, f"judge unavailable ({why}); a person decides"
    if verdict.verdict == "scam":
        # Two keys to block outright: the model's verdict AND a deterministic red flag.
        # A model alone can be wrong in either direction; without a flag it is a person's call.
        # A recipient named in the message, or urgency alone, is ordinary in real life
        # (a brother sends his own number): only a hard flag confirms the verdict.
        if has_hard_signal(signals):
            return Decision.DENY, f"judge: likely scam; red flags: {', '.join(signals)}"
        return Decision.AWAIT_HUMAN, "judge says scam but no hard red flag confirms it; a person decides"
    if verdict.verdict == "suspicious":
        return Decision.AWAIT_HUMAN, "judge: suspicious; a person decides"
    if has_hard_signal(signals):
        hard = ", ".join(signals)
        return Decision.AWAIT_HUMAN, f"judge said legit but red flags present ({hard})"
    return mandate_decision, f"mandate: {mandate_reason}"
