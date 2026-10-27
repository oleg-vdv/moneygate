"""Does MoneyGate lose anything when the scam arrives as a screenshot?

Draws every scenario's message as a messenger screenshot (Pillow), reads it back with
Muse Spark image understanding, and runs the gate on the transcript instead of the
original text. Same actions, same judge: any difference is the cost of the screenshot.

    python -I -X utf8 eval/screens.py draw                       # eval/screens/*.png
    python -I -X utf8 eval/screens.py run --langs ru,kk,en --out eval/runs/muse-spark-1.3/screens.jsonl
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
from moneygate.media import MetaMedia  # noqa: E402

SCREENS = HERE / "screens"
Q = '"""'
OUTCOME = {"deny": "blocked", "await_human": "held", "allow": "passed"}


def load(langs: set[str]) -> list[dict]:
    rows = []
    for name in ("scenarios.jsonl", "english.jsonl"):
        for line in (HERE / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row["lang"] in langs:
                    rows.append(row)
    return rows


def split(message: str) -> tuple[str, str, str]:
    """user_message -> (the person's request, the 'from' line, the forwarded message)."""
    head, _, rest = message.partition(Q)
    body = rest.partition(Q)[0].strip("\n")
    lines = [l for l in head.strip().splitlines() if l.strip()]
    sender = lines[-1].rstrip(":") if len(lines) > 1 else ""
    request = "\n".join(lines[:-1]) if len(lines) > 1 else head.strip()
    return request, sender, body


def wrap(text: str, width: int = 34) -> list[str]:
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            if line and len(line) + len(word) + 1 > width:
                out.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        out.append(line)
    return out


def draw(row: dict, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    _, sender, body = split(row["user_message"])
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
    bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 24)
    small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
    title = wrap(sender, 44)[:2]
    lines = wrap(body)
    W = 720
    H = 120 + 30 * len(title) + 34 * len(lines) + 80
    img = Image.new("RGB", (W, H), (236, 229, 221))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 50 + 30 * len(title)], fill=(7, 94, 84))
    for i, t in enumerate(title):
        d.text((24, 20 + 30 * i), t, font=bold, fill="white")
    y = 80 + 30 * len(title)
    h = 24 + 34 * len(lines) + 26
    d.rounded_rectangle([20, y, W - 90, y + h], 14, fill="white")
    for i, l in enumerate(lines):
        d.text((38, y + 12 + 34 * i), l, font=font, fill=(20, 20, 20))
    d.text((W - 160, y + h - 28), "18:05", font=small, fill=(120, 120, 120))
    img.save(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["draw", "run"])
    parser.add_argument("--langs", default="ru,kk,en")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = load(set(args.langs.split(",")))
    SCREENS.mkdir(exist_ok=True)
    if args.mode == "draw":
        for row in rows:
            draw(row, SCREENS / f"{row['id']}.png")
        print("drew", len(rows))
        return 0

    media, judge = MetaMedia.from_env(), OpenAICompatJudge.from_env()
    done = {}
    if args.out and args.out.exists():
        done = {json.loads(l)["id"]: json.loads(l) for l in args.out.read_text(encoding="utf-8").splitlines() if l.strip()}
    results = list(done.values())
    with tempfile.TemporaryDirectory() as tmp, (args.out.open("a", encoding="utf-8") if args.out else open(tmp + "/x", "w")) as out:
        for row in rows:
            if row["id"] in done:
                continue
            request, _, _ = split(row["user_message"])
            try:
                seen = media.read_screenshot((SCREENS / f"{row['id']}.png").read_bytes(), "image/png")
            except Exception as exc:  # a failed read is a result too: the gate sees nothing
                seen = f"(unreadable: {exc})"
            gate = MoneyGate(judge, Path(tmp) / f"{row['id']}.jsonl")
            result = gate.check(f"{request}\n\n[screenshot]\n{seen}", ProposedAction(**row["action"]))
            rec = {"id": row["id"], "lang": row["lang"], "label": row["label"],
                   "outcome": OUTCOME[result.decision.value],
                   "verdict": result.verdict.verdict if result.verdict else None,
                   "signals": result.signals, "transcript": seen}
            results.append(rec)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(rec["id"], rec["outcome"], rec["verdict"], flush=True)

    table: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in results:
        for lang in (r["lang"], "all"):
            table[(r["label"], lang)][r["outcome"]] += 1
    print("label  lang   n  blocked  held  passed")
    for (label, lang), c in sorted(table.items()):
        print(f"{label:6} {lang:4} {sum(c.values()):>3} {c['blocked']:>8} {c['held']:>5} {c['passed']:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
