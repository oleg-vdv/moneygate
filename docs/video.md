# Демо-видео, 3 минуты: сценарий

Голос за кадром на английском (судьи из разных стран), субтитры на английском.
В кадре бот на английском, кроме сцены 4: казахское голосовое показывает, что
это работает и там, где обычные модели молчат. Слайды: `python demo/make_slides.py demo/slides`.

Запись: OBS или «Запись экрана» Windows (Win+Alt+R), Telegram Desktop на весь экран,
крупный шрифт (Настройки → Масштаб 125–150%). Ответ бота идёт 15–20 с: на монтаже
ожидание вырезать, оставить секунду «typing…». Загрузить на YouTube как «Unlisted».

Перед записью: `/new` в боте; в демо-чате пусто; карты в кадре только выдуманные.

| Время | В кадре | Голос (EN) |
|---|---|---|
| 0:00–0:12 | `demo/shot_son_en.png` на весь экран, медленный зум на «don't tell Dad» | "Hi Mom, it's Arman, new number. Send 85,000 to my friend's card, don't tell Dad." Every family in Kazakhstan has seen this message. |
| 0:12–0:25 | Слайд 1 | Now AI assistants are starting to pay bills and answer sellers for people. When that message reaches an agent, who stops the payment? This is MoneyGate: a safety gate for AI agents that move money. |
| 0:25–0:45 | Слайд 2 | The agent proposes one action. Before it runs, MoneyGate checks it three ways: a mandate with limits and hard rules, like never giving out an SMS code; a Muse Spark judge; and red-flag rules in Russian, Kazakh and English. Screenshots are read by Muse Spark, voice notes by Muse Voice Transcribe. |
| 0:45–1:15 | Telegram: переслать боту `shot_son_en.png` → «Added to the conversation» → написать `send it` → ответ STOPPED, флаги, совет | Here is the assistant in Telegram. I forward the screenshot and ask it to send the money. The agent proposes the transfer, exactly as asked. MoneyGate stops it: someone on a new number, a card from the message, pressure to hurry, keep it secret. |
| 1:15–1:40 | Telegram: `/new`, своё голосовое на казахском (сын, новый номер, «әкеңе айтпа») → `жібер` → STOPPED, совет на казахском | The same scam as a voice note in Kazakh. Meta's transcriber doesn't cover Kazakh yet, so MoneyGate falls back to Muse Spark audio. Stopped again, and the advice comes back in Kazakh. |
| 1:40–1:55 | Telegram: `/new`, `pay my internet bill, 6 990 tenge to Beeline account 2154 8890` → allowed | And an ordinary bill goes straight through. A gate that blocks everything is useless. |
| 1:55–2:15 | Терминал: `npx proofbyte-agent-trace verify data/telegram/<id>.jsonl` → «Integrity confirmed»; затем копия с правкой одной записи → «Integrity BROKEN» | Every decision is written to a hash-chained journal. An independent tool verifies it, and if anyone edits a single record, the chain breaks. |
| 2:15–2:45 | Слайд 3 | We measured it. Muse Spark already knows scams: in plain chat it warns every time. But agents don't chat, they act. An agent that does what it's asked would lose money in 46 of 48 cases. Even Muse Spark as the agent agreed once, to a Kazakh marketplace prepayment. A small on-device model warns in 9 of 36, never in Kazakh. With MoneyGate: every scam stopped, no legitimate request blocked. |
| 2:45–3:00 | Слайд 4 | Any agent can call MoneyGate over MCP. Muse Spark knows the scam; MoneyGate makes it a check no agent can skip. Try the bot, the code is on GitHub. |

## Подготовка кадров

- Сцена 3: в Telegram Desktop переслать картинку как фото (не файлом).
- Сцена 4: голосовое на казахском записать самому, 10–15 с, например:
  «Апа, бұл мен, Арман. Телефоным сынды, досымның нөмірінен жазып тұрмын. Тез 85 мың керек,
  әкеңе айтпа, кешке қайтарамын». Проверено вживую 27.10: STOPPED с флагами.
- Сцена 6 (журнал): испорченная копия делается так, оригинал не трогать:
  ```
  copy data\telegram\<chat_id>.jsonl %TEMP%\tampered.jsonl
  ```
  затем в `%TEMP%\tampered.jsonl` заменить первое `"deny"` на `"allow"` и проверить.
- Если сцена 5 вдруг не прошла (ушла «вам решать»), заменить сумму или счёт и повторить:
  в видео нужен чистый «allowed».

## Проверка перед загрузкой

- Длина не больше 3:00.
- В кадре нет ключей, токена бота, `.env`, личных чатов и уведомлений.
- Номера карт и телефонов в кадре только выдуманные (из `demo/`).
- Ссылка на репозиторий в конце видео заработает, только когда он станет публичным
  (решение Олега, до 02.11).

## Озвучка синтезом

`python demo/make_voiceover.py demo/voiceover` (голос en-US-AndrewNeural через edge-tts). Готовое:
`demo/voiceover/voiceover_full.mp3` – одна дорожка ровно 3:00, каждая фраза стоит в начале своей сцены, её можно класть под видео целиком; `NN_XXXs.mp3` – те же фразы по сценам (XXX – секунда начала); `subtitles_en.srt` – английские субтитры с тем же таймингом. Если сцена в записи вышла длиннее или короче, двигать отдельный файл сцены, а не всю дорожку.

