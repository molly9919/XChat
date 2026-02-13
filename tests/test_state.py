from pathlib import Path

from xchat.state import clear_message_cache, load_message_cache, load_peers, save_message_cache, save_peers


def test_save_and_load_peers(tmp_path: Path) -> None:
    path = tmp_path / "peers.json"
    save_peers(str(path), ["alice.onion", "bob.onion", "alice.onion"])
    peers = load_peers(str(path))
    assert peers == ["alice.onion", "bob.onion"]


def test_load_peers_handles_missing_or_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    assert load_peers(str(path)) == []

    path.write_text("{invalid", encoding="utf-8")
    assert load_peers(str(path)) == []


def test_message_cache_roundtrip_and_clear(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    save_message_cache(
        str(path),
        ["me → alice.onion: hi", "alice.onion: hello"],
        {"alice.onion": ["queued 1", "queued 2"]},
    )

    history, outbox = load_message_cache(str(path))
    assert history == ["me → alice.onion: hi", "alice.onion: hello"]
    assert outbox == {"alice.onion": ["queued 1", "queued 2"]}

    clear_message_cache(str(path))
    assert load_message_cache(str(path)) == ([], {})
