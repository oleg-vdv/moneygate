from moneygate import FakeJudge, ProposedAction
from moneygate.assistant import Proposal
from moneygate.telegram_bot import Bot

SON = "Мама, это я, пишу с номера друга. Срочно скинь 85 000 на карту 4400 4302 1187 6650, только папе не говори"


class FakeTelegram:
    def __init__(self):
        self.sent, self.calls = [], []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((chat_id, text, buttons))
        return {}

    def call(self, method, **params):
        self.calls.append(method)
        return True

    def download(self, file_id):
        return b"bytes:" + file_id.encode()


class FakeMedia:
    def read_screenshot(self, image, mime):
        return "them: " + SON

    def transcribe(self, audio):
        return SON


def proposer(action):
    return lambda judge, request, conversation: Proposal(action, "Перевожу на 4400 4302 1187 6650.")


PAY = ProposedAction("pay:transfer", "4400 4302 1187 6650", 85_000)


def bot(tmp_path, verdict, action=PAY, allowed=None):
    tg = FakeTelegram()
    return Bot(tg, FakeJudge(verdict), FakeMedia(), tmp_path, allowed, proposer(action)), tg


def msg(chat_id=7, **fields):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, **fields}}


def test_screenshot_then_request_is_stopped(tmp_path):
    b, tg = bot(tmp_path, "scam")
    b.on_update(msg(photo=[{"file_id": "small"}, {"file_id": "big"}]))
    assert "Добавил в переписку" in tg.sent[-1][1]
    b.on_update(msg(text="помоги перевести"))
    assert "ОСТАНОВЛЕНО" in tg.sent[-1][1]
    assert "card:*6650" in tg.sent[-1][1]
    assert "4400 4302" not in tg.sent[-1][1]  # the card number is never echoed back


def test_voice_with_hard_flag_asks_the_person_and_button_resolves(tmp_path):
    b, tg = bot(tmp_path, "legit")
    b.on_update(msg(voice={"file_id": "v"}))
    b.on_update(msg(text="скинь ему"))
    text, buttons = tg.sent[-1][1], tg.sent[-1][2]
    assert "решаете вы" in text
    data = buttons[0][0]["callback_data"]
    b.on_update({"update_id": 2, "callback_query": {"id": "q", "data": data,
                 "message": {"chat": {"id": 7}, "message_id": 1}}})
    assert "решение ваше" in tg.sent[-1][1]
    b.on_update({"update_id": 3, "callback_query": {"id": "q", "data": data,
                 "message": {"chat": {"id": 7}, "message_id": 1}}})
    assert "уже принято" in tg.sent[-1][1]


def test_plain_small_request_is_allowed(tmp_path):
    action = ProposedAction("pay:transfer", "Kaspi Платежи: Alseco", 12_400)
    b, tg = bot(tmp_path, "legit", action)
    b.on_update(msg(text="Оплати коммуналку: Alseco, 12 400 ₸, Kaspi → Платежи"))
    assert "можно" in tg.sent[-1][1]


def test_forwarded_text_is_context_not_request(tmp_path):
    b, tg = bot(tmp_path, "scam")
    b.on_update(msg(text=SON, forward_origin={"type": "hidden_user", "sender_user_name": "Арман"}))
    assert "Добавил" in tg.sent[-1][1]
    assert b.chats[7].lines == [f"Арман: {SON}"]


def test_closed_bot_tells_chat_id(tmp_path):
    b, tg = bot(tmp_path, "legit", allowed={1})
    b.on_update(msg(chat_id=99, text="привет"))
    assert "99" in tg.sent[-1][1]
    assert 99 not in b.chats


def test_mask_cards():
    from moneygate.telegram_bot import mask_cards
    assert mask_cards("на карту 4400 4302 1187 6650 сегодня") == "на карту *6650 сегодня"
    assert mask_cards("сумма 85 000 ₸, л/с 1023344") == "сумма 85 000 ₸, л/с 1023344"


def test_vague_request_asks_whom_and_how_much(tmp_path):
    b, tg = bot(tmp_path, "legit", ProposedAction("pay:transfer"))
    b.on_update(msg(text="помоги перевести ему деньги"))
    assert "Кому и сколько" in tg.sent[-1][1]


def test_empty_voice_is_reported_not_added(tmp_path):
    b, tg = bot(tmp_path, "legit")
    b.media.transcribe = lambda audio: ""
    b.on_update(msg(voice={"file_id": "v"}))
    assert "не расслышал" in tg.sent[-1][1]
    assert b.chats[7].lines == []


def test_reply_to_nobody_asks_for_the_conversation(tmp_path):
    b, tg = bot(tmp_path, "legit", ProposedAction("message:send", text="Жарайды, қазір жіберемін"))
    b.on_update(msg(text="жібер"))
    assert "О какой переписке" in tg.sent[-1][1]


def test_voice_without_card_still_goes_to_the_gate(tmp_path):
    b, tg = bot(tmp_path, "scam", ProposedAction("pay:transfer", amount_kzt=50_000))
    b.on_update(msg(voice={"file_id": "v"}))
    b.on_update(msg(text="жібер"))
    assert "ОСТАНОВЛЕНО" in tg.sent[-1][1]


def test_english_speaker_gets_english(tmp_path):
    b, tg = bot(tmp_path, "scam")
    b.on_update({"update_id": 1, "message": {"chat": {"id": 7}, "from": {"language_code": "en"},
                                             "photo": [{"file_id": "x"}]}})
    assert tg.sent[-1][1].startswith("Added to the conversation")
    b.on_update(msg(text="Please send him the money"))
    out = tg.sent[-1][1]
    assert "STOPPED" in out and "Red flags" in out and "pressure to hurry" in out


def test_language_follows_own_words_and_commands(tmp_path):
    from moneygate.telegram_bot import guess_lang
    assert guess_lang("send it to him", "ru") == "en"
    assert guess_lang("жібер ақшаны", "en") == "ru"
    assert guess_lang("ok", "ru") == "ru"
    b, tg = bot(tmp_path, "legit")
    b.on_update(msg(text="/en"))
    b.on_update(msg(text="/new"))
    assert tg.sent[-1][1].startswith("Starting over")


def test_daily_quota_stops_model_calls_but_not_the_owner(tmp_path):
    from moneygate.telegram_bot import Quota
    tg = FakeTelegram()
    b = Bot(tg, FakeJudge("scam"), FakeMedia(), tmp_path, None, proposer(PAY),
            quota=Quota(per_chat=1, total=3, unlimited={1}))
    b.on_update(msg(photo=[{"file_id": "x"}]))
    b.on_update(msg(text="send it"))
    assert "today's demo limit" in tg.sent[-1][1]
    b.on_update(msg(text="/help"))  # commands cost nothing and still answer
    assert "MoneyGate" in tg.sent[-1][1]
    for _ in range(5):
        b.on_update(msg(chat_id=1, text="send it"))
    assert "limit" not in tg.sent[-1][1]
    b.on_update(msg(chat_id=8, text="send it"))
    b.on_update(msg(chat_id=9, text="send it"))
    b.on_update(msg(chat_id=10, text="send it"))
    assert "overall limit" in tg.sent[-1][1]
