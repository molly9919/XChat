from __future__ import annotations

import json
from pathlib import Path


def load_peers(path: str) -> list[str]:
    state_file = Path(path)
    if not state_file.exists():
        return []
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    peers = payload.get("peers", [])
    if not isinstance(peers, list):
        return []
    result: list[str] = []
    for peer in peers:
        if isinstance(peer, str) and peer.strip():
            result.append(peer.strip())
    return result


def save_peers(path: str, peers: list[str]) -> None:
    state_file = Path(path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    unique = list(dict.fromkeys(peers))
    payload = {"peers": unique}
    state_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_message_cache(path: str) -> tuple[list[str], dict[str, list[str]]]:
    state_file = Path(path)
    if not state_file.exists():
        return [], {}
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], {}
    if not isinstance(payload, dict):
        return [], {}

    history_payload = payload.get("history", [])
    outbox_payload = payload.get("outbox", {})

    history: list[str] = []
    if isinstance(history_payload, list):
        for line in history_payload:
            if isinstance(line, str) and line.strip():
                history.append(line)

    outbox: dict[str, list[str]] = {}
    if isinstance(outbox_payload, dict):
        for peer, messages in outbox_payload.items():
            if not isinstance(peer, str):
                continue
            if not isinstance(messages, list):
                continue
            cleaned = [msg for msg in messages if isinstance(msg, str) and msg.strip()]
            if cleaned:
                outbox[peer] = cleaned

    return history, outbox


def save_message_cache(path: str, history: list[str], outbox: dict[str, list[str]]) -> None:
    state_file = Path(path)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    normalized_outbox: dict[str, list[str]] = {}
    for peer, messages in outbox.items():
        cleaned = [msg for msg in messages if isinstance(msg, str) and msg.strip()]
        if cleaned:
            normalized_outbox[peer] = cleaned

    payload = {
        "history": [line for line in history if isinstance(line, str) and line.strip()],
        "outbox": normalized_outbox,
    }
    state_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clear_message_cache(path: str) -> None:
    state_file = Path(path)
    if state_file.exists():
        state_file.unlink()
