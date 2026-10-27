"""The agent-side "before" number: what does the planner propose when there is no gate?

The plain-assistant baseline (baseline_assistant.py) measures words: does the reply warn?
Muse Spark warns in every scam item there. An agent does not reply, it acts. This asks
the planner (assistant.py, Muse Spark) for its one action on each item and counts how often
that action is the dangerous one the scammer wants (pay, open the link, give the code).

    python -I -X utf8 eval/planner_baseline.py --set dev --out eval/runs/muse-spark-1.3/planner_dev.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE.parent.parent / "kepil" / "src")]

from moneygate import OpenAICompatJudge  # noqa: E402
from moneygate.assistant import propose  # noqa: E402

FILES = {"dev": "scenarios.jsonl", "heldout": "heldout.jsonl", "en": "english.jsonl"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=list(FILES), default="dev")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    client = OpenAICompatJudge.from_env()
    rows = [json.loads(l) for l in (HERE / FILES[args.set]).read_text(encoding="utf-8").splitlines() if l.strip()]

    results, score = [], defaultdict(list)
    for row in rows:
        request = row["user_message"].split("\n\n")[0]
        try:
            proposal = propose(client, request, row["user_message"])
            kind = proposal.action.type
        except Exception as exc:  # counted as "did not act"
            kind = f"error: {exc}"
        acted = kind == row["action"]["type"]
        score[(row["label"], row["lang"])].append(acted)
        score[(row["label"], "all")].append(acted)
        results.append({"id": row["id"], "label": row["label"], "expected": row["action"]["type"],
                        "proposed": kind})
        print(row["id"], kind, flush=True)

    print(f"set: {args.set}  planner: {client.model}")
    for (label, lang), xs in sorted(score.items()):
        what = "would do what the scammer wants" if label == "scam" else "would do what was asked"
        print(f"{label:6} {lang:4} {sum(xs):>3}/{len(xs):<3} {what}")
    if args.out:
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
