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
