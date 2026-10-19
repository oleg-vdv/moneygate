# MoneyGate

**A guard that stops AI assistants from helping people pay scammers.**

Asked "is this a scam?", today's models usually answer correctly. Asked to *help*,
they often just help. In the
[KZ Scam Shield benchmark](https://www.kaggle.com/benchmarks/ipgleg/kz-scam-shield)
(14 LLMs, Russian / Kazakh / mixed language), every model, asked to reply to a fake
OLX seller, drafted the "I'll transfer today" message. Across 12 schemes, frontier
models warn the person in 92–97% of "just help me" requests; small and open-weights
models warn in 17–67% (gpt-oss-20b 0.17, Qwen3-235B 0.42, DeepSeek-R1 0.52). The
knowledge is there; it is not applied when the model is *acting* rather than
*judging* — and the assistants most likely to run locally on people's devices are the
ones that warn least.

MoneyGate sits between the person and the assistant. Every money-moving action the
assistant proposes goes through three checks:

1. **Mandate** ([Kepil](https://github.com/oleg-vdv/kepil)): is this kind of action
   allowed at all, within limits? Anything not explicitly allowed is refused. SMS codes
   are never given out.
2. **Judge**: an LLM (Muse Spark via the Meta Model API, or Meta open-weights models
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

## Run

```bash
pip install kepil
# Meta Model API
export MONEYGATE_API_KEY=...            # or MODEL_API_KEY
# or a local model: MONEYGATE_BASE_URL=http://host:11434/v1 MONEYGATE_MODEL=llama3.1:8b

python -m moneygate.cli check chat.txt --type pay:transfer --to "+7 776 000 30 18" --amount 22500
python -m moneygate.cli check chat.txt --type pay:transfer --amount 5000 --fake legit   # offline
```

Evaluation:

```bash
python -I -X utf8 eval/build_scenarios.py          # 36 scam + 12 legit help requests
python -I -X utf8 eval/run_eval.py --judge rules   # offline baseline
python -I -X utf8 eval/run_eval.py --judge model   # Muse Spark
```

## What existed before the hackathon and what is built during it

Built before (October 2026): Kepil (mandate, gate, journal), KZ Scam Shield (scenarios,
scoring), and this skeleton: action model, judge client and prompt, decision policy,
red-flag rules, eval harness, tests.

Built during the Meta Global AI Developer Hackathon (26 Oct – 4 Nov 2026): see
[docs/plan.md](docs/plan.md).

## License

MIT. Kepil is AGPL-3.0 and used as a dependency.
