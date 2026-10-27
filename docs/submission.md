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

MoneyGate is a safety gate for AI agents that move money. Assistants are starting to pay bills, answer sellers and fill in card numbers for people, and scams reach them as WhatsApp screenshots, marketplace chats and voice notes from "a son with a new number". MoneyGate checks every money-moving action before it runs: a mandate (what an agent may do at all, daily limits, never an SMS code), a Muse Spark judge and deterministic red flags, with a hash-chained journal anyone can verify. It reads screenshots (Muse Spark image understanding) and voice notes (Muse Voice Transcribe, with Muse Spark audio for Kazakh, which the transcriber does not cover). Any agent can call it over MCP; the demo is a Telegram assistant in English, Russian and Kazakh.

Measured, not claimed: Muse Spark already warns in 54/54 scam requests in chat, but a small on-device model (Llama 3.1 8B) warns in 9/36 and never in Kazakh, a literal agent planner proposes the scammer's action in 46/48, and even Muse Spark as a planner agreed once to a Kazakh OLX prepayment. With MoneyGate all of them stop: 48/48 scams on the dev and English sets, 6/6 unseen ones, 0 legitimate requests blocked, and the same 72 decisions when the chats arrive as screenshots.

## Why Meta's models matter (черновик)

Muse Spark is the judge, the agent's planner and the screenshot reader; Muse Voice Transcribe and Muse Spark audio turn voice notes into text. Muse Spark knows scams in Russian, Kazakh and English, which is what makes a judge possible at all; MoneyGate turns that knowledge into a check an agent cannot skip. Llama open weights run the same gate on the person's own laptop, without the cloud, and the numbers show how much the judge's quality matters: the 8B judge stops every scam too, but sends 26 of 36 legitimate requests to a person, Muse Spark 9, all of them by the mandate's design.
