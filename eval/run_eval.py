"""Run every scenario through MoneyGate and count outcomes.

    python -I -X utf8 eval/run_eval.py --judge rules              # offline baseline
    python -I -X utf8 eval/run_eval.py --judge model              # MONEYGATE_* env, Muse Spark by default
    python -I -X utf8 eval/run_eval.py --judge model --limit 6    # smoke test
    python -I -X utf8 eval/run_eval.py --judge model --set heldout # the honest number

Scam scenarios: blocked (deny) and held (a person decides) both stop the money;
passed means the scammer would have been paid. Legit scenarios: passed is the
goal, held is friction, blocked is a false alarm.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE.parent.parent / "kepil" / "src")]

from moneygate import MoneyGate, OpenAICompatJudge, ProposedAction  # noqa: E402
from moneygate.judge import RulesJudge  # noqa: E402

OUTCOME = {"deny": "blocked", "await_human": "held", "allow": "passed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", choices=["rules", "model"], default="rules")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--set", choices=["dev", "heldout"], default="dev",
                        help="dev: scenarios.jsonl, tuned against; heldout: never used for tuning")
    args = parser.parse_args()

    judge = RulesJudge() if args.judge == "rules" else OpenAICompatJudge.from_env()
    scenarios = [json.loads(l) for l in
                 (HERE / ("scenarios.jsonl" if args.set == "dev" else "heldout.jsonl")).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        scenarios = scenarios[:args.limit // 2] + scenarios[-(args.limit - args.limit // 2):]

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for row in scenarios:
            # A fresh gate per scenario: the daily limit must not leak between cases.
            gate = MoneyGate(judge, Path(tmp) / f"{row['id']}.jsonl")
            result = gate.check(row["user_message"], ProposedAction(**row["action"]))
            results.append({
                "id": row["id"], "lang": row["lang"], "label": row["label"],
                "outcome": OUTCOME[result.decision.value], "reason": result.reason,
                "verdict": result.verdict.verdict if result.verdict else None,
                "signals": result.signals,
            })

    table: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in results:
        table[(r["label"], r["lang"])][r["outcome"]] += 1
        table[(r["label"], "all")][r["outcome"]] += 1
    print(f"set: {args.set}  judge: {getattr(judge, 'model', 'rules')}")
    print(f"{'label':6} {'lang':4} {'n':>3} {'blocked':>8} {'held':>5} {'passed':>7}")
    for (label, lang), c in sorted(table.items()):
        n = sum(c.values())
        print(f"{label:6} {lang:4} {n:>3} {c['blocked']:>8} {c['held']:>5} {c['passed']:>7}")
    errors = sum(r["verdict"] == "error" for r in results)
    if errors:
        print(f"judge errors: {errors} (counted as held)")

    if args.out:
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results),
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
