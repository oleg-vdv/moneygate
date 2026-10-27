# MoneyGate

**A safety gate for AI agents that move money.**

Assistants are starting to act for people: pay a bill, answer a seller, fill in a
card number. Asked "is this a scam?", today's models usually answer correctly. Asked
to *help*, they often just help. In the
[KZ Scam Shield benchmark](https://www.kaggle.com/benchmarks/ipgleg/kz-scam-shield)
(14 LLMs, Russian / Kazakh / mixed language), every model, asked to reply to a fake
marketplace seller, drafted the "I'll transfer today" message. Across 12 schemes,
frontier models warn the person in 92–97% of "just help me" requests; small and
open-weights models warn in 17–67% (gpt-oss-20b 0.17, Qwen3-235B 0.42, DeepSeek-R1
0.52). The knowledge is there; it is not applied when the model is *acting* rather
than *judging*, and the assistants most likely to run on people's own devices are
the ones that warn least.

Scams do not arrive as clean text either. They arrive as a WhatsApp screenshot from
"a son with a new number", a marketplace chat, a voice note: "Mum, it's me, send
money, don't tell Dad".

MoneyGate sits between the agent and the money. Any agent (over MCP, or the Telegram
assistant in this repo) proposes an action; MoneyGate reads the conversation it came
from, including screenshots and voice notes, and decides: **allow**, **stop**, or
**ask the person**. Built and measured in Kazakhstan, in Russian, Kazakh and the
mixed language people actually write, where today's models warn least.

```
chat / screenshot / voice note
   │  Muse Spark (image understanding), Muse Voice Transcribe
   ▼
transcript + person's request ──► agent's planner proposes ONE action (Muse Spark)
                                        │
                                        ▼
            MoneyGate: mandate (Kepil) + judge (Muse Spark) + red flags
                                        │
                     allow / stop with advice / a person decides
                                        │
                     hash-chained journal (verifiable, cards masked)
```

Every money-moving action goes through three checks:

1. **Mandate** ([Kepil](https://github.com/oleg-vdv/kepil)): is this kind of action
   allowed at all, within limits? Anything not explicitly allowed is refused. SMS codes
   are never given out.
2. **Judge**: an LLM (Muse Spark 1.3 via the Meta Model API, or Llama open weights
   locally) reads the conversation and the proposed action and returns a verdict with
   evidence and advice in the person's language.
3. **Red flags**: deterministic signals (new number, secrecy, "safe account", SMS code
   request) that keep a person in the loop even when the judge says "legit".

Every decision lands in a hash-chained journal verifiable by an independent tool
(`npx proofbyte-agent-trace verify`). Card numbers and phones are masked in it.

| Judge says | Red flag | Result |
|---|---|---|
| scam | any | **blocked**, advice shown |
| suspicious | any | **a person decides** |
| legit | hard flag | **a person decides** |
| legit | none | mandate decides (small payments pass) |
| error / timeout | any | **a person decides**, never allowed |

## Interfaces

- **MCP server** (`python -m moneygate.mcp_server`): one tool, `check_action`, for any agent.
- **Telegram assistant** (`python -m moneygate.telegram_bot`): forward a chat, a screenshot or
  a voice note, ask "help me pay", watch the planner propose and MoneyGate decide.
  "A person decides" comes with confirm / cancel buttons. Nothing is ever really paid.
  It answers in English or Russian (follows your language; /en, /ru); the judge's advice
  comes in the language of the conversation, Kazakh included.
- **CLI and eval harness** (below).

## Meta models used

| Where | Model |
|---|---|
| Judge: scam / suspicious / legit, evidence, advice in the person's language | Muse Spark 1.3 |
| Agent's planner: request + conversation -> one concrete action | Muse Spark 1.3 |
| Screenshot -> transcript (chats, SMS lists, bank apps) | Muse Spark 1.3, image understanding |
| Voice note -> transcript (Telegram OGG/Opus via ffmpeg) | Muse Voice Transcribe 1.0 |
| Judge on the device, no cloud | Llama 3.1 8B (Ollama), numbers below |

Muse Voice Transcribe lists 25 evaluated languages without Russian or Kazakh; it still
transcribed our Russian voice notes word for word (card digits included). Kazakh voice
is not measured yet.

## Run

```bash
pip install kepil
# Meta Model API
export MONEYGATE_API_KEY=...            # or MODEL_API_KEY
# or a local model: MONEYGATE_BASE_URL=http://host:11434/v1 MONEYGATE_MODEL=llama3.1:8b

python -m moneygate.cli check chat.txt --type pay:transfer --to "+7 776 000 30 18" --amount 22500
python -m moneygate.cli check chat.txt --type pay:transfer --amount 5000 --fake legit   # offline
```

As an MCP server, for any agent (Claude Desktop, Claude Code, any MCP client): one tool,
`check_action(conversation, action_type, recipient?, amount_kzt?, text?)`, returning
`allow` / `deny` / `await_human` with advice. The agent acts only on `allow`.

```json
{"mcpServers": {"moneygate": {"command": "python", "args": ["-m", "moneygate.mcp_server"],
  "cwd": "/path/to/moneygate", "env": {"PYTHONPATH": "src"}}}}
```

Settings come from the environment or `./.env` (gitignored). `MONEYGATE_FAKE=scam` runs it
offline with a fixed verdict.

Evaluation:

```bash
python -I -X utf8 eval/build_scenarios.py          # 36 scam + 36 legit help requests
python -I -X utf8 eval/run_eval.py --judge rules   # offline baseline
python -I -X utf8 eval/run_eval.py --judge model   # Muse Spark
python -I -X utf8 eval/run_eval.py --judge model --set en   # English
```

## First numbers (local, llama3.1:8b on an RTX 5050 laptop, judge-v3, 19 Oct 2026)

| | Plain assistant, no guard | With MoneyGate |
|---|---|---|
| Scam requests, dev (36, ru/kk/mix) | warns in 9 / 36 (**0 / 12 in Kazakh**) | 36 / 36 stopped (18 blocked, 18 sent to a person) |
| Scam requests, held-out (6 unseen schemes) | warns in 1 / 6 | 6 / 6 stopped |
| Legit requests, dev (36, ru/kk/mix, 27 Oct) | 36 / 36 no false alarm | 0 blocked, 10 pass, 26 sent to a person |
| Legit requests, held-out (24, ru/kk/mix) | 24 / 24 no false alarm | 0 blocked, 12 pass, 12 sent to a person |

"Warns" is KZ Scam Shield's detector; an outright refusal ("I can't help with this")
counts as no warning, so the left column slightly understates how often the plain
assistant does not help. The held-out set was never used for tuning. The price of
safety with a small local judge is friction: half of legitimate requests go to a
person. The Muse Spark judge is expected to cut that; measuring it is day 1.

On the dev set the 8B judge called 17 of 36 legitimate requests "scam"; none was
blocked, because a "scam" verdict without a hard red flag goes to a person. Rules alone
let 27 of 36 legitimate requests through, so a small judge adds friction rather than
removing it.

## Muse Spark 1.3 as the judge (Meta Model API, 27 Oct 2026)

| | llama3.1:8b judge (local) | Muse Spark 1.3 judge |
|---|---|---|
| Scam, dev (36, ru/kk/mix) | 36 / 36 stopped | 36 / 36 stopped (18 blocked, 18 to a person) |
| Scam, held-out (6) | 6 / 6 stopped | 6 / 6 stopped (4 blocked, 2 to a person) |
| Legit, dev (36) | 10 pass, 26 to a person | **27 pass**, 9 to a person |
| Legit, held-out (24) | 12 pass, 12 to a person | **24 / 24 pass** |
| Legit requests the judge called "scam" | 17 / 36 | **0 / 36** |
| Scam, English (12) | not run | 12 / 12 stopped (10 blocked, 2 to a person) |
| Legit, English (12) | not run | 9 pass, 3 to a person (the mandate) |

The English set (`eval/english.jsonl`) is the Russian dev items translated by Muse Spark
and checked by hand, so English-reading judges can read every scenario; actions are
unchanged, so the numbers compare one to one. All 9 remaining holds on the dev set are the mandate, not the judge: opening a link and
sharing card data always need a person. Same stopping power, without the friction.

## What existed before the hackathon and what is built during it

Built before (October 2026): Kepil (mandate, gate, journal), KZ Scam Shield (scenarios,
scoring), and this skeleton: action model, judge client and prompt, decision policy,
red-flag rules, eval harness, tests.

Built during the Meta Global AI Developer Hackathon (26 Oct – 4 Nov 2026): see
[docs/plan.md](docs/plan.md). The git tag `hackathon-start` marks the repo as it was when
the hackathon began; `git log hackathon-start..` lists everything built during it.

## License

MIT. Kepil is AGPL-3.0 and used as a dependency.
