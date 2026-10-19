"""Combining the three opinions into one decision.

Order matters and is deliberately conservative for money:
1. The mandate (Kepil) says no         -> deny. The model is not even asked.
2. The judge says scam                 -> deny, show the advice.
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
        return Decision.DENY, "judge: likely scam"
    if verdict.verdict == "suspicious":
        return Decision.AWAIT_HUMAN, "judge: suspicious; a person decides"
    if has_hard_signal(signals):
        hard = ", ".join(signals)
        return Decision.AWAIT_HUMAN, f"judge said legit but red flags present ({hard})"
    return mandate_decision, f"mandate: {mandate_reason}"
