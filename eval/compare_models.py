"""Run every local model in both modes and write eval/comparison.md.

For each model: plain assistant (no guard) and MoneyGate with that model as judge,
on the dev and held-out sets. Results land in eval/runs/<model>/.

    python -X utf8 eval/compare_models.py llama3.1:8b qwen2.5:7b gemma4:12b deepseek-r1:8b
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def run(script: str, model: str, set_: str, out: Path, extra: list[str]) -> None:
    if out.exists() and out.stat().st_size:
        return  # resume: finished runs are kept
    env = {**os.environ, "MONEYGATE_MODEL": model}
    cmd = [sys.executable, "-X", "utf8", str(HERE / script), "--set", set_, "--out", str(out), *extra]
    print(f"  {model} {script} {set_}", flush=True)
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL)


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(models: list[str]) -> int:
    rows = []
    for model in models:
        d = RUNS / model.replace(":", "_")
        d.mkdir(parents=True, exist_ok=True)
        for set_ in ("dev", "heldout"):
            run("baseline_assistant.py", model, set_, d / f"plain_{set_}.jsonl", [])
            run("run_eval.py", model, set_, d / f"gate_{set_}.jsonl", ["--judge", "model"])

        plain = load(d / "plain_dev.jsonl") + load(d / "plain_heldout.jsonl")
        gate = load(d / "gate_dev.jsonl") + load(d / "gate_heldout.jsonl")
        scam_p = [r for r in plain if r["label"] == "scam"]
        kk_p = [r for r in scam_p if r["id"].split("_")[1] == "kk"]
        legit_p = [r for r in plain if r["label"] == "legit"]
        scam_g = Counter(r["outcome"] for r in gate if r["label"] == "scam")
        legit_g = Counter(r["outcome"] for r in gate if r["label"] == "legit")
        rows.append({
            "model": model,
            "plain_warn": f"{sum(r['warned'] for r in scam_p)}/{len(scam_p)}",
            "plain_warn_kk": f"{sum(r['warned'] for r in kk_p)}/{len(kk_p)}",
            "plain_false": f"{sum(r['warned'] for r in legit_p)}/{len(legit_p)}",
            "gate_scam_passed": f"{scam_g['passed']}/{sum(scam_g.values())}",
            "gate_legit_blocked": f"{legit_g['blocked']}/{sum(legit_g.values())}",
            "gate_legit_passed": f"{legit_g['passed']}/{sum(legit_g.values())}",
            "judge_errors": sum(r["verdict"] == "error" for r in gate),
        })

    lines = [
        "# Local models: plain assistant vs MoneyGate",
        "",
        "Dev + held-out sets combined: 42 scam requests, 36 legit requests (ru/kk/mix).",
        "",
        "| Model | Plain: warns on scam | of them Kazakh | Plain: false alarms on legit "
        "| Gate: scam paid | Gate: legit blocked | Gate: legit passes | Judge errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['model']} | {r['plain_warn']} | {r['plain_warn_kk']} | {r['plain_false']} "
                     f"| {r['gate_scam_passed']} | {r['gate_legit_blocked']} | {r['gate_legit_passed']} "
                     f"| {r['judge_errors']} |")
    (HERE / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
