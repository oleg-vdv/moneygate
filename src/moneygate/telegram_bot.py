"""Telegram demo: forward the conversation, ask the assistant to help, watch MoneyGate decide.

  1. Forward the messages, a screenshot or a voice note you received.
  2. Write what you want: "помоги перевести", "ответь, что согласна".
  3. The assistant proposes an action; MoneyGate allows it, stops it, or asks you.

  TELEGRAM_BOT_TOKEN=...            # from @BotFather, in ./.env
  TELEGRAM_ALLOWED_CHATS=123,456    # optional: who may use it (every message costs API calls)
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

SIGNAL_RU = {
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
}

ACTION_RU = {
    "pay:transfer": "перевод", "share:card": "передача данных карты", "share:id": "передача ИИН или документа",
    "share:code": "передача кода из SMS", "message:send": "ответ от вашего имени", "link:open": "открыть ссылку",
}

HELP = (
    "Я ассистент с предохранителем MoneyGate.\n\n"
    "1. Перешлите мне переписку: сообщения, скриншот или голосовое.\n"
    "2. Напишите, что сделать: «помоги перевести», «ответь, что согласна».\n"
    "3. Я предложу действие, а MoneyGate решит: можно, нельзя или решаете вы.\n\n"
    "Деньги и сообщения на самом деле не отправляются: это демо.\n"
    "/new — начать новую переписку.\n\n"
    "Хабарламаны, скриншотты немесе дауыстық хабарды жіберіңіз, сосын не істеу керегін жазыңыз."
)


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


@dataclass
class Chat:
    lines: list[str] = field(default_factory=list)
    gate: MoneyGate | None = None
    pending: dict[str, ProposedAction] = field(default_factory=dict)


class Bot:
    def __init__(self, tg: Telegram, judge: OpenAICompatJudge, media: MetaMedia,
                 journal_dir: Path, allowed: set[int] | None = None, proposer=propose) -> None:
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
        if self.allowed is not None and chat_id not in self.allowed:
            self.tg.send(chat_id, f"Этот бот закрыт для демо. Ваш chat id: {chat_id}")
            return
        state = self.chat(chat_id)
        text = message.get("text") or message.get("caption") or ""
        forwarded = "forward_origin" in message or "forward_from" in message or "forward_sender_name" in message

        if text.startswith("/start") or text.startswith("/help"):
            self.tg.send(chat_id, HELP)
            return
        if text.startswith("/new"):
            state.lines.clear()
            state.pending.clear()
            self.tg.send(chat_id, "Начинаем заново. Перешлите переписку.")
            return

        self.tg.call("sendChatAction", chat_id=chat_id, action="typing")
        try:
            got = self.read_media(message)
        except MediaError as exc:
            self.tg.send(chat_id, f"Не смог прочитать вложение: {exc}")
            return
        if got:
            state.lines.append(got)
        if forwarded and message.get("text"):
            state.lines.append(f"{_sender(message)}: {message['text']}")
            text = ""
        if forwarded or (got and not text):
            self.tg.send(chat_id, "Добавил в переписку" + (":\n\n" + got[:700] if got else ".")
                         + "\n\nТеперь напишите, что сделать.")
            return
        if text:
            self.handle_request(chat_id, state, text)

    def read_media(self, message: dict) -> str:
        if "photo" in message:
            image = self.tg.download(message["photo"][-1]["file_id"])
            return "[скриншот]\n" + self.media.read_screenshot(image, "image/jpeg")
        document = message.get("document") or {}
        if str(document.get("mime_type", "")).startswith("image/"):
            image = self.tg.download(document["file_id"])
            return "[скриншот]\n" + self.media.read_screenshot(image, document["mime_type"])
        voice = message.get("voice") or message.get("audio")
        if voice:
            audio = self.tg.download(voice["file_id"])
            return "[голосовое сообщение]\n" + self.media.transcribe(audio)
        return ""

    def handle_request(self, chat_id: int, state: Chat, request: str) -> None:
        # No shared conversation: the request itself is the conversation (pasted text).
        conversation = "\n\n".join(state.lines) or request
        conversation = f"Просьба человека: {request}\n\n{conversation}"
        try:
            proposal = self.propose(self.judge, request, conversation)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            self.tg.send(chat_id, f"Ассистент не ответил: {exc}")
            return
        action = proposal.action
        if action.type == "pay:transfer" and not (action.recipient and action.amount_kzt):
            # Keep what was forwarded so far: the person only has to add the missing part.
            self.tg.send(chat_id, "Кому и сколько? Перешлите переписку, скриншот или голосовое, "
                                  "где это сказано, или напишите получателя и сумму.")
            return
        result = state.gate.check(conversation, action)
        text, buttons = render(proposal.reply, proposal.action, result)
        if result.decision is Decision.AWAIT_HUMAN:
            key = result.record_hash[-12:] if result.record_hash else str(int(time.time()))
            state.pending[key] = proposal.action
            buttons = [[{"text": "Я проверил(а), выполнить", "callback_data": f"ok:{key}"},
                        {"text": "Отменить", "callback_data": f"no:{key}"}]]
        self.tg.send(chat_id, text, buttons)
        state.lines.clear()

    def on_button(self, query: dict) -> None:
        chat_id = query["message"]["chat"]["id"]
        verb, _, key = str(query.get("data", "")).partition(":")
        action = self.chat(chat_id).pending.pop(key, None)
        self.tg.call("answerCallbackQuery", callback_query_id=query["id"])
        self.tg.call("editMessageReplyMarkup", chat_id=chat_id, message_id=query["message"]["message_id"],
                     reply_markup={"inline_keyboard": []})
        if action is None:
            self.tg.send(chat_id, "Это решение уже принято.")
        elif verb == "ok":
            self.tg.send(chat_id, f"Хорошо, решение ваше: {ACTION_RU[action.type]} выполнен(а) (демо).")
        else:
            self.tg.send(chat_id, "Отменено. Ничего не отправлено.")


def _sender(message: dict) -> str:
    origin = message.get("forward_origin") or {}
    user = origin.get("sender_user") or message.get("forward_from") or {}
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return name or origin.get("sender_user_name") or message.get("forward_sender_name") or "собеседник"


_CARD = re.compile(r"\b(?:\d[ -]?){12,18}(\d{4})\b")


def mask_cards(text: str) -> str:
    """The bot never repeats a full card number, even one the person sent."""
    return _CARD.sub(lambda m: "*" + m.group(1), text)


def describe(action: ProposedAction) -> str:
    parts = [ACTION_RU.get(action.type, action.type)]
    if action.amount_kzt:
        parts.append(f"{action.amount_kzt:,.0f} ₸".replace(",", " "))
    if action.recipient:
        parts.append(f"→ {action.masked_recipient()}")
    return " ".join(parts)


def render(reply: str, action: ProposedAction, result: GuardResult) -> tuple[str, list | None]:
    head = f"Ассистент хотел: {describe(action)}"
    if reply:
        head += f"\n«{mask_cards(reply)}»"
    flags = [SIGNAL_RU.get(s, s) for s in result.signals]
    why = ("\nПризнаки: " + "; ".join(flags)) if flags else ""
    advice = f"\n\n{mask_cards(result.advice)}" if result.advice else ""
    proof = f"\n\nЗапись в журнале: {result.record_hash[:23]}…" if result.record_hash else ""
    if result.decision is Decision.ALLOW:
        body = "MoneyGate: можно. Похоже на обычную просьбу, в пределах лимита (демо: ничего не отправлено)."
    elif result.decision is Decision.DENY:
        body = "MoneyGate: ОСТАНОВЛЕНО. Ассистент не будет этого делать."
    else:
        body = "MoneyGate: решаете вы. Ассистент сам это делать не будет."
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
    bot = Bot(tg, OpenAICompatJudge.from_env(), MetaMedia.from_env(), journal_dir, allowed)
    me = tg.call("getMe")
    print(f"@{me['username']} running; judge={bot.judge.model}; allowed={allowed or 'everyone'}", file=sys.stderr)
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
