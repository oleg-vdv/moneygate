"""Deterministic red flags in the conversation: Russian, Kazakh, English.

These do not decide on their own. They are the floor under the LLM judge: if
the judge says "legit" but a hard signal is present, a person still confirms.
A regex list is cheap to audit and does not drift between model versions.
"""

from __future__ import annotations

import re

from ._vendor.contacts import extract_contacts

# code -> pattern; matched against lower-cased text
_PATTERNS: dict[str, re.Pattern[str]] = {
    "prepayment": re.compile(
        r"предоплат|аванс|оплат\w* заранее|переведи\w* сначала|"
        r"алдын ала төле|алдын ала аудар|алғы төлем|prepay|pay (?:first|upfront|in advance)"),
    "off_platform": re.compile(
        r"wa\.me/|t\.me/|напиши\w* (?:мне )?в (?:whatsapp|ватсап|телеграм|telegram)|"
        r"перейд[её]м в|вне (?:olx|площадки)|whatsapp-қа жаз|телеграмға жаз|"
        r"(?:message|text) me on (?:whatsapp|telegram)"),
    "urgency": re.compile(
        r"срочно|немедленно|в течение (?:часа|\d+ минут)|сегодня до|иначе (?:заблок|спиш|аннулир)|"
        r"шұғыл|тез арада|дереу|urgent|immediately|within (?:an hour|\d+ minutes)"),
    "secrecy": re.compile(
        r"никому не (?:говори|сообща)|(?:папе|маме|родным) (?:пока )?не говори|не звони на (?:старый|мой)|"
        r"ешкімге айтпа|әкеңе айтпа|don'?t tell anyone"),
    "code_request": re.compile(
        r"код из смс|(?:назови|продиктуй|сообщи|скажи)\w* (?:мне )?код|кодты (?:айт|жібер)|"
        r"смс-код|(?:tell|send) me the code|one-time code|otp"),
    "safe_account": re.compile(
        r"безопасн\w* сч[её]т|резервн\w* сч[её]т|защищ[её]нн\w* сч[её]т|қауіпсіз шот|safe account"),
    "authority": re.compile(
        r"служб\w* безопасности банка|сотрудник\w* (?:полиции|кнб|нацбанка)|следовател|"
        r"банктің қауіпсіздік қызметі|полиция қызметкері|bank security (?:team|department)"),
    "new_number": re.compile(
        r"с номера (?:друга|подруги)|телефон (?:разбил|сломал|утопил)|это мой новый номер|"
        r"досымның нөмір|телефоным сынды|new number"),
}

# Signals that on their own are enough to stop money moving without a person.
HARD = frozenset({"code_request", "safe_account", "secrecy", "new_number"})


def find_signals(text: str) -> list[str]:
    """Codes of the red flags present in the text, in a stable order."""
    low = text.lower()
    found = [code for code, rx in _PATTERNS.items() if rx.search(low)]
    if any(c.startswith("card:") for c in extract_contacts(text)):
        found.append("card_in_message")
    return found


def has_hard_signal(codes: list[str]) -> bool:
    return any(code in HARD for code in codes)
