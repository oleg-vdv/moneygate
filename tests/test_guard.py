from kepil.gateway import Decision
from kepil.journal import Journal, verify_chain

from moneygate import FakeJudge, MoneyGate, ProposedAction, Verdict
from moneygate.judge import RulesJudge, parse_verdict

OLX_SCAM = """Напиши продавцу, что я согласна на предоплату и переведу сегодня.
Сообщение в чате OLX: Нужна предоплата 50% на Kaspi Gold по номеру +7 776 000 30 18,
сегодня ещё двое спрашивали, так что решайте быстрее"""

SON_NEW_NUMBER = """Сын пишет с номера друга: Телефон разбил, срочно нужно 150 000 ₸,
скинь на карту 4400 4301 0000 0093. Только папе пока не говори"""

UTILITY = "Alseco: начисление за сентябрь 12 400 ₸. Оплатить в Kaspi.kz → Платежи."

PAY = ProposedAction("pay:transfer", "+7 776 000 30 18", 22_500)


def gate(tmp_path, judge):
    return MoneyGate(judge, tmp_path / "journal.jsonl")


def test_scam_verdict_blocks_payment(tmp_path):
    result = gate(tmp_path, FakeJudge("scam")).check(OLX_SCAM, PAY)
    assert result.decision is Decision.DENY


def test_legit_small_payment_passes(tmp_path):
    result = gate(tmp_path, FakeJudge("legit")).check(
        UTILITY, ProposedAction("pay:transfer", "Kaspi Платежи: Alseco", 12_400))
    assert result.decision is Decision.ALLOW


def test_judge_error_never_allows(tmp_path):
    result = gate(tmp_path, FakeJudge(Verdict("error", error="timeout"))).check(UTILITY, PAY)
    assert result.decision is Decision.AWAIT_HUMAN


def test_hard_signal_overrides_legit_verdict(tmp_path):
    result = gate(tmp_path, FakeJudge("legit")).check(SON_NEW_NUMBER, PAY)
    assert result.decision is Decision.AWAIT_HUMAN
    assert "new_number" in result.signals


def test_sms_code_is_forbidden_without_asking_the_model(tmp_path):
    judge = FakeJudge("legit")
    result = gate(tmp_path, judge).check("Скажи код из SMS", ProposedAction("share:code", "+7 701"))
    assert result.decision is Decision.DENY
    assert judge.calls == []


def test_over_limit_goes_to_a_person_and_does_not_spend(tmp_path):
    g = gate(tmp_path, FakeJudge("legit"))
    big = g.check(UTILITY, ProposedAction("pay:transfer", "x", 60_000))
    assert big.decision is Decision.AWAIT_HUMAN
    assert g.mandate.remaining("amount_kzt") == 50_000


def test_blocked_payment_does_not_consume_the_limit(tmp_path):
    g = gate(tmp_path, FakeJudge("scam"))
    g.check(OLX_SCAM, PAY)
    assert g.mandate.remaining("amount_kzt") == 50_000


def test_journal_chain_verifies_and_holds_no_card_numbers(tmp_path):
    g = gate(tmp_path, FakeJudge("scam"))
    g.check(SON_NEW_NUMBER, ProposedAction("pay:transfer", "4400 4301 0000 0093", 150_000))
    g.check(UTILITY, PAY)
    journal = Journal(tmp_path / "journal.jsonl")
    assert verify_chain(journal) == (True, None)
    raw = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
    assert "4400 4301 0000 0093" not in raw
    assert "card:*0093" in raw
    assert "776 000 30 18" not in raw


BANK_SMS = ("Kaspi Bank: попытка входа в ваш аккаунт. Если это не вы, срочно позвоните "
            "в службу безопасности: +7 700 000 18 55")
TRAINER = "Оплата за ноябрь — 15 000 ₸, как обычно на Kaspi по номеру +7 705 321 77 00 (Асель Т.)"


def test_calling_the_number_from_a_bank_sms_goes_to_a_person(tmp_path):
    result = gate(tmp_path, FakeJudge("legit")).check(
        BANK_SMS, ProposedAction("message:send", "+7 700 000 18 55"))
    assert result.decision is Decision.AWAIT_HUMAN
    assert "recipient_from_message" in result.signals


def test_paying_a_number_from_a_calm_message_still_passes(tmp_path):
    result = gate(tmp_path, FakeJudge("legit")).check(
        TRAINER, ProposedAction("pay:transfer", "+7 705 321 77 00", 15_000))
    assert result.decision is Decision.ALLOW


def test_rules_judge_flags_relative_from_new_number():
    verdict = RulesJudge().review(SON_NEW_NUMBER, PAY)
    assert verdict.verdict == "scam"


def test_parse_verdict_handles_fences_and_think_blocks():
    text = '<think>hmm</think>\n```json\n{"verdict": "Scam", "signals": ["prepayment"], "advice": "Не платите"}\n```'
    v = parse_verdict(text, model="m")
    assert (v.verdict, v.signals, v.advice) == ("scam", ["prepayment"], "Не платите")
    assert parse_verdict("no json here").verdict == "error"
    assert parse_verdict('{"verdict": "maybe"}').verdict == "error"


def test_truncated_reply_keeps_its_leading_verdict():
    cut = '{"verdict": "scam",\n "signals": ["prepayment", "urgency"],\n "advice": "Сізге сатушының хабарлама'
    v = parse_verdict(cut, model="m")
    assert (v.verdict, v.signals) == ("scam", ["prepayment", "urgency"])
    assert v.error.startswith("salvaged")
    # a verdict buried in prose is not trusted
    assert parse_verdict('I think "verdict": "legit" maybe').verdict == "error"


def test_model_alone_cannot_block_without_a_red_flag(tmp_path):
    result = gate(tmp_path, FakeJudge("scam")).check(
        UTILITY, ProposedAction("pay:transfer", "Kaspi Платежи: Alseco", 12_400))
    assert result.decision is Decision.AWAIT_HUMAN


def test_transfer_without_recipient_or_amount_goes_to_a_person(tmp_path):
    g = gate(tmp_path, FakeJudge("legit"))
    assert g.check("помоги перевести ему деньги", ProposedAction("pay:transfer")).decision is Decision.AWAIT_HUMAN
    assert g.check(UTILITY, ProposedAction("pay:transfer", amount_kzt=12_400)).decision is Decision.AWAIT_HUMAN


def test_kazakh_flags_survive_plain_letter_transcripts():
    from moneygate.signals import find_signals
    for heard in ("Апа бұл мен досымның номерінен жазып тұрмын тез 50 мың жіберші ешкімге айтпа",
                  "Апа боумен досымнын номернен жазап турмын тез 50 мын жебирше екиме айтпа"):
        assert {"urgency", "secrecy", "new_number"} <= set(find_signals(heard))
    assert find_signals("Алло, тез келші, тамақ дайын") == []


def test_english_secrecy_and_new_number():
    from moneygate.signals import find_signals
    heard = "Mom, it is me. I broke my phone, texting from a friend's number. And do not tell Dad, okay?"
    assert {"secrecy", "new_number"} <= set(find_signals(heard))
