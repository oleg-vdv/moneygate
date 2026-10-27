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
        r"шұғыл|тез арада|дереу|urgent|immediately|within (?:an hour|\d+ minutes|\d+ hours)|"
        r"before (?:23:59|the end of the day)|decide quickly|otherwise (?:\w+ ){0,3}(?:blocked|confiscated|returned)|"
        r"\bтез [\d\s]+ ?мын|\bшугыл"),
    "secrecy": re.compile(
        r"никому не (?:говори|сообща)|(?:папе|маме|родным) (?:пока )?не говори|не звони на (?:старый|мой)|"
        r"ешкімге айтпа|әкеңе айтпа|don'?t tell anyone|"
        # Plain-letter forms: speech recognisers often drop Kazakh letters ("екиме айтпа").
        r"\bеш\w* айтпа|\bеки?ме айтпа|\bаке\w* айтпа|\bпапа\w* айтпа|"
        r"(?:don'?t|do not) tell (?:anyone|dad|mom|mum|your (?:dad|mom|mum|husband|wife|family))|"
        r"keep (?:it|this) (?:a )?secret|don'?t call (?:the|my) old number"),
    "code_request": re.compile(
        r"код из смс|(?:назови|продиктуй|сообщи|скажи)\w* (?:мне )?код|кодты (?:айт|жібер)|"
        r"смс-код|(?:tell|send) me the code|one-time code|otp|"
        r"(?:dictate|read out|tell|give) (?:\w+ ){0,3}(?:the )?code|code from the sms"),
    "safe_account": re.compile(
        r"безопасн\w* сч[её]т|резервн\w* сч[её]т|защищ[её]нн\w* сч[её]т|қауіпсіз шот|safe account"),
    "authority": re.compile(
        r"служб\w* безопасности|сотрудник\w* (?:полиции|кнб|нацбанка)|следовател|"
        r"қауіпсіздік қызмет|полиция қызметкері|security (?:team|department|service)"),
    "easy_money": re.compile(
        r"подработк|доход\w* (?:от )?[\d\s]+.{0,20}(?:ежедневно|в день)|опыт не нужен|"
        r"қосымша табыс|күніне [\d\s]+|тәжірибе қажет емес|easy money|no experience needed|"
        r"part-time job|income [\d\s–-]+ ?₸ (?:daily|a day|per day)"),
    "new_number": re.compile(
        r"с номера (?:друга|подруги)|телефон (?:разбил|сломал|утопил)|это мой новый номер|"
        r"досымның нөмір|телефоным сынды|new number|"
        r"\bдос\w* ном\w*|жана ном\w*|телефон\w* сын|"
        r"(?:from|on) (?:a|my) friend'?s (?:number|phone)|(?:broke|lost|dropped) my phone|"
        r"this is my new number"),
}

# Kazakh letters -> the Russian ones a recogniser or a hurried typist writes instead.
_KAZAKH_TO_PLAIN = str.maketrans("әғқңөұүһі", "агкноуухи")

# Signals that on their own are enough to stop money moving without a person.
HARD = frozenset({"code_request", "safe_account", "secrecy", "new_number"})


def find_signals(text: str) -> list[str]:
    """Codes of the red flags present in the text, in a stable order."""
    low = text.lower()
    plain = low.translate(_KAZAKH_TO_PLAIN)
    found = [code for code, rx in _PATTERNS.items() if rx.search(low) or rx.search(plain)]
    if any(c.startswith("card:") for c in extract_contacts(text)):
        found.append("card_in_message")
    return found


def recipient_from_message(recipient: str | None, text: str) -> bool:
    """Is the action aimed at a card, phone, handle or site that the message itself supplied?

    This is the core trick of most schemes: "verify" or "pay" through the
    contact the fraudster gave. Paying a number the person already knows does
    not trip it; paying the number from the forwarded text does.
    """
    if not recipient:
        return False
    wanted = extract_contacts(recipient)
    return bool(wanted) and bool(wanted & extract_contacts(text))


def has_hard_signal(codes: list[str]) -> bool:
    """A hard flag alone, or the message's own contact plus any other flag."""
    if any(code in HARD for code in codes):
        return True
    soft = [c for c in codes if c != "recipient_from_message"]
    return "recipient_from_message" in codes and bool(soft)
