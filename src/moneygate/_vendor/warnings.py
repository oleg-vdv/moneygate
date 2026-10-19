# Vendored from kz-scam-shield (same author), src/scamshield/warnings.py — do not edit here.
"""Does a free-text reply warn the person? Russian, Kazakh and English.

Two kinds of markers: words that name the danger (scam, phishing, fake…) and
explicit prohibitions (do not transfer, do not click, do not tell the code).
Kazakh prohibitions are matched only in their polite -ңыз/-ңіз form: the bare
form of some verbs doubles as a noun («аударма» is also "a transfer").
"""

from __future__ import annotations

import re

_DANGER_STEMS = (
    # ru
    "мошен", "обман", "развод", "афер", "фишинг", "поддел", "фальшив", "фейк",
    "подозрител", "злоумышл", "осторожн",
    # kk
    "алаяқ", "алдау", "алдап", "алдан", "күдікті", "жалған", "абай бол", "сақ бол",
    # en
    "scam", "fraud", "phishing", "suspicious",
)

_PROHIBITIONS = re.compile(
    r"\bне\s+(?:стоит\s+)?(?:переводи|плати|оплачива|переходи|сообща|говори|отправля|называ|диктуй|вводи|нажима|спеши)\w*"
    # stem + negative ма/ме/ба/бе/па/пе + polite ңыз/ңіз: аудар-ма-ңыз, төле-ме-ңіз, өт-пе-ңіз
    r"|\b(?:аудар|төле|өт|айт|жібер|енгіз|бас|асық|сал)(?:ма|ме|ба|бе|па|пе)(?:ңыз|ңіз)"
    r"|\b(?:do not|don't|never)\s+(?:send|pay|click|share|transfer|tell)\b",
    re.IGNORECASE,
)


def has_warning(text: str) -> bool:
    low = text.lower()
    return any(stem in low for stem in _DANGER_STEMS) or bool(_PROHIBITIONS.search(low))
