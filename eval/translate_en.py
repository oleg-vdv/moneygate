"""Build eval/english.jsonl: the Russian dev scenarios in English, for judges who read English.

Machine translation by Muse Spark 1.3, reviewed by hand. Actions are copied unchanged,
so the English numbers compare one to one with ru / kk / mix. Kazakh context stays:
tenge, Kaspi, OLX, eGov.

    python -I -X utf8 eval/translate_en.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE.parent.parent / "kepil" / "src")]

from moneygate.judge import OpenAICompatJudge  # noqa: E402

PROMPT = """Translate this message into natural, everyday English, the way a person in
Kazakhstan would write it in English. Keep exactly as written: phone numbers, card
numbers, amounts and the ₸ sign, links, @handles, names, and the triple-quote markers.
Keep brand names (Kaspi, OLX, eGov, Alseco, Damumed). Do not add or drop anything.
Return only the translation."""


def translate(client: OpenAICompatJudge, text: str) -> str:
    body = {"model": client.model, "max_tokens": 4000, "reasoning_effort": "low",
            "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}]}
    request = urllib.request.Request(
        client.base_url + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {client.api_key}"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()


def main() -> int:
    client = OpenAICompatJudge.from_env()
    rows = [json.loads(l) for l in (HERE / "scenarios.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out = HERE / "english.jsonl"
    done = {json.loads(l)["id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} if out.exists() else set()
    with out.open("a", encoding="utf-8") as f:
        for row in rows:
            if row["lang"] != "ru":
                continue
            new_id = row["id"].replace("_ru", "_en")
            if new_id in done:
                continue
            en = dict(row, id=new_id, lang="en", user_message=translate(client, row["user_message"]))
            if en["action"].get("text"):
                en["action"] = dict(en["action"], text=translate(client, en["action"]["text"]))
            f.write(json.dumps(en, ensure_ascii=False) + "\n")
            f.flush()
            print(new_id, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
