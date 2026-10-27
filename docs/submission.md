# Submission form (Cerebral Valley), черновик

Форма: cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit. Срок: 04.11 21:00 ET (05.11 06:00 Алматы). Отправляет Олег, в последний день, когда есть репозиторий и видео. Поля прочитаны 27.10.

| Поле | Что ставим |
|---|---|
| Team Name * | MoneyGate |
| Team Members | Oleg Vdovin (ipgleg), один |
| Track * | Indie Developer Track |
| Problem statement * | Build for Your World (второй вариант: Push the Frontier) |
| Most Viral Track: ссылка на пост в X | по желанию; пост в X публикует Олег |
| Project Description | ниже |
| Public GitHub Repository | нужен публичный репозиторий; пушит Олег или по его «да» |
| 3-Minute Demo Video | YouTube, до 3 минут |
| Use of Meta products | Muse Spark через Meta Model API как судья; Llama 3.1 8B локально как открытая альтернатива; цифры обоих |
| Why Meta's models matter | ниже |
| Feedback on Meta products | заполнить по опыту за неделю |
| Feedback on partner technologies | если использовали Fireworks / Modal / Baseten |
| Согласие на использование материалов | галочка, ставит Олег |

## Project Description (черновик)

MoneyGate is a safety gate for AI agents that move money. Assistants are starting to pay bills and answer sellers for people, and models that recognise a scam when asked "is this a scam?" still help when asked to help. MoneyGate checks every money-moving action before it runs: a mandate (what the agent may do at all), a Muse Spark judge and deterministic red flags, with a hash-chained journal anyone can verify. Scams arrive as screenshots and voice notes, so MoneyGate reads those too (Muse Spark image understanding, Muse Voice Transcribe). Any agent can use it over MCP; the demo is a Telegram assistant. Measured in Russian, Kazakh and mixed language: Muse Spark stops 36/36 scams on the dev set and 6/6 unseen ones, and lets 24/24 unseen legitimate requests through, where a local 8B judge sent half of them to a person.

## Why Meta's models matter (черновик)

The judge has to read Kazakh and code-switched text, explain its verdict in the person's language, and run either in the cloud (Muse Spark) or on the person's own device (Llama open weights). Numbers for both are in the repo; the local 8B judge stops every scam on our dev set but sends 26 of 36 legitimate requests to a person, and that friction is what Muse Spark is measured against.
