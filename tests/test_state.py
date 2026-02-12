from pathlib import Path

from xchat.state import load_peers, save_peers


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
