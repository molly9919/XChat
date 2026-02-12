from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class TorConfig:
    socks_host: str = "127.0.0.1"
    socks_port: int = 0
    control_host: str = "127.0.0.1"
    control_port: int = 0
    virtual_port: int = 11009
    local_host: str = "127.0.0.1"
    local_port: int = 0
    control_password: str | None = None
    launch_private_tor: bool = True
    tor_binary: str | None = None
    tor_data_dir: str = str(Path.home() / ".local" / "share" / "xchat" / "tor")
    onion_key_file: str = str(Path.home() / ".local" / "share" / "xchat" / "onion_private_key")
    peers_file: str = str(Path.home() / ".local" / "share" / "xchat" / "peers.json")

    @classmethod
    def from_env(cls) -> "TorConfig":
        password = os.environ.get("XCHAT_TOR_CONTROL_PASSWORD")
        return cls(
            socks_host=os.environ.get("XCHAT_TOR_SOCKS_HOST", "127.0.0.1"),
            socks_port=int(os.environ.get("XCHAT_TOR_SOCKS_PORT", "0")),
            control_host=os.environ.get("XCHAT_TOR_CONTROL_HOST", "127.0.0.1"),
            control_port=int(os.environ.get("XCHAT_TOR_CONTROL_PORT", "0")),
            virtual_port=int(os.environ.get("XCHAT_TOR_VIRTUAL_PORT", "11009")),
            local_host=os.environ.get("XCHAT_TOR_LOCAL_HOST", "127.0.0.1"),
            local_port=int(os.environ.get("XCHAT_TOR_LOCAL_PORT", "0")),
            control_password=password,
            launch_private_tor=_bool_env("XCHAT_PRIVATE_TOR", True),
            tor_binary=os.environ.get("XCHAT_TOR_BINARY"),
            tor_data_dir=os.environ.get(
                "XCHAT_TOR_DATA_DIR", str(Path.home() / ".local" / "share" / "xchat" / "tor")
            ),
            onion_key_file=os.environ.get(
                "XCHAT_ONION_KEY_FILE", str(Path.home() / ".local" / "share" / "xchat" / "onion_private_key")
            ),
            peers_file=os.environ.get(
                "XCHAT_PEERS_FILE", str(Path.home() / ".local" / "share" / "xchat" / "peers.json")
            ),
        )
