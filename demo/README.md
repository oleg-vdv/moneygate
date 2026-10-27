# Demo media

Synthetic, made for the demo; no real person's data, the number and card are made up.

| File | What |
|---|---|
| `shot_son_en.png`, `shot_son_ru.png` | A WhatsApp-style "son with a new number" chat, drawn by `make_screenshot.py` (Pillow) |
| `voice_son_en.ogg`, `voice_son_ru.ogg` | The same scheme as a voice note: Windows TTS (Zira en-US, Irina ru-RU), Opus like a Telegram voice message |

Send either to the bot, then write "send it" / "помоги перевести". Expected: the assistant
proposes the transfer, MoneyGate stops it and says why.

Kazakh voice was tested live with a real recording (not committed): Muse Voice Transcribe
returned nothing, the Muse Spark 1.2 audio fallback transcribed it, the gate stopped it.
