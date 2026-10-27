import io
import json
import os
import subprocess
import sys
from pathlib import Path

from moneygate import FakeJudge, MoneyGate
from moneygate.mcp_server import Server, serve

ROOT = Path(__file__).resolve().parent.parent

OLX_SCAM = """Напиши продавцу, что я согласна на предоплату и переведу сегодня.
Сообщение в чате OLX: Нужна предоплата 50% на Kaspi Gold по номеру +7 776 000 30 18,
сегодня ещё двое спрашивали, так что решайте быстрее"""


def call(server, args, id_=1):
    return server.handle({"jsonrpc": "2.0", "id": id_, "method": "tools/call",
                          "params": {"name": "check_action", "arguments": args}})


def test_initialize_and_list(tmp_path):
    server = Server(MoneyGate(FakeJudge("legit"), tmp_path / "j.jsonl"))
    init = server.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                          "params": {"protocolVersion": "2025-03-26", "capabilities": {}}})
    assert init["result"]["protocolVersion"] == "2025-03-26"
    assert "tools" in init["result"]["capabilities"]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == ["check_action"]


def test_scam_is_denied_with_structured_result(tmp_path):
    server = Server(MoneyGate(FakeJudge("scam"), tmp_path / "j.jsonl"))
    result = call(server, {"conversation": OLX_SCAM, "action_type": "pay:transfer",
                           "recipient": "+7 776 000 30 18", "amount_kzt": 22500})["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "deny"
    assert json.loads(result["content"][0]["text"])["decision"] == "deny"
    assert result["structuredContent"]["journal_record"]


def test_bad_arguments_are_a_tool_error(tmp_path):
    server = Server(MoneyGate(FakeJudge("legit"), tmp_path / "j.jsonl"))
    result = call(server, {"conversation": "x", "action_type": "pay:crypto"})["result"]
    assert result["isError"] is True
    assert "unknown action type" in result["content"][0]["text"]


def test_unknown_method_and_tool(tmp_path):
    server = Server(MoneyGate(FakeJudge("legit"), tmp_path / "j.jsonl"))
    assert server.handle({"jsonrpc": "2.0", "id": 5, "method": "nope"})["error"]["code"] == -32601
    bad = server.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "x"}})
    assert bad["error"]["code"] == -32602


def test_serve_reads_lines_and_survives_bad_json(tmp_path):
    server = Server(MoneyGate(FakeJudge("legit"), tmp_path / "j.jsonl"))
    stdin = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\nnot json\n\n')
    stdout = io.BytesIO()
    serve(server, stdin, stdout)
    lines = [json.loads(l) for l in stdout.getvalue().splitlines()]
    assert lines[0] == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert lines[1]["error"]["code"] == -32700


def test_stdio_subprocess(tmp_path):
    env = dict(os.environ, MONEYGATE_FAKE="suspicious", MONEYGATE_JOURNAL=str(tmp_path / "j.jsonl"),
               PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT.parent / "kepil" / "src")]))
    requests = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "check_action", "arguments": {
            "conversation": OLX_SCAM, "action_type": "pay:transfer", "recipient": "+7 776 000 30 18",
            "amount_kzt": 22500}}},
    ]
    proc = subprocess.run([sys.executable, "-m", "moneygate.mcp_server"], cwd=tmp_path, env=env,
                          input="\n".join(json.dumps(r, ensure_ascii=False) for r in requests).encode("utf-8"),
                          capture_output=True, timeout=60)
    replies = [json.loads(l) for l in proc.stdout.splitlines()]
    assert [r["id"] for r in replies] == [0, 1]
    assert replies[1]["result"]["structuredContent"]["decision"] == "await_human"
