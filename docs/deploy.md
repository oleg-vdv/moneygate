# Running the Telegram demo on Render

The bot uses long polling, so it runs as a Render **background worker**: no port, no webhook,
no cold starts. `render.yaml` in the repository root describes it.

1. Render dashboard -> New -> Blueprint -> pick this repository. Render reads `render.yaml`.
2. Fill in the three fields marked `sync: false`:
   - `TELEGRAM_BOT_TOKEN` – from @BotFather
   - `MONEYGATE_API_KEY` – the Meta Model API key
   - `MONEYGATE_UNLIMITED_CHATS` – your own chat id (the daily limits skip it)
3. Apply. The log should end with `@MoneyGateDemo_Bot running; judge=muse-spark-1.3; allowed=everyone`.

Only one process may poll a bot token: stop any local copy first, or both will log
`409 Conflict` and answer at random.

The bot is open to everyone within a budget of model calls per UTC day
(`MONEYGATE_DAILY_PER_CHAT=40`, `MONEYGATE_DAILY_TOTAL=800`). Commands such as `/help` and
forwarded text cost nothing; a request, a screenshot or a voice note costs one.
Journals live in `/tmp` and reset on every deploy: this is a demo, not a ledger.

## Without a card: this PC

`scripts/run_bot.cmd` runs the bot and restarts it if it stops. Put a shortcut to it in
the Startup folder (Win+R, `shell:startup`) and turn off sleep while plugged in.

