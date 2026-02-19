from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(slots=True)
class ChatMessage:
    kind: str
    sender: str
    text: str


def encode_message(kind: str, sender: str, text: str) -> bytes:
    payload = {"type": kind, "sender": sender, "text": text}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(line: str) -> ChatMessage | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("type", ""))
    sender = str(payload.get("sender", ""))
    text = str(payload.get("text", ""))
    if not kind or not sender:
        return None
    return ChatMessage(kind=kind, sender=sender, text=text)
