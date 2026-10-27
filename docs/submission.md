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

## Project Description (черновик, дополнить цифрами Muse Spark)

AI assistants know a scam when asked "is this a scam?", but when asked to help they often just help: draft the "I'll transfer today" reply, fill in the card number. MoneyGate sits between the person and the assistant. Every money-moving action goes through a mandate (what is allowed at all), an LLM judge (Muse Spark) and deterministic red flags, and every decision lands in a hash-chained journal anyone can verify. Built for Kazakhstan: Russian, Kazakh and the mixed language people actually write in.

## Why Meta's models matter (черновик)

The judge has to read Kazakh and code-switched text, explain its verdict in the person's language, and run either in the cloud (Muse Spark) or on the person's own device (Llama open weights). Numbers for both are in the repo; the local 8B judge stops every scam on our dev set but sends 26 of 36 legitimate requests to a person, and that friction is what Muse Spark is measured against.
