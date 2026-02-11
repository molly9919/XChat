from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True)
class TorConfig:
    socks_host: str = "127.0.0.1"
    socks_port: int = 9050
    control_host: str = "127.0.0.1"
    control_port: int = 9051
    virtual_port: int = 11009
    local_host: str = "127.0.0.1"
    local_port: int = 0
    control_password: str | None = None

    @classmethod
    def from_env(cls) -> "TorConfig":
        password = os.environ.get("XCHAT_TOR_CONTROL_PASSWORD")
        return cls(
            socks_host=os.environ.get("XCHAT_TOR_SOCKS_HOST", "127.0.0.1"),
            socks_port=int(os.environ.get("XCHAT_TOR_SOCKS_PORT", "9050")),
            control_host=os.environ.get("XCHAT_TOR_CONTROL_HOST", "127.0.0.1"),
            control_port=int(os.environ.get("XCHAT_TOR_CONTROL_PORT", "9051")),
            virtual_port=int(os.environ.get("XCHAT_TOR_VIRTUAL_PORT", "11009")),
            local_host=os.environ.get("XCHAT_TOR_LOCAL_HOST", "127.0.0.1"),
            local_port=int(os.environ.get("XCHAT_TOR_LOCAL_PORT", "0")),
            control_password=password,
        )
