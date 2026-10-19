"""MoneyGate: one call per proposed action, one journal record per decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from kepil.gateway import ActionGateway, ActionRequest, Decision
from kepil.journal import Journal
from kepil.mandate import Mandate

from .actions import ProposedAction
from .judge import PROMPT_VERSION, Judge, Verdict
from .policy import decide
from .signals import find_signals


def family_mandate(daily_limit_kzt: float = 50_000, days: int = 365) -> Mandate:
    """A household assistant: may pay small amounts, never gives out codes.

    Card and ID data and opening links always go to a person. Payments above
    the remaining daily limit go to a person too (handled in MoneyGate).
    """
    now = datetime.now()
    return Mandate(
        mandate_id="family-default",
        agent_id="household-assistant",
        order_id="household",
        principal={"role": "family"},
        allowed_actions=["pay:transfer", "share:card", "share:id", "message:send", "link:open"],
        allowed_systems=["*"],
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=days),
        human_confirmation_required=["share:card", "share:id", "link:open"],
        forbidden_actions=["share:code"],
        limits={"amount_kzt": daily_limit_kzt},
    )


@dataclass
class GuardResult:
    decision: Decision
    reason: str
    verdict: Verdict | None
    signals: list[str] = field(default_factory=list)
    record_hash: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW

    @property
    def advice(self) -> str:
        return self.verdict.advice if self.verdict else ""


class MoneyGate:
    def __init__(self, judge: Judge, journal_path: str | Path,
                 mandate: Mandate | None = None) -> None:
        self.judge = judge
        self.mandate = mandate or family_mandate()
        self.journal = Journal(journal_path)
        self._gateway = ActionGateway(self.journal, passport_is_active=lambda _: True)

    def check(self, conversation: str, action: ProposedAction) -> GuardResult:
        # The amount is not passed to Kepil here: Kepil would spend the limit even
        # if the judge then blocks the payment. MoneyGate spends it only on allow.
        request = ActionRequest(action=action.type, system=action.masked_recipient(),
                                payload_ref=action.ref())
        mandate_decision, mandate_reason = self._gateway.check(self.mandate, request)

        signals = find_signals(conversation)
        verdict: Verdict | None = None
        if mandate_decision is not Decision.DENY:
            verdict = self.judge.review(conversation, action)

        decision, reason = decide(mandate_decision, mandate_reason, verdict, signals)

        if decision is Decision.ALLOW and action.amount_kzt:
            if action.amount_kzt > self.mandate.remaining("amount_kzt"):
                decision, reason = Decision.AWAIT_HUMAN, "over the remaining daily limit; a person decides"
            else:
                self.mandate.spend("amount_kzt", action.amount_kzt)

        record = self._gateway.record(
            self.mandate, request, decision, reason,
            prompt_version=PROMPT_VERSION,
            # Evidence quotes can hold card numbers and names: only codes go to the journal.
            model={"name": verdict.model if verdict else None,
                   "verdict": verdict.verdict if verdict else None,
                   "signals": sorted(set(signals) | set(verdict.signals if verdict else []))},
        )
        return GuardResult(decision, reason, verdict, signals, record["hash"])
