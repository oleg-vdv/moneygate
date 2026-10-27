"""MCP server: any agent asks MoneyGate before it moves money for a person.

One tool, check_action. The agent passes the conversation it is acting on and the
action it is about to take; the answer is allow / deny / await_human with advice.
The agent must not act on anything but "allow".

  python -m moneygate.mcp_server                        # MONEYGATE_* env or ./.env
  MONEYGATE_FAKE=scam python -m moneygate.mcp_server    # offline, fixed verdict

Claude Desktop / Claude Code config:
  {"mcpServers": {"moneygate": {"command": "python", "args": ["-m", "moneygate.mcp_server"],
                                "cwd": "<repo>", "env": {"PYTHONPATH": "src"}}}}

Standard library only: MCP over stdio is newline-delimited JSON-RPC 2.0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from . import __doc__ as PACKAGE_DOC
from .actions import ACTION_TYPES, ProposedAction
from .guard import MoneyGate
from .judge import FakeJudge, OpenAICompatJudge, load_env_file

SERVER_INFO = {"name": "moneygate", "version": "0.1.0"}
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

CHECK_ACTION = {
    "name": "check_action",
    "title": "Check a money-moving action",
    "description": (
        "Call BEFORE you send money, share a card number, an ID number or an SMS code, "
        "send a message on the person's behalf, or open a link from a message. Pass the "
        "conversation you are acting on, word for word, and the exact action. Act only if "
        "decision is \"allow\". On \"deny\" do not act and show the advice to the person. "
        "On \"await_human\" ask the person to confirm themselves, and show the advice."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "conversation": {"type": "string",
                             "description": "The person's request and the messages it refers to, verbatim."},
            "action_type": {"type": "string", "enum": list(ACTION_TYPES)},
            "recipient": {"type": "string",
                          "description": "Card, phone, account, handle or domain exactly as written."},
            "amount_kzt": {"type": "number", "minimum": 0},
            "text": {"type": "string", "description": "The message you want to send, for message:send."},
        },
        "required": ["conversation", "action_type"],
        "additionalProperties": False,
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["allow", "deny", "await_human"]},
            "reason": {"type": "string"},
            "verdict": {"type": ["string", "null"]},
            "signals": {"type": "array", "items": {"type": "string"}},
            "advice": {"type": "string"},
            "journal_record": {"type": ["string", "null"]},
        },
        "required": ["decision", "reason"],
    },
}


class Server:
    def __init__(self, gate: MoneyGate) -> None:
        self.gate = gate
        self._methods: dict[str, Callable[[dict], Any]] = {
            "initialize": self.initialize,
            "ping": lambda _: {},
            "tools/list": lambda _: {"tools": [CHECK_ACTION]},
            "tools/call": self.call_tool,
        }

    def initialize(self, params: dict) -> dict:
        asked = params.get("protocolVersion")
        return {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": PACKAGE_DOC.strip() + " " + CHECK_ACTION["description"],
        }

    def call_tool(self, params: dict) -> dict:
        if params.get("name") != "check_action":
            raise LookupError(f"unknown tool: {params.get('name')!r}")
        args = params.get("arguments") or {}
        try:
            action = ProposedAction(args["action_type"], args.get("recipient") or None,
                                    float(args.get("amount_kzt") or 0), args.get("text") or None)
            conversation = str(args["conversation"])
        except (KeyError, ValueError, TypeError) as exc:
            # A bad call is a tool error the agent can read and fix, not a protocol error.
            return {"content": [{"type": "text", "text": f"invalid arguments: {exc}"}], "isError": True}
        result = self.gate.check(conversation, action)
        out = {
            "decision": result.decision.value,
            "reason": result.reason,
            "verdict": result.verdict.verdict if result.verdict else None,
            "signals": result.signals,
            "advice": result.advice,
            "journal_record": result.record_hash,
        }
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                "structuredContent": out, "isError": False}

    def handle(self, message: dict) -> dict | None:
        """One JSON-RPC message in, one response out (None for notifications)."""
        if "id" not in message:
            return None
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        method = self._methods.get(message.get("method", ""))
        if method is None:
            reply["error"] = {"code": -32601, "message": f"method not found: {message.get('method')}"}
            return reply
        try:
            reply["result"] = method(message.get("params") or {})
        except LookupError as exc:
            reply["error"] = {"code": -32602, "message": str(exc)}
        except Exception as exc:  # the server must outlive one bad call
            reply["error"] = {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}
        return reply


def serve(server: Server, stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    for raw in stdin:
        if not raw.strip():
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            reply = server.handle(message) if isinstance(message, dict) else None
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            stdout.flush()


def main() -> int:
    load_env_file()
    fake = os.environ.get("MONEYGATE_FAKE")
    judge = FakeJudge(fake) if fake else OpenAICompatJudge.from_env()
    journal = Path(os.environ.get("MONEYGATE_JOURNAL", "data/journal.jsonl"))
    journal.parent.mkdir(parents=True, exist_ok=True)
    print(f"moneygate MCP: judge={fake or judge.model}, journal={journal}", file=sys.stderr)
    serve(Server(MoneyGate(judge, journal)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
