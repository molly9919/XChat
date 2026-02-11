from xchat.config import TorConfig


def test_private_tor_defaults_enabled() -> None:
    cfg = TorConfig.from_env()
    assert cfg.launch_private_tor is True
    assert cfg.socks_port == 0
    assert cfg.control_port == 0


def test_private_tor_env_override_disabled(monkeypatch) -> None:
    monkeypatch.setenv("XCHAT_PRIVATE_TOR", "0")
    monkeypatch.setenv("XCHAT_TOR_SOCKS_PORT", "9150")
    monkeypatch.setenv("XCHAT_TOR_CONTROL_PORT", "9151")
    cfg = TorConfig.from_env()
    assert cfg.launch_private_tor is False
    assert cfg.socks_port == 9150
    assert cfg.control_port == 9151
