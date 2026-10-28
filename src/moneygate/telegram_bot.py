"""Telegram demo: forward the conversation, ask the assistant to help, watch MoneyGate decide.

  1. Forward the messages, a screenshot or a voice note you received.
  2. Write what you want: "help me pay him", "помоги перевести", "ответь, что согласна".
  3. The assistant proposes an action; MoneyGate allows it, stops it, or asks you.

The bot speaks English or Russian: it follows the language you write in (Latin text ->
English), falls back to your Telegram language, and /en or /ru switch it by hand.
Advice comes from the judge in the language of the conversation, Kazakh included.

  TELEGRAM_BOT_TOKEN=...            # from @BotFather, in ./.env
  TELEGRAM_ALLOWED_CHATS=123,456    # optional: who may use it (every message costs API calls)
  MONEYGATE_DAILY_PER_CHAT=40       # optional, for an open bot: model calls per chat per day
  MONEYGATE_DAILY_TOTAL=800         # optional: model calls per day for everyone together
  MONEYGATE_UNLIMITED_CHATS=123     # optional: chats the limits do not apply to
  python -m moneygate.telegram_bot

Nothing is ever paid or sent: "allowed" means the assistant would now go ahead.
Standard library only (long polling).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from kepil.gateway import Decision

from .actions import ProposedAction
from .assistant import propose
from .guard import GuardResult, MoneyGate
from .judge import OpenAICompatJudge, load_env_file
from .media import MediaError, MetaMedia

SIGNALS = {
    "ru": {
        "prepayment": "предоплата незнакомцу",
        "off_platform": "уводят из площадки в мессенджер или на внешнюю ссылку",
        "urgency": "торопят",
        "secrecy": "просят никому не говорить",
        "code_request": "просят код из SMS",
        "safe_account": "«безопасный счёт»",
        "authority": "представляются банком, полицией или госорганом",
        "easy_money": "лёгкий заработок",
        "new_number": "«новый номер» знакомого человека",
        "card_in_message": "номер карты прямо в сообщении",
        "recipient_from_message": "получатель взят из присланного сообщения",
    },
    "en": {
        "prepayment": "prepayment to a stranger",
        "off_platform": "moved off the marketplace to a messenger or an outside link",
        "urgency": "pressure to hurry",
        "secrecy": "asked to tell no one",
        "code_request": "asks for the SMS code",
        "safe_account": "a \"safe account\"",
        "authority": "poses as a bank, police or government",
        "easy_money": "easy money",
        "new_number": "someone you know on a \"new number\"",
        "card_in_message": "card number right in the message",
        "recipient_from_message": "recipient taken from the forwarded message",
    },
}

ACTIONS = {
    "ru": {"pay:transfer": "перевод", "share:card": "передача данных карты",
           "share:id": "передача ИИН или документа", "share:code": "передача кода из SMS",
           "message:send": "ответ от вашего имени", "link:open": "открыть ссылку"},
    "en": {"pay:transfer": "transfer", "share:card": "share card details", "share:id": "share an ID number",
           "share:code": "share the SMS code", "message:send": "reply on your behalf", "link:open": "open a link"},
}

TEXT = {
    "ru": {
        "help": (
            "Я ассистент с предохранителем MoneyGate.\n\n"
            "1. Перешлите мне переписку: сообщения, скриншот или голосовое.\n"
            "2. Напишите, что сделать: «помоги перевести», «ответь, что согласна».\n"
            "3. Я предложу действие, а MoneyGate решит: можно, нельзя или решаете вы.\n\n"
            "Деньги и сообщения на самом деле не отправляются: это демо.\n"
            "/new – начать новую переписку, /en – English.\n\n"
            "Хабарламаны, скриншотты немесе дауыстық хабарды жіберіңіз, сосын не істеу керегін жазыңыз."),
        "closed": "Этот бот закрыт для демо. Ваш chat id: {id}",
        "new": "Начинаем заново. Перешлите переписку.",
        "unreadable": "Не смог прочитать вложение: {err}",
        "not_heard": "не расслышал голосовое, запишите ещё раз или перешлите текстом",
        "added": "Добавил в переписку",
        "now_ask": "Теперь напишите, что сделать.",
        "no_answer": "Ассистент не ответил: {err}",
        "whom": "Кому и сколько? Перешлите переписку, скриншот или голосовое, где это сказано, "
                "или напишите получателя и сумму.",
        "which_chat": "О какой переписке речь? Перешлите сообщения, скриншот или голосовое.",
        "confirm": "Я проверил(а), выполнить", "cancel": "Отменить",
        "decided": "Это решение уже принято.",
        "done": "Хорошо, решение ваше: {what} (демо, ничего не отправлено).",
        "cancelled": "Отменено. Ничего не отправлено.",
        "wanted": "Ассистент хотел", "flags": "Признаки", "journal": "Запись в журнале",
        "allow": "MoneyGate: можно. Похоже на обычную просьбу, в пределах лимита (демо: ничего не отправлено).",
        "deny": "MoneyGate: ОСТАНОВЛЕНО. Ассистент не будет этого делать.",
        "human": "MoneyGate: решаете вы. Ассистент сам это делать не будет.",
        "screenshot": "скриншот", "voice": "голосовое сообщение", "request": "Просьба человека",
        "someone": "собеседник", "lang_set": "Язык: русский.",
        "limit_chat": "На сегодня лимит демо для этого чата исчерпан. Попробуйте завтра.",
        "limit_total": "Демо на сегодня исчерпало общий лимит запросов. Попробуйте завтра.",
    },
    "en": {
        "help": (
            "I'm an assistant with a MoneyGate safety gate.\n\n"
            "1. Forward me a conversation: messages, a screenshot or a voice note.\n"
            "2. Tell me what to do: \"help me pay him\", \"reply that I agree\".\n"
            "3. I propose an action, and MoneyGate decides: allowed, stopped, or your call.\n\n"
            "Nothing is really paid or sent: this is a demo.\n"
            "/new – start a new conversation, /ru – по-русски.\n\n"
            "Try it: forward a screenshot of a chat where someone asks for money, then write \"send it\"."),
        "closed": "This bot is closed for the demo. Your chat id: {id}",
        "new": "Starting over. Forward the conversation.",
        "unreadable": "Couldn't read the attachment: {err}",
        "not_heard": "couldn't make out the voice note, record it again or forward it as text",
        "added": "Added to the conversation",
        "now_ask": "Now tell me what to do.",
        "no_answer": "The assistant didn't answer: {err}",
        "whom": "To whom, and how much? Forward the chat, screenshot or voice note that says it, "
                "or write the recipient and the amount.",
        "which_chat": "Which conversation? Forward the messages, a screenshot or a voice note.",
        "confirm": "I've checked, go ahead", "cancel": "Cancel",
        "decided": "That's already been decided.",
        "done": "OK, your call: {what} (demo, nothing sent).",
        "cancelled": "Cancelled. Nothing was sent.",
        "wanted": "The assistant wanted to", "flags": "Red flags", "journal": "Journal record",
        "allow": "MoneyGate: allowed. Looks like an ordinary request, within the limit (demo: nothing sent).",
        "deny": "MoneyGate: STOPPED. The assistant will not do this.",
        "human": "MoneyGate: your call. The assistant won't do this on its own.",
        "screenshot": "screenshot", "voice": "voice note", "request": "The person's request",
        "someone": "the other person", "lang_set": "Language: English.",
        "limit_chat": "This chat has used today's demo limit. Please try again tomorrow.",
        "limit_total": "The demo has used today's overall limit. Please try again tomorrow.",
    },
}

_LATIN = re.compile(r"[a-z]", re.IGNORECASE)
_CYRILLIC = re.compile(r"[а-яёәғқңөұүһі]", re.IGNORECASE)


def guess_lang(text: str, fallback: str) -> str:
    """Latin-script text -> English; Cyrillic (Russian, Kazakh) -> Russian interface."""
    latin, cyrillic = len(_LATIN.findall(text)), len(_CYRILLIC.findall(text))
    if latin + cyrillic < 3:
        return fallback
    return "en" if latin > cyrillic else "ru"


class Telegram:
    def __init__(self, token: str) -> None:
        self.base = f"https://api.telegram.org/bot{token}/"
        self.files = f"https://api.telegram.org/file/bot{token}/"

    def call(self, method: str, timeout: float = 70, **params) -> dict | list | bool:
        data = json.dumps(params).encode("utf-8")
        request = urllib.request.Request(self.base + method, data=data,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("ok"):
            raise RuntimeError(f"{method}: {payload.get('description')}")
        return payload["result"]

    def download(self, file_id: str) -> bytes:
        path = self.call("getFile", file_id=file_id)["file_path"]
        with urllib.request.urlopen(self.files + urllib.parse.quote(path), timeout=60) as response:
            return response.read()

    def send(self, chat_id: int, text: str, buttons: list[list[dict]] | None = None) -> dict:
        params: dict = {"chat_id": chat_id, "text": text[:4000]}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        return self.call("sendMessage", **params)


class Quota:
    """Model calls per chat and in total, per UTC day: an open demo bot must not burn the credits.

    Chats in `unlimited` (the owner) are never counted. A limit of 0 means no limit.
    """

    def __init__(self, per_chat: int = 0, total: int = 0, unlimited: set[int] | None = None) -> None:
        self.per_chat, self.total, self.unlimited = per_chat, total, unlimited or set()
        self.day, self.used, self.used_total = "", {}, 0

    def take(self, chat_id: int) -> str | None:
        """None if the call may go ahead (and counts it); otherwise "chat" or "total"."""
        if chat_id in self.unlimited:
            return None
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self.day:
            self.day, self.used, self.used_total = today, {}, 0
        if self.total and self.used_total >= self.total:
            return "total"
        if self.per_chat and self.used.get(chat_id, 0) >= self.per_chat:
            return "chat"
        self.used[chat_id] = self.used.get(chat_id, 0) + 1
        self.used_total += 1
        return None


@dataclass
class Chat:
    lines: list[str] = field(default_factory=list)
    gate: MoneyGate | None = None
    pending: dict[str, ProposedAction] = field(default_factory=dict)
    lang: str | None = None     # None: not decided yet
    pinned: bool = False        # set by /en or /ru: stop guessing


class Bot:
    def __init__(self, tg: Telegram, judge: OpenAICompatJudge, media: MetaMedia,
                 journal_dir: Path, allowed: set[int] | None = None, proposer=propose,
                 voice_dir: Path | None = None, quota: Quota | None = None) -> None:
        self.voice_dir = voice_dir
        self.quota = quota or Quota()
        self.tg, self.judge, self.media = tg, judge, media
        self.propose = proposer
        self.journal_dir = journal_dir
        self.allowed = allowed
        self.chats: dict[int, Chat] = {}

    def chat(self, chat_id: int) -> Chat:
        state = self.chats.get(chat_id)
        if state is None:
            # One gate per person: the daily limit and the journal follow them across conversations.
            gate = MoneyGate(self.judge, self.journal_dir / f"{chat_id}.jsonl")
            state = self.chats[chat_id] = Chat(gate=gate)
        return state

    # --- incoming -------------------------------------------------------------

    def on_update(self, update: dict) -> None:
        if "callback_query" in update:
            return self.on_button(update["callback_query"])
        message = update.get("message")
        if not message:
            return
        chat_id = message["chat"]["id"]
        kind = next((k for k in ("photo", "voice", "audio", "document", "text") if k in message), "other")
        print(f"chat {chat_id}: {kind}", file=sys.stderr, flush=True)
        code = str((message.get("from") or {}).get("language_code") or "ru")
        tg_lang = "ru" if code.startswith(("ru", "kk", "uz", "ky", "be", "uk")) else "en"
        if self.allowed is not None and chat_id not in self.allowed:
            self.tg.send(chat_id, TEXT[tg_lang]["closed"].format(id=chat_id))
            return
        state = self.chat(chat_id)
        text = message.get("text") or message.get("caption") or ""
        forwarded = "forward_origin" in message or "forward_from" in message or "forward_sender_name" in message

        if text.startswith(("/en", "/ru")):
            state.lang, state.pinned = text[1:3], True
            self.tg.send(chat_id, TEXT[state.lang]["lang_set"])
            return
        # The person's own words decide the interface; forwarded text is someone else's.
        if not state.pinned and text and not forwarded and not text.startswith("/"):
            state.lang = guess_lang(text, state.lang or tg_lang)
        t = TEXT[state.lang or tg_lang]

        if text.startswith("/start") or text.startswith("/help"):
            self.tg.send(chat_id, t["help"])
            return
        if text.startswith("/new"):
            state.lines.clear()
            state.pending.clear()
            self.tg.send(chat_id, t["new"])
            return

        costly = any(k in message for k in ("photo", "voice", "audio")) or bool(
            str((message.get("document") or {}).get("mime_type", "")).startswith("image/")) or (
            bool(text) and not forwarded)
        if costly:
            over = self.quota.take(chat_id)
            if over:
                self.tg.send(chat_id, t["limit_" + over])
                return
        self.tg.call("sendChatAction", chat_id=chat_id, action="typing")
        try:
            got = self.read_media(message, t)
        except MediaError as exc:
            self.tg.send(chat_id, t["unreadable"].format(err=exc))
            return
        if got:
            state.lines.append(got)
        if forwarded and message.get("text"):
            state.lines.append(f"{_sender(message, t['someone'])}: {message['text']}")
            text = ""
        if forwarded or (got and not text):
            self.tg.send(chat_id, t["added"] + (":\n\n" + got[:700] if got else ".") + "\n\n" + t["now_ask"])
            return
        if text:
            self.handle_request(chat_id, state, text)

    def read_media(self, message: dict, t: dict) -> str:
        if "photo" in message:
            image = self.tg.download(message["photo"][-1]["file_id"])
            return f"[{t['screenshot']}]\n" + self.media.read_screenshot(image, "image/jpeg")
        document = message.get("document") or {}
        if str(document.get("mime_type", "")).startswith("image/"):
            image = self.tg.download(document["file_id"])
            return f"[{t['screenshot']}]\n" + self.media.read_screenshot(image, document["mime_type"])
        voice = message.get("voice") or message.get("audio")
        if voice:
            audio = self.tg.download(voice["file_id"])
            if self.voice_dir:  # local only (data/ is gitignored): to compare recognisers
                self.voice_dir.mkdir(parents=True, exist_ok=True)
                (self.voice_dir / f"{int(time.time())}.ogg").write_bytes(audio)
            heard = self.media.transcribe(audio)
            if not heard:
                raise MediaError(t["not_heard"])
            return f"[{t['voice']}]\n" + heard
        return ""

    def handle_request(self, chat_id: int, state: Chat, request: str) -> None:
        lang = state.lang or "ru"
        t = TEXT[lang]
        # No shared conversation: the request itself is the conversation (pasted text).
        conversation = "\n\n".join(state.lines) or request
        conversation = f"{t['request']}: {request}\n\n{conversation}"
        try:
            proposal = self.propose(self.judge, request, conversation)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            self.tg.send(chat_id, t["no_answer"].format(err=exc))
            return
        action = proposal.action
        # Nothing forwarded and nothing concrete asked: there is nothing to check yet.
        # With a conversation, the gate decides even if the recipient is missing: a voice
        # note "send 50 000, tell no one" has no card number and is still a scam to stop.
        if not state.lines and action.type == "pay:transfer" and not (action.recipient and action.amount_kzt):
            self.tg.send(chat_id, t["whom"])
            return
        if not state.lines and not action.recipient:
            self.tg.send(chat_id, t["which_chat"])
            return
        result = state.gate.check(conversation, action)
        text, buttons = render(proposal.reply, proposal.action, result, lang)
        if result.decision is Decision.AWAIT_HUMAN:
            key = result.record_hash[-12:] if result.record_hash else str(int(time.time()))
            state.pending[key] = proposal.action
            buttons = [[{"text": t["confirm"], "callback_data": f"ok:{key}"},
                        {"text": t["cancel"], "callback_data": f"no:{key}"}]]
        self.tg.send(chat_id, text, buttons)
        state.lines.clear()

    def on_button(self, query: dict) -> None:
        chat_id = query["message"]["chat"]["id"]
        state = self.chat(chat_id)
        lang = state.lang or "ru"
        t = TEXT[lang]
        verb, _, key = str(query.get("data", "")).partition(":")
        action = state.pending.pop(key, None)
        self.tg.call("answerCallbackQuery", callback_query_id=query["id"])
        self.tg.call("editMessageReplyMarkup", chat_id=chat_id, message_id=query["message"]["message_id"],
                     reply_markup={"inline_keyboard": []})
        if action is None:
            self.tg.send(chat_id, t["decided"])
        elif verb == "ok":
            self.tg.send(chat_id, t["done"].format(what=describe(action, lang)))
        else:
            self.tg.send(chat_id, t["cancelled"])


def _sender(message: dict, someone: str) -> str:
    origin = message.get("forward_origin") or {}
    user = origin.get("sender_user") or message.get("forward_from") or {}
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return name or origin.get("sender_user_name") or message.get("forward_sender_name") or someone


_CARD = re.compile(r"\b(?:\d[ -]?){12,18}(\d{4})\b")


def mask_cards(text: str) -> str:
    """The bot never repeats a full card number, even one the person sent."""
    return _CARD.sub(lambda m: "*" + m.group(1), text)


def describe(action: ProposedAction, lang: str = "ru") -> str:
    parts = [ACTIONS[lang].get(action.type, action.type)]
    if action.amount_kzt:
        parts.append(f"{action.amount_kzt:,.0f} ₸".replace(",", " "))
    if action.recipient:
        parts.append(f"→ {action.masked_recipient()}")
    return " ".join(parts)


def render(reply: str, action: ProposedAction, result: GuardResult,
           lang: str = "ru") -> tuple[str, list | None]:
    t = TEXT[lang]
    head = f"{t['wanted']}: {describe(action, lang)}"
    if reply:
        head += f"\n«{mask_cards(reply)}»" if lang == "ru" else f"\n\"{mask_cards(reply)}\""
    flags = [SIGNALS[lang].get(s, s) for s in result.signals]
    why = (f"\n{t['flags']}: " + "; ".join(flags)) if flags else ""
    advice = f"\n\n{mask_cards(result.advice)}" if result.advice else ""
    proof = f"\n\n{t['journal']}: {result.record_hash[:23]}…" if result.record_hash else ""
    body = {Decision.ALLOW: t["allow"], Decision.DENY: t["deny"]}.get(result.decision, t["human"])
    return f"{head}\n\n{body}{why}{advice}{proof}", None


def main() -> int:
    load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set (put it in ./.env)", file=sys.stderr)
        return 2
    allowed_env = os.environ.get("TELEGRAM_ALLOWED_CHATS", "").strip()
    allowed = {int(x) for x in allowed_env.split(",") if x.strip()} if allowed_env else None
    journal_dir = Path(os.environ.get("MONEYGATE_JOURNAL_DIR", "data/telegram"))
    journal_dir.mkdir(parents=True, exist_ok=True)
    tg = Telegram(token)
    voice_dir = Path(os.environ["MONEYGATE_VOICE_DIR"]) if os.environ.get("MONEYGATE_VOICE_DIR") else None
    unlimited = {int(x) for x in os.environ.get("MONEYGATE_UNLIMITED_CHATS", "").split(",") if x.strip()}
    quota = Quota(int(os.environ.get("MONEYGATE_DAILY_PER_CHAT", "0")),
                  int(os.environ.get("MONEYGATE_DAILY_TOTAL", "0")), unlimited)
    bot = Bot(tg, OpenAICompatJudge.from_env(), MetaMedia.from_env(), journal_dir, allowed,
              voice_dir=voice_dir, quota=quota)
    me = tg.call("getMe")
    print(f"@{me['username']} running; judge={bot.judge.model}; allowed={allowed or 'everyone'}; "
          f"daily per chat={quota.per_chat or '-'}, total={quota.total or '-'}", file=sys.stderr)
    offset = 0
    while True:
        try:
            updates = tg.call("getUpdates", offset=offset, timeout=50,
                              allowed_updates=["message", "callback_query"])
        except (urllib.error.URLError, TimeoutError, ConnectionError, RuntimeError) as exc:
            print(f"getUpdates: {exc}", file=sys.stderr)
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                bot.on_update(update)
            except Exception as exc:  # one bad update must not stop the bot
                print(f"update {update.get('update_id')}: {type(exc).__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
