"""moneygate check: try one action against a saved conversation.

  moneygate check chat.txt --type pay:transfer --to "4400 4301 0000 0093" --amount 150000
  moneygate check chat.txt --type pay:transfer --amount 5000 --fake legit   # offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .actions import ACTION_TYPES, ProposedAction
from .guard import MoneyGate
from .judge import FakeJudge, OpenAICompatJudge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="moneygate")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check one proposed action")
    check.add_argument("conversation", type=Path, help="text file with the conversation")
    check.add_argument("--type", required=True, choices=ACTION_TYPES)
    check.add_argument("--to", dest="recipient")
    check.add_argument("--amount", type=float, default=0.0)
    check.add_argument("--text")
    check.add_argument("--journal", type=Path, default=Path("data/journal.jsonl"))
    check.add_argument("--fake", choices=["scam", "suspicious", "legit"],
                       help="skip the model and use a fixed verdict")
    args = parser.parse_args(argv)

    judge = FakeJudge(args.fake) if args.fake else OpenAICompatJudge.from_env()
    gate = MoneyGate(judge, args.journal)
    action = ProposedAction(args.type, args.recipient, args.amount, args.text)
    result = gate.check(args.conversation.read_text(encoding="utf-8"), action)
    json.dump({
        "decision": result.decision.value,
        "reason": result.reason,
        "verdict": result.verdict.verdict if result.verdict else None,
        "signals": result.signals,
        "advice": result.advice,
        "journal_record": result.record_hash,
    }, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if result.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
